import streamlit as st
import cv2
import numpy as np
import os
from PIL import Image
import io

def take_photo():
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
        
        return image
    else:
        st.info("사진을 찍으려면 카메라 버튼을 클릭하세요.")
        return None
