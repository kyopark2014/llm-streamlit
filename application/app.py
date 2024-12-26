import streamlit as st 
import boto3
from datetime import datetime
import uuid
import os
import re
import chat

from io import BytesIO
from PIL import Image

def upload_to_s3(file_bytes, file_name):
    """
    Upload a file to S3 and return the URL
    """
    try:
        s3_client = boto3.client("s3")
        bucket_name = os.getenv("S3_BUCKET_NAME")

        # Generate a unique file name to avoid collisions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        s3_key = f"uploaded_images/{timestamp}_{unique_id}_{file_name}"

        content_type = (
            "image/jpeg"
            if file_name.lower().endswith((".jpg", ".jpeg"))
            else "image/png"
        )

        s3_client.put_object(
            Bucket=bucket_name, Key=s3_key, Body=file_bytes, ContentType=content_type
        )

        url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        return url
    except Exception as e:
        st.error(f"Error uploading to S3: {str(e)}")
        return None

def extract_and_display_s3_images(text, s3_client):
    """
    Extract S3 URLs from text, download images, and return them for display
    """
    s3_pattern = r"https://[\w\-\.]+\.s3\.amazonaws\.com/[\w\-\./]+"
    s3_urls = re.findall(s3_pattern, text)

    images = []
    for url in s3_urls:
        try:
            bucket = url.split(".s3.amazonaws.com/")[0].split("//")[1]
            key = url.split(".s3.amazonaws.com/")[1]

            response = s3_client.get_object(Bucket=bucket, Key=key)
            image_data = response["Body"].read()

            image = Image.open(BytesIO(image_data))
            images.append(image)

        except Exception as e:
            st.error(f"Error downloading image from S3: {str(e)}")
            continue

    return images

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

st.sidebar.markdown(
    "This app shows an Agentic Chatbot powered by Amazon Bedrock to answer questions."
)
    
# Always show the chat input
if user_input := st.chat_input("메시지를 입력하세요."):
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


