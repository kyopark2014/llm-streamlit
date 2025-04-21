from PIL import Image
import chat
import utils
from io import BytesIO
import base64

# logging
logger = utils.CreateLogger("streamlit")

def take_photo(st):
    st.title("📸 카메라로 사진 찍기")
    
    # 카메라 입력 위젯
    camera_input = st.camera_input("사진을 찍어주세요")
    
    if camera_input is not None:
        image = Image.open(camera_input)        
        st.image(image, caption="찍은 사진")
         
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
