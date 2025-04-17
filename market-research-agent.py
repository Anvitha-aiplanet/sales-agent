import streamlit as st
from graph import stream_graph_updates
# Configure the Streamlit page
st.set_page_config(
    page_title="Chat Assistant",
    page_icon="💬",
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
</style>
""", unsafe_allow_html=True)

# Initialize session state for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display the chat title
st.title("💬 Chat Assistant")

# Function to simulate AI response (replace with your actual AI backend)
def get_ai_response(user_input):
    return f"I received your message: '{user_input}'. This is a simulated response."

# Create a container for the chat history
chat_container = st.container()

# Create a form for user input
with st.form(key="chat_form", clear_on_submit=True):
    # Create a horizontal layout for input and button
    cols = st.columns([4, 1])
    
    # Add input field and submit button
    user_input = cols[0].text_input(
        "Your message:",
        key="user_input",
        label_visibility="collapsed"
    )
    submit_button = cols[1].form_submit_button("Send")

# Handle form submission
if submit_button and user_input.strip():
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Get AI response
    ai_response = stream_graph_updates(user_input)
    
    # Add AI response to chat history
    st.session_state.messages.append({"role": "assistant", "content": ai_response})

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

# Automatically scroll to the bottom of the chat
if st.session_state.messages:
    st.markdown("""
        <script>
            var element = document.getElementsByClassName('main')[0];
            element.scrollTop = element.scrollHeight;
        </script>
        """, unsafe_allow_html=True)
