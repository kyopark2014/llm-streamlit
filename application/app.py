import streamlit as st 
import chat
import json
import logging
import sys
import time

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# formatter = logging.Formatter('%(asctime)s | %(filename)s:%(lineno)d | %(message)s')
formatter = logging.Formatter('%(message)s')

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
stdout_handler.setFormatter(formatter)

enableLoggerApp = chat.get_logger_state()
print('enableLoggerApp: ', enableLoggerApp)

if not enableLoggerApp:
    logger.addHandler(stdout_handler)
    try:
        with open("/home/config.json", "r", encoding="utf-8") as f:
            file_handler = logging.FileHandler('/var/log/application/logs.log')
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            logger.info("Ready to write log (app)!")
    except Exception:
        logger.debug(f"Not available to write application log (app)")

st.set_page_config(page_title='AWS', page_icon=None, layout="centered", initial_sidebar_state="auto", menu_items=None)

mode_descriptions = {
    "일상적인 대화": [
        "대화이력을 바탕으로 챗봇과 일상의 대화를 편안히 즐길수 있습니다."
    ],
    "Agentic Workflow (Tool Use)": [
        "Agent를 이용해 다양한 툴을 사용할 수 있습니다. 여기에서는 날씨, 시간, 도서추천, 인터넷 검색을 제공합니다."
    ],
    "Agentic Workflow Chat": [
        "Agent를 이용해 다양한 툴을 사용할 수 있습니다. 또한, 이전 채팅 히스토리를 반영한 대화가 가능합니다."
    ],
    "번역하기 (한국어 / 영어)": [
        "한국어와 영어에 대한 번역을 제공합니다. 한국어로 입력하면 영어로, 영어로 입력하면 한국어로 번역합니다."        
    ],
    "번역하기 (일본어 / 한국어)": [
        "일본어를 한국어로 번역합니다."        
    ],
    "문법 검토하기": [
        "영어와 한국어 문법의 문제점을 설명하고, 수정된 결과를 함께 제공합니다."
    ],
    "이미지 분석": [
        "이미지를 업로드하면 이미지의 내용을 요약할 수 있습니다."
    ]
}

with st.sidebar:
    st.title("🔮 Menu")
    
    st.markdown(
        "Amazon Bedrock을 이용해 다양한 형태의 대화를 구현합니다." 
        "여기에서는 일상적인 대화와 각종 툴을 이용해 Agent를 구현할 수 있습니다." 
        "또한 번역이나 문법 확인과 같은 용도로 사용할 수 있습니다."
        "주요 코드는 LangChain과 LangGraph를 이용해 구현되었습니다.\n"
        "상세한 코드는 [Github](https://github.com/kyopark2014/llm-streamlit)을 참조하세요."
    )

    st.subheader("🐱 대화 형태")
    
    # radio selection
    mode = st.radio(
        label="원하는 대화 형태를 선택하세요. ",options=["일상적인 대화", "Agentic Workflow (Tool Use)", "Agentic Workflow Chat", "번역하기 (한국어 / 영어)", "번역하기 (일본어 / 한국어)", "문법 검토하기", "이미지 분석"], index=0
    )   
    st.info(mode_descriptions[mode][0])
    # limit = st.slider(
    #     label="Number of cards",
    #     min_value=1,
    #     max_value=mode_descriptions[mode][2],
    #     value=6,
    # )

    # model selection box
    if mode == '이미지 분석':
        index = 3
    else:
        index = 0   
    modelName = st.selectbox(
        '🖊️ 사용 모델을 선택하세요',
        ('Nova Pro', 'Nova Lite', 'Nova Micro', 'Claude 3.5 Sonnet', 'Claude 3.0 Sonnet', 'Claude 3.5 Haiku'), index=index
    )
    
    uploaded_file = None
    if mode == '이미지 분석':
        st.subheader("🌇 이미지 업로드")
        uploaded_file = st.file_uploader("이미지 요약을 위한 파일을 선택합니다.", type=["png", "jpg", "jpeg"])

    # debug checkbox
    select_debugMode = st.checkbox('Debug Mode', value=True)
    debugMode = 'Enable' if select_debugMode else 'Disable'
    # print('debugMode: ', debugMode)

    # multi region check box
    select_multiRegion = st.checkbox('Multi Region', value=False)
    multiRegion = 'Enable' if select_multiRegion else 'Disable'
    #print('multiRegion: ', multiRegion)
   
    chat.update(modelName, debugMode, multiRegion)

    st.success(f"Connected to {modelName}", icon="💚")
    clear_button = st.button("대화 초기화", key="clear")
    # print('clear_button: ', clear_button)

st.title('🔮 '+ mode)

if clear_button==True:
    chat.initiate()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.greetings = False

# Display chat messages from history on app rerun
def display_chat_messages() -> None:
    """Print message history
    @returns None
    """
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

display_chat_messages()

def show_references(reference_docs):
    if debugMode == "Enable" and reference_docs:
        with st.expander(f"답변에서 참조한 {len(reference_docs)}개의 문서입니다."):
            for i, doc in enumerate(reference_docs):
                st.markdown(f"**{doc.metadata['name']}**: {doc.page_content}")
                st.markdown("---")

# Greet user
if not st.session_state.greetings:
    with st.chat_message("assistant"):
        intro = "아마존 베드락을 이용하여 주셔서 감사합니다. 편안한 대화를 즐기실수 있으며, 파일을 업로드하면 요약을 할 수 있습니다."
        st.markdown(intro)
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": intro})
        st.session_state.greetings = True

if clear_button or "messages" not in st.session_state:
    st.session_state.messages = []        
    uploaded_file = None
    
    st.session_state.greetings = False
    #st.rerun()

    chat.clear_chat_history()

# Preview the uploaded image in the sidebar
file_name = ""
if uploaded_file and clear_button==False and mode == '이미지 분석':
    st.image(uploaded_file, caption="이미지 미리보기", use_container_width=True)

    file_name = uploaded_file.name
    image_url = chat.upload_to_s3(uploaded_file.getvalue(), file_name)
    print('image_url: ', image_url)    
            
# Always show the chat input
if prompt := st.chat_input("메시지를 입력하세요."):
    logger.info(f"prompt: {prompt}")
    with st.chat_message("user"):  # display user message in chat message container
        st.markdown(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})  # add user message to chat history
    prompt = prompt.replace('"', "").replace("'", "")
    
    with st.chat_message("assistant"):
        
        if mode == '일상적인 대화':
            # with st.status("thinking...", expanded=True, state="running") as status:
            #     stream = chat.general_conversation(prompt)            
            #     response = st.write_stream(stream)
            #     print('response: ', response)
            #     st.session_state.messages.append({"role": "assistant", "content": response})
            #     st.rerun()                

            stream = chat.general_conversation(prompt)            
            response = st.write_stream(stream)            
            logger.info(f"response: {response}")
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            # st.rerun()

        elif mode == 'Agentic Workflow (Tool Use)':
            with st.status("thinking...", expanded=True, state="running") as status:
                response, reference_docs = chat.run_agent_executor(prompt, st)
                # response = chat.run_agent_executor2(prompt st, debugMode, modelName)
                st.write(response)
                print('response: ', response)

                st.session_state.messages.append({"role": "assistant", "content": response})
                if debugMode != "Enable":
                    st.rerun()
            
            show_references(reference_docs) 

        elif mode == 'Agentic Workflow Chat':
            with st.status("thinking...", expanded=True, state="running") as status:
                revise_prompt = chat.revise_question(prompt, st)
                response, reference_docs = chat.run_agent_executor(revise_prompt, st)
                st.write(response)
                print('response: ', response)
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                if debugMode != "Enable":
                    st.rerun()

                chat.save_chat_history(prompt, response)
            
            show_references(reference_docs) 
        elif mode == '번역하기 (한국어 / 영어)':
            response = chat.translate_text(prompt, modelName)
            st.write(response)

            st.session_state.messages.append({"role": "assistant", "content": response})
            # chat.save_chat_history(prompt, response)
        
        elif mode == '번역하기 (일본어 / 한국어)':
            response = chat.translate_text_for_japanese(prompt, modelName)
            st.write(response)

            st.session_state.messages.append({"role": "assistant", "content": response})
            # chat.save_chat_history(prompt, response)

        elif mode == '문법 검토하기':
            response = chat.check_grammer(prompt, modelName)
            st.write(response)

            st.session_state.messages.append({"role": "assistant", "content": response})
            # chat.save_chat_history(prompt, response)
        elif mode == '이미지 분석':
            if uploaded_file is None or uploaded_file == "":
                st.error("파일을 먼저 업로드하세요.")
                st.stop()

            else:                
                with st.status("thinking...", expanded=True, state="running") as status:
                    summary = chat.get_image_summarization(file_name, prompt, st)
                    st.write(summary)

                    st.session_state.messages.append({"role": "assistant", "content": summary})
                    if debugMode != "Enable":
                        st.rerun()
        else:
            stream = chat.general_conversation(prompt)

            response = st.write_stream(stream)
            print('response: ', response)

            st.session_state.messages.append({"role": "assistant", "content": response})
            chat.save_chat_history(prompt, response)
        
        
