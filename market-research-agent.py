import streamlit as st
from graph import build_market_research_graph
from langchain_core.messages import HumanMessage, AIMessage

# Configure the Streamlit page
st.set_page_config(
    page_title="Company Research Assistant",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS for chat bubbles and layout
st.markdown("""
<style>
.chat-container {
    margin-bottom: 20px;
}
.user-message {
    background-color: #e6f3ff;
    padding: 10px 15px;
    border-radius: 15px;
    margin: 5px 0;
    max-width: 70%;
    margin-left: auto;
}
.assistant-message {
    background-color: #f0f0f0;
    padding: 10px 15px;
    border-radius: 15px;
    margin: 5px 0;
    max-width: 70%;
}
.markdown-text-container {
    max-width: 100% !important;
}
.stMarkdown {
    max-width: 100% !important;
}
.research-status {
    margin: 20px 0;
    padding: 10px;
    border-radius: 5px;
    background-color: #f9f9f9;
    border-left: 5px solid #4CAF50;
}
.status-pending {
    color: #FFA500;
}
.status-completed {
    color: #4CAF50;
}
</style>
""", unsafe_allow_html=True)

# Title and description
st.title("📊 Company Research Assistant")
st.subheader("Specialized in Revenue History and GenAI Competitive Analysis")

# Initialize the market research graph
if "graph" not in st.session_state:
    st.session_state.graph = build_market_research_graph()

# Initialize session state for conversation history and research status
if "messages" not in st.session_state:
    st.session_state.messages = []

if "research_status" not in st.session_state:
    st.session_state.research_status = None

if "company_name" not in st.session_state:
    st.session_state.company_name = None

if "research_in_progress" not in st.session_state:
    st.session_state.research_in_progress = False

if "last_user_input" not in st.session_state:
    st.session_state.last_user_input = ""

# New state variable to track processed messages
if "processed_events" not in st.session_state:
    st.session_state.processed_events = set()

# Create a container for the chat history
chat_container = st.container()

# Display status of research if company name is provided
if st.session_state.research_status and st.session_state.company_name:
    status_html = f"""<div class="research-status">
        <h3>Research Status for {st.session_state.company_name}</h3>
        <ul>
    """
    
    for task, status in st.session_state.research_status.items():
        task_name = task.replace("_", " ").title()
        status_class = "status-completed" if status == "completed" else "status-pending"
        status_html += f'<li>{task_name}: <span class="{status_class}">{status.title()}</span></li>'
    
    status_html += "</ul></div>"
    st.markdown(status_html, unsafe_allow_html=True)

# Create a form for user input
with st.form(key="chat_form", clear_on_submit=True):
    # Create a horizontal layout for input and button
    cols = st.columns([4, 1])
    
    # Add input field and submit button
    user_input = cols[0].text_input(
        "Company name or research query:",
        key="user_input",
        placeholder="Example: Research Microsoft's revenue and competitors' GenAI use cases"
    )
    submit_button = cols[1].form_submit_button("Research")

# Helper function to process graph events
def process_graph_events(events, is_new_query=False):
    research_complete = False
    progress_made = False
    
    for event in events:
        # Generate a unique identifier for this event
        event_id = None
        if "messages" in event and event["messages"]:
            latest_message = event["messages"][-1]
            if isinstance(latest_message, AIMessage):
                event_id = hash(latest_message.content)
        
        # Skip already processed events
        if event_id and event_id in st.session_state.processed_events:
            continue
            
        # Update company name if available
        if "company_name" in event and event["company_name"]:
            st.session_state.company_name = event["company_name"]
        
        # Update research status if available
        if "status" in event and event["status"]:
            st.session_state.research_status = event["status"]
            
            # Check if all tasks are completed
            if all(v == "completed" for v in event["status"].values()):
                research_complete = True
        
        # Add AI messages to chat history
        if "messages" in event and event["messages"]:
            latest_message = event["messages"][-1]
            if isinstance(latest_message, AIMessage):
                # Add AI response to chat history (avoid duplicates)
                if event_id:
                    st.session_state.processed_events.add(event_id)
                    st.session_state.messages.append({"role": "assistant", "content": latest_message.content})
                    progress_made = True
    
    return research_complete, progress_made

# Handle research continuation when in progress
if st.session_state.research_in_progress:
    with st.spinner("Continuing research..."):
        try:
            # Process events from the graph stream
            events = st.session_state.graph.stream(
                {},  # No new input, continue from where we left off
                {"configurable": {"thread_id": "1"}},
                stream_mode="values"
            )
            
            # Process events and check for completion
            research_complete, progress_made = process_graph_events(events)
            
            # Update research status flag
            if research_complete:
                st.session_state.research_in_progress = False
                
            # Only trigger rerun if we made progress
            if progress_made:
                st.rerun()
                
        except Exception as e:
            st.error(f"Error during research: {str(e)}")
            st.session_state.research_in_progress = False

# Handle form submission for new research
if submit_button and user_input.strip():
    # Reset processed events for new query
    st.session_state.processed_events = set()
    
    # Store the user input
    st.session_state.last_user_input = user_input
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Reset research status
    st.session_state.research_status = None
    st.session_state.company_name = None
    
    # Set research in progress flag
    st.session_state.research_in_progress = True
    
    # Process with the market research graph
    with st.spinner("Starting research... This may take a few moments"):
        try:
            events = st.session_state.graph.stream(
                {"messages": [HumanMessage(content=user_input)]},
                {"configurable": {"thread_id": "1"}},
                stream_mode="values"
            )
            
            # Process events and check for completion
            research_complete, _ = process_graph_events(events, is_new_query=True)
            
            # Update research status flag
            if research_complete:
                st.session_state.research_in_progress = False
                
            # Always rerun after starting new research
            st.rerun()
            
        except Exception as e:
            st.error(f"Error during research: {str(e)}")
            st.session_state.research_in_progress = False

# Display chat history
with chat_container:
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"""
            <div class="chat-container">
                <div class="user-message">
                    {message["content"]}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-container">
                <div class="assistant-message">
                    {message["content"]}
                </div>
            </div>
            """, unsafe_allow_html=True)

# Add a "Continue Research" button to manually trigger continuation if needed
if st.session_state.research_in_progress:
    if st.button("Continue Research"):
        st.rerun()

# Add usage instructions in the sidebar
with st.sidebar:
    st.header("How to Use")
    st.markdown("""
    1. Enter a company name or a research query
    2. The assistant will research:
       - Revenue history (past 3 years)
       - Major sources of revenue
       - Competitors' GenAI use cases and benefits
    3. Wait for the comprehensive report
    
    **Example queries:**
    - "Research Microsoft's revenue and competitors"
    - "Tell me about Apple's revenue and GenAI competition"
    - "I need information about Tesla's financials and competitors' AI"
    """)
    
    st.header("About")
    st.markdown("""
    This research assistant uses a multi-agent architecture with specialized agents:
    
    - **Revenue History Agent**: Analyzes financial data
    - **Revenue Sources Agent**: Identifies business models and revenue streams
    - **Competitor GenAI Agent**: Researches AI implementations and benefits
    
    The orchestrator coordinates these agents to provide comprehensive research.
    """)