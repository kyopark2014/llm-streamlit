import streamlit as st 
import boto3
from datetime import datetime
import uuid
import os
import re
import chat

# Add file uploader to sidebar
st.sidebar.subheader("Upload Image")
uploaded_file = st.sidebar.file_uploader("Choose an image", type=["png", "jpg", "jpeg"])

option = st.sidebar.selectbox('Please select in selectbox!',('일상적인 대화', 'Agentic Workflow (Tool Use)', '번역하기', '문법 검토하기'))
st.sidebar.write('Selected application:', option)

# Preview the uploaded image in the sidebar
if uploaded_file is not None:
    st.image(uploaded_file, caption="Preview of uploaded image", use_column_width=True)
    if st.button("Clear Image"):
        uploaded_file = None
        st.rerun()

clear_button = st.sidebar.button("Clear Conversation", key="clear")

st.title(option)

if clear_button or "messages" not in st.session_state:
    st.session_state.messages = []
    chat.clear_chat_history()

st.sidebar.markdown(
    "This app shows an Agentic Chatbot powered by Amazon Bedrock to answer questions."
)
    
# Always show the chat input
if user_input := st.chat_input("메시지를 입력하세요."):
    if uploaded_file is not None:
        # Upload the file to S3
        image_url = chat.upload_to_s3(uploaded_file.getvalue(), uploaded_file.name)
        print('image_url: ', image_url)

    with st.chat_message("user"):
        st.markdown(user_input)

#st.header('this is header')
#st.subheader('this is subheader')
    if option == '일상적인 대화':
        msg = chat.general_conversation(user_input)
    elif option == 'Agentic Workflow (Tool Use)':
        msg = chat.run_agent_executor2(user_input)
    elif option == '번역하기':
        msg = chat.translate_text(user_input)
    elif option == 'Grammer':
        msg = chat.check_grammer(user_input)
    else:
        msg = chat.general_conversation(user_input)
    print('msg: ', msg)

    with st.chat_message("assistant"):
        st.write(msg)

    chat.save_chat_history(user_input, msg)


