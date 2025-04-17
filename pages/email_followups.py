import streamlit as st
import os
import sys
import json
from datetime import datetime
from io import StringIO
import uuid

# # Add parent directory to path to import TranscriptAnalyzer
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the TranscriptAnalyzer class
# Note: In production, you'd properly structure your imports
from transcript_analyzer import TranscriptAnalyzer

# Set page configuration
st.set_page_config(
    page_title="Client Transcript Follow-up Analyzer",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)


AZURE_OPENAI_DEPLOYMENT_NAME = st.secrets.get("AZURE_OPENAI_DEPLOYMENT_NAME")

# Email configuration (hidden from user)
EMAIL_ADDRESS = st.secrets.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = st.secrets.get("EMAIL_PASSWORD")
DEFAULT_RECIPIENT = os.environ.get("DEFAULT_RECIPIENT", "anvithareddy1308@gmail.com")



email_configured = all([
    EMAIL_ADDRESS,
    EMAIL_PASSWORD
])

# Initialize session state variables
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'transcript_id' not in st.session_state:
    st.session_state.transcript_id = None
if 'email_sent' not in st.session_state:
    st.session_state.email_sent = False

def process_transcript(transcript_text):
    """Process the transcript and return analysis results"""
    try:
        # Generate a unique ID for this transcript
        transcript_id = f"TRANSCRIPT-{uuid.uuid4().hex[:8]}"
        st.session_state.transcript_id = transcript_id
        
        # Create analyzer instance
        analyzer = TranscriptAnalyzer(
            AZURE_OPENAI_DEPLOYMENT_NAME
        )
        
        # Process the transcript
        results = analyzer.get_structured_follow_ups(transcript_text)
        st.session_state.analysis_results = results
        
        return results, transcript_id, analyzer
    
    except Exception as e:
        st.error(f"Error processing transcript: {str(e)}")
        return None, None, None

def send_follow_up_email(analyzer, transcript_id, results, recipient_email):
    """Send follow-up email if needed"""
    if not results or results.get("status") != "success" or not results.get("follow_ups"):
        st.warning("No follow-ups to send email about")
        return False
        
    try:
        email_config = {
            "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": int(os.environ.get("SMTP_PORT", 587)),
            "email_address": EMAIL_ADDRESS,
            "email_password": EMAIL_PASSWORD
        }
        
        email_sent = analyzer.send_email_alert(
            transcript_id=transcript_id,
            recipient_email=recipient_email,
            follow_up_info=results,
            email_config=email_config
        )
        
        return email_sent
        
    except Exception as e:
        st.error(f"Error sending email: {str(e)}")
        return False

# Create the Streamlit UI
st.title("🔍 Client Transcript Follow-up Analyzer")

# Sidebar configuration
st.sidebar.header("About")
st.sidebar.info(
    "This application analyzes client transcripts to identify "
    "necessary follow-up actions and can automatically send "
    "notifications for high priority items."
)

# Check if credentials are properly configured
# if not credentials_configured:
#     st.error(
#         "⚠️ Azure OpenAI credentials are not configured. "
#         "Please set the required environment variables before using this application."
#     )
#     st.stop()

# Main content area
tab1, tab2 = st.tabs(["Upload & Analyze", "Results"])

with tab1:
    st.header("Upload Client Transcript")
    
    # File upload option
    uploaded_file = st.file_uploader("Upload a transcript file (txt)", type=["txt"])
    
    # Text area option
    st.markdown("### Or paste transcript text directly")
    transcript_text = st.text_area(
        "Paste transcript content here:", 
        height=300,
        placeholder="Client: Hello, I'm calling about...\nAgent: How can I help you today?"
    )
    
    # Email notification section
    if email_configured:
        st.markdown("### Email Notification")
        send_email = st.checkbox("Send email notification for follow-ups", value=True)
        
        if send_email:
            recipient_email = st.text_input(
                "Recipient email address:", 
                value=DEFAULT_RECIPIENT
            )
    else:
        send_email = False
        recipient_email = DEFAULT_RECIPIENT
        st.warning("⚠️ Email functionality is not configured. Notifications will not be sent.")
    
    # Process button
    col1, col2 = st.columns([1, 4])
    with col1:
        analyze_button = st.button("Analyze Transcript", type="primary")

# Process the transcript when the button is clicked
if analyze_button:
    final_transcript = ""
    
    # Get transcript from file upload or text area
    if uploaded_file is not None:
        stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
        final_transcript = stringio.read()
    elif transcript_text:
        final_transcript = transcript_text
    
    if not final_transcript.strip():
        st.error("Please provide a transcript to analyze")
    else:
        with st.spinner("Analyzing transcript..."):
            results, transcript_id, analyzer = process_transcript(final_transcript)
            
            if results and results.get("status") == "success":
                # Switch to results tab automatically
                tab2.button("View Results", key="switch_to_results")
                
                # Send email if requested
                if send_email and email_configured and results.get("total_follow_ups", 0) > 0:
                    with st.spinner("Sending email notification..."):
                        email_success = send_follow_up_email(
                            analyzer, 
                            transcript_id, 
                            results, 
                            recipient_email
                        )
                        st.session_state.email_sent = email_success

# Display results in the Results tab
with tab2:
    if st.session_state.analysis_results:
        results = st.session_state.analysis_results
        
        if results.get("status") == "success":
            st.header("📊 Analysis Results")
            
            # Email notification status
            if st.session_state.email_sent:
                st.success(f"✅ Follow-up email sent to {recipient_email}")
            
            # Summary section
            st.subheader("Conversation Summary")
            st.write(results.get("summary", "No summary available"))
            
            # Statistics
            st.subheader("Statistics")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Follow-ups", results.get("total_follow_ups", 0))
            col2.metric("High Priority", results.get("priority_counts", {}).get("High", 0))
            col3.metric("Medium Priority", results.get("priority_counts", {}).get("Medium", 0))
            col4.metric("Low Priority", results.get("priority_counts", {}).get("Low", 0))
            
            # Follow-up items section
            if results.get("follow_ups"):
                st.subheader("Follow-up Actions Required")
                
                for i, item in enumerate(results.get("follow_ups", []), 1):
                    with st.expander(f"{i}. {item['action']} (Priority: {item['priority']})"):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            priority = item.get("priority", "Low")
                            if priority == "High":
                                st.error("HIGH PRIORITY")
                            elif priority == "Medium":
                                st.warning("MEDIUM PRIORITY")
                            else:
                                st.info("LOW PRIORITY")
                        
                        with col2:
                            st.markdown(f"**Action:** {item.get('action', 'No action specified')}")
                            st.markdown(f"**Justification:** {item.get('justification', 'No justification provided')}")
                            st.markdown(f"**Details:** {item.get('details', 'No details available')}")
            else:
                st.success("No follow-up actions required!")
        else:
            st.error(f"Analysis failed: {results.get('message', 'Unknown error')}")
    else:
        st.info("Upload and analyze a transcript to see results here.")

# Footer
st.markdown("---")
# st.caption("Client Transcript Follow-up Analyzer © 2025")