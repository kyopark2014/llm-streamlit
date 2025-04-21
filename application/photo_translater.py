import streamlit as st
import cv2
import numpy as np
import os
from PIL import Image
import io
import chat
import utils
from io import BytesIO
import base64

# logging
logger = utils.CreateLogger("streamlit")

def take_photo(st):
    """
    카메라 UI를 이용해 사진을 찍고 photo.jpg로 저장하는 함수
    """
    st.title("📸 카메라로 사진 찍기")
    
    # 카메라 입력 위젯
    camera_input = st.camera_input("사진을 찍어주세요")
    
    if camera_input is not None:
        # 이미지를 바이트에서 PIL 이미지로 변환
        image = Image.open(camera_input)
        
        # 이미지를 화면에 표시
        st.image(image, caption="찍은 사진", use_column_width=True)
        
        # 이미지를 photo.jpg로 저장
        image.save("photo.jpg")
        st.success("사진이 성공적으로 저장되었습니다! (photo.jpg)")
        
        # 저장된 이미지 정보 표시
        st.info(f"저장된 이미지 크기: {image.size}")
        
        # 번역을 위한 입력 필드
        text_prompt = st.text_input("이미지에서 번역할 내용에 대한 설명을 입력하세요:", "이 이미지에 있는 텍스트를 한국어로 번역해주세요.")
        
        if st.button("번역하기"):
            with st.status("번역 중...", expanded=True, state="running") as status:
                # 이미지 파일명 가져오기
                file_name = "photo.jpg"
                
                # 이미지 분석 및 번역 수행
                translation = chat.get_image_summarization(file_name, text_prompt, st)
                st.write(translation)
                
                # 메시지 히스토리에 추가
                if "messages" in st.session_state:
                    st.session_state.messages.append({"role": "assistant", "content": translation})
        
        return image
    else:
        st.info("사진을 찍으려면 카메라 버튼을 클릭하세요.")
        return None

def load_text_from_image(img, st):
    width, height = img.size 
    logger.info(f"width: {width}, height: {height}, size: {width*height}")
    
    isResized = False
    while(width*height > 5242880):                    
        width = int(width/2)
        height = int(height/2)
        isResized = True
        logger.info(f"width: {width}, height: {height}, size: {width*height}")
    
    if isResized:
        img = img.resize((width, height))
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # extract text from the image
    status = "이미지에서 텍스트를 추출합니다."
    logger.info(f"status: {status}")
    st.info(status)

    text = chat.extract_text(img_base64)
    logger.info(f"extracted text: {text}")

    if text.find('<result>') != -1:
        extracted_text = text[text.find('<result>')+8:text.find('</result>')] # remove <result> tag
        # print('extracted_text: ', extracted_text)
    else:
        extracted_text = text
    
    status = f"### 추출된 텍스트\n\n{extracted_text}"
    logger.info(f"status: {status}")
    st.info(status)
    
    return extracted_text
