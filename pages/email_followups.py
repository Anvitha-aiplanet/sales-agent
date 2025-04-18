import streamlit as st
import os
import sys
import json
from datetime import datetime
from io import StringIO
import uuid

from follow_up_test import TranscriptAnalyzer

# Set page configuration
st.set_page_config(
    page_title="Client Transcript Follow-up Analyzer",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Store the deployment name in session state
if 'deployment_name' not in st.session_state:
    st.session_state.deployment_name = "intern-gpt4"


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
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "Upload & Analyze"
if 'email_draft' not in st.session_state:
    st.session_state.email_draft = None
if 'show_feedback' not in st.session_state:
    st.session_state.show_feedback = False
if 'show_send_options' not in st.session_state:
    st.session_state.show_send_options = False
if 'feedback_provided' not in st.session_state:
    st.session_state.feedback_provided = ""
if 'email_sent_final' not in st.session_state:
    st.session_state.email_sent_final = False
if 'analyzer' not in st.session_state:
    st.session_state.analyzer = None

def process_transcript(transcript_text):
    """Process the transcript and return analysis results"""
    try:
        # Generate a unique ID for this transcript
        transcript_id = f"TRANSCRIPT-{uuid.uuid4().hex[:8]}"
        st.session_state.transcript_id = transcript_id
        
        # Create analyzer instance
        analyzer = TranscriptAnalyzer(
            st.session_state.deployment_name
        )
        st.session_state.analyzer = analyzer
        
        # Process the transcript
        results = analyzer.get_structured_follow_ups(transcript_text)
        st.session_state.analysis_results = results
        
        return results, transcript_id, analyzer
    
    except Exception as e:
        st.error(f"Error processing transcript: {str(e)}")
        return None, None, None

def display_email_workflow(follow_up_info, transcript_id):
    """Display the email drafting and approval workflow"""
    
    # Check if we have follow-ups to process
    if not follow_up_info or follow_up_info.get("status") != "success" or not follow_up_info.get("follow_ups"):
        st.warning("No follow-ups found to create email draft")
        return
    
    st.header("📧 Email Draft and Approval")
    
    # Generate initial draft if not already done
    if not st.session_state.email_draft:
        with st.spinner("Generating email draft..."):
            email_draft = st.session_state.analyzer.generate_email_draft(follow_up_info, transcript_id)
            st.session_state.email_draft = email_draft
    
    # Display current draft
    with st.container():
        st.subheader("Email Draft")
        st.text_input("Subject:", value=st.session_state.email_draft["subject"], key="email_subject", disabled=False)
        
        # Make the body editable
        updated_body = st.text_area("Body:", value=st.session_state.email_draft["body"], height=300, key="email_body")
        
        # If user edited the body, update the session state
        if updated_body != st.session_state.email_draft["body"]:
            st.session_state.email_draft["body"] = updated_body
    
    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("Regenerate Email", key="regenerate_email"):
            st.session_state.show_feedback = True
    
    with col2:
        if st.button("Approve & Send", key="approve_email", type="primary"):
            st.session_state.show_send_options = True
    
    with col3:
        if st.button("Save Draft", key="save_draft"):
            # Update the subject in case it was edited
            st.session_state.email_draft["subject"] = st.session_state.email_subject
            st.success("Draft saved successfully!")
    
    # Feedback form for regeneration
    if st.session_state.show_feedback:
        st.subheader("Provide Feedback for Regeneration")
        feedback = st.text_area(
            "What would you like to change in the email draft?",
            placeholder="e.g., Make it more formal, add more details about the third follow-up item, etc.",
            key="feedback_text"
        )
        
        if st.button("Submit Feedback & Regenerate", key="submit_feedback"):
            if feedback:
                with st.spinner("Regenerating email draft..."):
                    new_draft = st.session_state.analyzer.generate_email_draft(follow_up_info, transcript_id, feedback)
                    st.session_state.email_draft = new_draft
                    st.session_state.feedback_provided = feedback
                    st.session_state.show_feedback = False
                    st.rerun()
            else:
                st.warning("Please provide feedback for regeneration.")
    
    # Email sending options
    if st.session_state.show_send_options:
        st.subheader("Send Email")
        recipient_email = st.text_input(
            "Recipient email address:", 
            value=DEFAULT_RECIPIENT,
            key="final_recipient_email"
        )
        
        if st.button("Confirm & Send Now", key="send_email_final"):
            # Update the email draft with any edits
            st.session_state.email_draft["subject"] = st.session_state.email_subject
            
            # Configure email settings
            email_config = {
                "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
                "smtp_port": int(os.environ.get("SMTP_PORT", 587)),
                "email_address": EMAIL_ADDRESS,
                "email_password": EMAIL_PASSWORD
            }
            
            # Send the approved email
            with st.spinner("Sending email..."):
                sent = st.session_state.analyzer.send_custom_email(
                    email_data=st.session_state.email_draft,
                    recipient_email=recipient_email,
                    email_config=email_config
                )
                
                if sent:
                    st.success(f"✅ Email successfully sent to {recipient_email}")
                    st.session_state.email_sent_final = True
                    st.session_state.show_send_options = False
                else:
                    st.error("Failed to send email. Please check settings and try again.")

    # Display feedback history if available
    if st.session_state.feedback_provided:
        with st.expander("Previous Feedback"):
            st.info(st.session_state.feedback_provided)

    # Final success message if email was sent
    if st.session_state.email_sent_final:
        st.success("✅ Follow-up process completed successfully!")

# Create the Streamlit UI
st.title("🔍 Client Transcript Follow-up Analyzer")

# Sidebar configuration
st.sidebar.header("About")
st.sidebar.info(
    "This application analyzes client transcripts to identify "
    "necessary follow-up actions and allows you to draft, review, "
    "and send personalized follow-up emails."
)

# Tab selection based on session state
tab_options = ["Upload & Analyze", "Results", "Email Draft"]
tab1, tab2, tab3 = st.tabs(tab_options)

# Initialize variables
uploaded_file = None
transcript_text = ""

with tab1:
    st.header("Upload Client Transcript")
    
    # Input method selection
    input_method = st.radio(
        "Choose input method:",
        options=["Upload File", "Paste Text"],
        horizontal=True,
        key="input_method"
    )
    
    # Show relevant input method based on selection
    if input_method == "Upload File":
        uploaded_file = st.file_uploader(
            "Upload a transcript file (txt)", 
            type=["txt"],
            help="Upload a text file containing the client transcript",
            key="file_uploader"
        )
        if uploaded_file is not None:
            st.success("File uploaded successfully!")
            # Preview the uploaded content
            with st.expander("Preview uploaded content"):
                stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
                transcript_text = stringio.read()
                st.text(transcript_text)
    else:
        transcript_text = st.text_area(
            "Paste transcript content here:", 
            height=300,
            placeholder="Client: Hello, I'm calling about...\nAgent: How can I help you today?",
            key="text_input"
        )
    
    # Email notification section
    if email_configured:
        st.markdown("### Email Notification")
        send_auto_email = st.checkbox(
            "Send automated email notification for follow-ups", 
            value=False,
            help="This will send an automated notification. You can also craft a custom email in the Email Draft tab.",
            key="send_auto_email"
        )
        
        if send_auto_email:
            recipient_email = st.text_input(
                "Recipient email address:", 
                value=DEFAULT_RECIPIENT,
                key="recipient_email"
            )
    else:
        send_auto_email = False
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
    if input_method == "Upload File" and uploaded_file is not None:
        final_transcript = transcript_text
    elif input_method == "Paste Text" and transcript_text:
        final_transcript = transcript_text
    
    if not final_transcript.strip():
        st.error("Please provide a transcript to analyze")
    else:
        with st.spinner("Analyzing transcript..."):
            results, transcript_id, analyzer = process_transcript(final_transcript)
            
            if results and results.get("status") == "success":
                # Switch to results tab automatically
                st.session_state.current_tab = "Results"
                
                # Send automated email if requested
                if send_auto_email and email_configured and results.get("total_follow_ups", 0) > 0:
                    with st.spinner("Sending automated email notification..."):
                        email_success = analyzer.send_email_alert(
                            transcript_id, 
                            recipient_email, 
                            results
                        )
                        st.session_state.email_sent = email_success
                
                # Reset email draft when analyzing a new transcript
                st.session_state.email_draft = None
                st.session_state.show_feedback = False
                st.session_state.show_send_options = False
                st.session_state.feedback_provided = ""
                st.session_state.email_sent_final = False
                
                # Auto-refresh to show results in the correct tab
                st.rerun()

# Display results in the Results tab
with tab2:
    if st.session_state.analysis_results:
        results = st.session_state.analysis_results
        
        if results.get("status") == "success":
            st.header("📊 Analysis Results")
            
            # Email notification status for automated emails
            if st.session_state.email_sent:
                st.success(f"✅ Automated follow-up email sent to {recipient_email}")
            
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
                
                # Button to go to email draft tab
                if st.button("Draft Custom Follow-up Email", key="go_to_email_draft"):
                    st.session_state.current_tab = "Email Draft"
                    st.rerun()
            else:
                st.success("No follow-up actions required!")
        else:
            st.error(f"Analysis failed: {results.get('message', 'Unknown error')}")
    else:
        st.info("Upload and analyze a transcript to see results here.")

# Email Draft tab
with tab3:
    if st.session_state.analysis_results and st.session_state.analysis_results.get("status") == "success":
        # Display the email workflow
        display_email_workflow(
            st.session_state.analysis_results,
            st.session_state.transcript_id
        )
    else:
        st.info("Please analyze a transcript first to generate an email draft.")
        if st.button("Go to Upload & Analyze", key="go_to_upload"):
            st.session_state.current_tab = "Upload & Analyze"
            st.experimental_rerun()

# Ensure we're on the correct tab based on session state
if st.session_state.current_tab == "Results":
    # This is a hack to programmatically click the Results tab
    js = f"""
    <script>
        var tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
        tabs[1].click();
    </script>
    """
    st.components.v1.html(js, height=0)
elif st.session_state.current_tab == "Email Draft":
    # This is a hack to programmatically click the Email Draft tab
    js = f"""
    <script>
        var tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
        tabs[2].click();
    </script>
    """
    st.components.v1.html(js, height=0)

# Footer
st.markdown("---")
st.markdown("© 2025 Client Transcript Follow-up Analyzer")