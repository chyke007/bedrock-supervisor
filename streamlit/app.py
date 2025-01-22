import streamlit as st
import agent as agenthelper
import uuid
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Streamlit page configuration
st.set_page_config(page_title="Steakhouse Agent", page_icon=":robot_face:", layout="wide")

# Custom CSS for styling
st.markdown(
    """
    <style>
    .main-header {
        text-align: center;
        font-size: 1.8em;
        color: #2E4053;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .conversation-box {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
    }
    .conversation-box h5 {
        margin: 0;
        font-weight: bold;
    }
    .conversation-box p {
        margin: 5px 0 0 0;
        font-size: 0.9em;
        color: #34495E;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Main header
st.markdown("<div class='main-header'>Welcome to Steakhouse Agent</div>", unsafe_allow_html=True)

# Agent message
st.write("I am an AI Agent that can help you make reservations, retrieve reservations, and cancel reservations. You can also ask me about menu details, special deals, desserts & drinks.")

# Display a text box for input
prompt = st.text_area("**How may I help you?**", value="", height=70, key="prompt")
prompt = prompt.strip()

# Generate unique session ID if not already present
if 'session_id' not in st.session_state:
    st.session_state['session_id'] = str(uuid.uuid4())

# Session State Management
if 'history' not in st.session_state:
    st.session_state['history'] = []

if 'session_ended' not in st.session_state:
    st.session_state['session_ended'] = False

# Primary buttons
col1, col2 = st.columns(2)
with col1:
    submit_button = st.button("Submit")
with col2:
    end_button = st.button("End Session", type="primary")

st.divider()

# Handling the "End Session" button
if end_button:
    st.session_state['history'].append({"question": "Session Ended", "answer": "Thank you for using Steakhouse Support Agent!"})
    event = {
        "sessionId": st.session_state['session_id'],
        "question": "placeholder to end session",
        "endSession": True
    }
    agenthelper.agent_handler(event, None)
    st.session_state['session_id'] = None  # Clear session ID
    st.session_state['session_ended'] = True  # Mark the session as ended

# Handling user input and responses
if submit_button and prompt:
    # Clear history if session was ended previously
    if st.session_state['session_ended']:
        st.session_state['history'] = []
        st.session_state['session_ended'] = False  # Reset session ended flag
    
    # Process the new prompt
    event = {
        "sessionId": st.session_state['session_id'],
        "question": prompt
    }
    response = agenthelper.agent_handler(event, None)
    logging.info(f"Response from app.py: {response}")

    try:
        if response and 'response' in response and response['response']:
            response_data = response['response']
        else:
            response_data = None
    except Exception as e:
        logging.error(f"Error processing response: {e}")
        response_data = None

    st.session_state['history'].append({"question": prompt, "answer": response_data or "..."})

# Display conversation history
st.write("## Conversation History")
if st.session_state["history"]:
    for chat in reversed(st.session_state['history']):
        with st.chat_message(
            name="human",
            avatar="https://api.dicebear.com/7.x/notionists-neutral/svg?seed=Felix",
        ):
            st.markdown(chat['question'])

        with st.chat_message(
            name="ai",
            avatar="https://assets-global.website-files.com/62b1b25a5edaf66f5056b068/62d1345ba688202d5bfa6776_aws-sagemaker-eyecatch-e1614129391121.png",
        ):
            st.markdown(chat['answer'])
