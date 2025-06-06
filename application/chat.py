import traceback
import boto3
import os
import json
import re
import requests
import datetime
import functools
import base64
import uuid
import info
import yfinance as yf
import utils

from io import BytesIO
from PIL import Image
from pytz import timezone
from langchain_aws import ChatBedrock
from botocore.config import Config
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.tools import tool
from langchain.docstore.document import Document
from tavily import TavilyClient  
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import START, END, StateGraph
from typing import Literal
from typing_extensions import Annotated, TypedDict
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.output_parsers import StrOutputParser
from urllib import parse

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langchain_experimental.tools import PythonAstREPLTool

logger = utils.CreateLogger("chat")

userId = uuid.uuid4().hex
logger.info(f"userId: {userId}")
map_chain = dict() # general conversation

checkpointers = dict() 
memorystores = dict() 

checkpointer = MemorySaver()
memorystore = InMemoryStore()

checkpointers[userId] = checkpointer
memorystores[userId] = memorystore

def initiate():
    global userId
    global map_chain, memory_chain, checkpointers, memorystores, checkpointer, memorystore

    userId = uuid.uuid4().hex
    logger.info(f"userId: {userId}")

    if userId in map_chain:  
        # print('memory exist. reuse it!')
        memory_chain = map_chain[userId]

        checkpointer = checkpointers[userId]
        memorystore = memorystores[userId]
    else: 
        # print('memory does not exist. create new one!')        
        memory_chain = ConversationBufferWindowMemory(memory_key="chat_history", output_key='answer', return_messages=True, k=5)
        map_chain[userId] = memory_chain

        checkpointer = MemorySaver()
        memorystore = InMemoryStore()

        checkpointers[userId] = checkpointer
        memorystores[userId] = memorystore
        
initiate()
 
config = utils.load_config()
        
bedrock_region = "us-west-2"
projectName = config["projectName"] if "projectName" in config else "bedrock-agent"

accountId = config["accountId"] if "accountId" in config else None
if accountId is None:
    raise Exception ("No accountId")

region = config["region"] if "region" in config else "us-west-2"
logger.info(f"region: {region}")

s3_prefix = 'docs'
s3_image_prefix = 'images'

path = config["sharing_url"] if "sharing_url" in config else None
if path is None:
    raise Exception ("No Sharing URL")

s3_bucket = config["s3_bucket"] if "s3_bucket" in config else None
if s3_bucket is None:
    raise Exception ("No storage!")

MSG_LENGTH = 100

model_name = "Nova Pro"
model_type = "nova"
multi_region = 'Enable'
contextual_embedding = "Disable"
debug_mode = "Enable"

models = info.get_model_info(model_name)
number_of_models = len(models)
selected_chat = 0

reasoning_mode = 'Disable'
def update(modelName, debugMode, multiRegion, reasoningMode):    
    global model_name, debug_mode, multi_region
    global selected_chat, models, number_of_models, reasoning_mode
    
    if model_name != modelName:
        model_name = modelName
        logger.info(f"model_name: {model_name}")

        selected_chat = 0
        models = info.get_model_info(model_name)
        number_of_models = len(models)
                
    if debug_mode != debugMode:
        debug_mode = debugMode
        logger.info(f"debug_mode: {debug_mode}")

    if multi_region != multiRegion:
        multi_region = multiRegion
        logger.info(f"multi_region: {multi_region}")

        selected_chat = 0
    
    reasoning_mode = "Enable" if reasoningMode=="Enable" else "Disable"
    logger.info(f"reasoning_mode: {reasoning_mode}")

def clear_chat_history():
    memory_chain = []
    map_chain[userId] = memory_chain

def save_chat_history(text, msg):
    memory_chain.chat_memory.add_user_message(text)
    if len(msg) > MSG_LENGTH:
        memory_chain.chat_memory.add_ai_message(msg[:MSG_LENGTH])                          
    else:
        memory_chain.chat_memory.add_ai_message(msg) 

def get_chat(extended_thinking):
    global selected_chat, model_type

    profile = models[selected_chat]
    # print('profile: ', profile)
        
    bedrock_region =  profile['bedrock_region']
    modelId = profile['model_id']
    model_type = profile['model_type']
    if model_type == 'claude':
        maxOutputTokens = 4096 # 4k
    else:
        maxOutputTokens = 5120 # 5k
    logger.info(f'LLM: {selected_chat}, bedrock_region: {bedrock_region}, modelId: {modelId}, model_type: {model_type}')

    if profile['model_type'] == 'nova':
        STOP_SEQUENCE = '"\n\n<thinking>", "\n<thinking>", " <thinking>"'
    elif profile['model_type'] == 'claude':
        STOP_SEQUENCE = "\n\nHuman:" 
                          
    # bedrock   
    boto3_bedrock = boto3.client(
        service_name='bedrock-runtime',
        region_name=bedrock_region,
        config=Config(
            retries = {
                'max_attempts': 30,
                'mode': 'adaptive'
            }
        )
    )
    if extended_thinking=='Enable':
        maxReasoningOutputTokens=64000
        logger.info(f"extended_thinking: {extended_thinking}")
        thinking_budget = min(maxOutputTokens, maxReasoningOutputTokens-1000)

        parameters = {
            "max_tokens":maxReasoningOutputTokens,
            "temperature":1,            
            "thinking": {
                "type": "enabled",
                "budget_tokens": thinking_budget
            },
            "stop_sequences": [STOP_SEQUENCE],
            "anthropic_beta": ["token-efficient-tools-2025-02-19"]
        }
    else:
        parameters = {
            "max_tokens":maxOutputTokens,     
            "temperature":0.1,
            "top_k":250,
            "top_p":0.9,
            "stop_sequences": [STOP_SEQUENCE],
            "anthropic_beta": ["token-efficient-tools-2025-02-19"]
        }

    chat = ChatBedrock(   # new chat model
        model_id=modelId,
        client=boto3_bedrock, 
        model_kwargs=parameters,
        region_name=bedrock_region
    )    
    
    if multi_region=='Enable':
        selected_chat = selected_chat + 1
        if selected_chat == number_of_models:
            selected_chat = 0
    else:
        selected_chat = 0

    return chat

reference_docs = []
# api key to get weather information in agent
secretsmanager = boto3.client(
    service_name='secretsmanager',
    region_name=bedrock_region
)
try:
    get_weather_api_secret = secretsmanager.get_secret_value(
        SecretId=f"openweathermap-{projectName}"
    )
    #print('get_weather_api_secret: ', get_weather_api_secret)
    secret = json.loads(get_weather_api_secret['SecretString'])
    #print('secret: ', secret)
    weather_api_key = secret['weather_api_key']

except Exception as e:
    raise e

# api key to use LangSmith
langsmith_api_key = ""
try:
    get_langsmith_api_secret = secretsmanager.get_secret_value(
        SecretId=f"langsmithapikey-{projectName}"
    )
    #print('get_langsmith_api_secret: ', get_langsmith_api_secret)
    secret = json.loads(get_langsmith_api_secret['SecretString'])
    #print('secret: ', secret)
    langsmith_api_key = secret['langsmith_api_key']
    langchain_project = secret['langchain_project']
except Exception as e:
    raise e

if langsmith_api_key:
    os.environ["LANGCHAIN_API_KEY"] = langsmith_api_key
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = langchain_project

# api key to use Tavily Search
tavily_key = tavily_api_wrapper = ""
try:
    get_tavily_api_secret = secretsmanager.get_secret_value(
        SecretId=f"tavilyapikey-{projectName}"
    )
    #print('get_tavily_api_secret: ', get_tavily_api_secret)
    secret = json.loads(get_tavily_api_secret['SecretString'])
    #print('secret: ', secret)

    if "tavily_api_key" in secret:
        tavily_key = secret['tavily_api_key']
        #print('tavily_api_key: ', tavily_api_key)

        if tavily_key:
            tavily_api_wrapper = TavilySearchAPIWrapper(tavily_api_key=tavily_key)
            #     os.environ["TAVILY_API_KEY"] = tavily_key

            # # Tavily Tool Test
            # query = 'what is Amazon Nova Pro?'
            # search = TavilySearchResults(
            #     max_results=1,
            #     include_answer=True,
            #     include_raw_content=True,
            #     api_wrapper=tavily_api_wrapper,
            #     search_depth="advanced", # "basic"
            #     # include_domains=["google.com", "naver.com"]
            # )
            # output = search.invoke(query)
            # print('tavily output: ', output)
                
            # for result in output:
            #     logger.info(f"result: {result}")
            #     break
        else:
            logger.info(f"tavily_key is required.")

except Exception as e: 
    print('Tavily credential is required: ', e)
    raise e

# secret of code interpreter
code_interpreter_api_key = ""
try:
    get_code_interpreter_api_secret = secretsmanager.get_secret_value(
        SecretId=f"code-interpreter-{projectName}"
    )
    #print('get_code_interpreter_api_secret: ', get_code_interpreter_api_secret)
    secret = json.loads(get_code_interpreter_api_secret['SecretString'])
    #print('secret: ', secret)
    code_interpreter_api_key = secret['code_interpreter_api_key']
    code_interpreter_project = secret['project_name']
    code_interpreter_id = secret['code_interpreter_id']

    # logger.info(f"code_interpreter_id: {code_interpreter_id}")
except Exception as e:
    raise e

if code_interpreter_api_key:
    os.environ["RIZA_API_KEY"] = code_interpreter_api_key

def isKorean(text):
    # check korean
    pattern_hangul = re.compile('[\u3131-\u3163\uac00-\ud7a3]+')
    word_kor = pattern_hangul.search(str(text))
    # print('word_kor: ', word_kor)

    if word_kor and word_kor != 'None':
        # print('Korean: ', word_kor)
        return True
    else:
        # print('Not Korean: ', word_kor)
        return False
    
def traslation(chat, text, input_language, output_language):
    system = (
        "You are a helpful assistant that translates {input_language} to {output_language} in <article> tags." 
        "Put it in <result> tags."
    )
    human = "<article>{text}</article>"
    
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])
    # print('prompt: ', prompt)
    
    chain = prompt | chat    
    try: 
        result = chain.invoke(
            {
                "input_language": input_language,
                "output_language": output_language,
                "text": text,
            }
        )
        
        msg = result.content
        # print('translated text: ', msg)
    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"err_msg: {err_msg}")                
        raise Exception ("Not able to request to LLM")

    return msg[msg.find('<result>')+8:msg.find('</result>')] # remove <result> tag

def extract_thinking_tag(response, st):
    if response.find('<thinking>') != -1:
        status = response[response.find('<thinking>')+10:response.find('</thinking>')]
        logger.info(f"agent_thinking: {status}")                
        
        if debug_mode=="Enable":
            st.info(status)

        if response.find('<thinking>') == 0:
            msg = response[response.find('</thinking>')+12:]
        else:
            msg = response[:response.find('<thinking>')]
        logger.info(f"msg: {msg}")    
    else:
        msg = response

    return msg

def revise_question(query, st):    
    logger.info(f"###### revise_question ######")    

    chat = get_chat(extended_thinking="Disable")
    st.info("히스토리를 이용해 질문을 변경합니다.")
        
    if isKorean(query)==True :      
        human = (
            "이전 대화를 참조하여, 다음의 <question>의 뜻을 명확히 하는 새로운 질문을 한국어로 생성하세요." 
            "새로운 질문은 원래 질문의 중요한 단어를 반드시 포함합니다." 
            "결과는 <result> tag를 붙여주세요."
        
            "<question>"
            "{question}"
            "</question>"
        )
        
    else: 
        human = (
            "Rephrase the follow up <question> to be a standalone question." 
            "Put it in <result> tags."

            "<question>"
            "{question}"
            "</question>"
        )
            
    prompt = ChatPromptTemplate.from_messages([
        MessagesPlaceholder(variable_name="history"), 
        ("human", human)]
    )
    # print('prompt: ', prompt)
    
    history = memory_chain.load_memory_variables({})["chat_history"]
    # print('history: ', history)    

    if not len(history):        
        logger.info(f"no history")
        
        st.info("이전 히스트로가 없어서 질문을 그대로 전달합니다.")
        return query
                
    chain = prompt | chat    
    try: 
        result = chain.invoke(
            {
                "history": history,
                "question": query,
            }
        )
        generated_question = result.content
        
        revised_question = generated_question[generated_question.find('<result>')+8:len(generated_question)-9] # remove <result> tag                   
        # print('revised_question: ', revised_question)

        st.info(f"수정된 질문: {revised_question}")
        
    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")   
        raise Exception ("Not able to request to LLM")
            
    return revised_question    

def show_extended_thinking(st, result):
    # logger.info(f"result: {result}")
    if "thinking" in result.response_metadata:
        if "text" in result.response_metadata["thinking"]:
            thinking = result.response_metadata["thinking"]["text"]
            st.info(thinking)

####################### LangChain #######################
# General Conversation
#########################################################

def general_conversation(query):
    llm = get_chat(reasoning_mode)

    system = (
        "당신의 이름은 서연이고, 질문에 대해 친절하게 답변하는 사려깊은 인공지능 도우미입니다."
        "상황에 맞는 구체적인 세부 정보를 충분히 제공합니다." 
        "모르는 질문을 받으면 솔직히 모른다고 말합니다."
    )
    
    human = "Question: {input}"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system), 
        MessagesPlaceholder(variable_name="history"), 
        ("human", human)
    ])
                
    history = memory_chain.load_memory_variables({})["chat_history"]

    try: 
        if reasoning_mode == "Disable":
            chain = prompt | llm | StrOutputParser()
            output = chain.stream(
                {
                    "history": history,
                    "input": query,
                }
            )  
            response = output
        else:
            # output = llm.invoke(query)
            # logger.info(f"output: {output}")
            # response = output.content
            chain = prompt | llm
            output = chain.invoke(
                {
                    "history": history,
                    "input": query,
                }
            )
            logger.info(f"output: {output}")
            response = output
            
    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")  
        raise Exception ("Not able to request to LLM: "+err_msg)
        
    return response

def get_references(docs):
    reference = "\n\n### 관련 문서\n"
    for i, doc in enumerate(docs):
        page = ""
        if "page" in doc.metadata:
            page = doc.metadata['page']
            #print('page: ', page)            
        url = ""
        if "url" in doc.metadata:
            url = doc.metadata['url']
            #print('url: ', url)                
        name = ""
        if "name" in doc.metadata:
            name = doc.metadata['name']
            #print('name: ', name)     
           
        sourceType = ""
        if "from" in doc.metadata:
            sourceType = doc.metadata['from']
        else:
            # if useEnhancedSearch:
            #     sourceType = "OpenSearch"
            # else:
            #     sourceType = "WWW"
            sourceType = "WWW"

        #print('sourceType: ', sourceType)        
        
        #if len(doc.page_content)>=1000:
        #    excerpt = ""+doc.page_content[:1000]
        #else:
        #    excerpt = ""+doc.page_content
        excerpt = ""+doc.page_content
        # print('excerpt: ', excerpt)
        
        # for some of unusual case 
        #excerpt = excerpt.replace('"', '')        
        #excerpt = ''.join(c for c in excerpt if c not in '"')
        excerpt = re.sub('"', '', excerpt)
        excerpt = re.sub('\n', '', excerpt)   
        logger.info(f"excerpt(quotation removed): {excerpt}")
        
        if page:                
            reference = reference + f"{i+1}. {page}page in [{name}]({url})), {excerpt[:40]}...\n"
        else:
            reference = reference + f"{i+1}. [{name}]({url}), {excerpt[:40]}...\n"
    return reference

def show_graph(app, st):
    from IPython.display import Image
    from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles

    graphImage = Image(
        app.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API
        )
    )
    # show graph in streamlit
    st.image(graphImage.data, caption="Graph", use_container_width=True)

    # save a file
    import PIL
    import io
    pimg = PIL.Image.open(io.BytesIO(graphImage.data))
    pimg.save('graph-file.png')

####################### LangGraph #######################
# Agentic Workflow: Tool Use
#########################################################
image_url = []
@tool 
def get_book_list(keyword: str) -> str:
    """
    Search book list by keyword and then return book list
    keyword: search keyword
    return: book list
    """
    
    keyword = keyword.replace('\'','')

    answer = ""
    url = f"https://search.kyobobook.co.kr/search?keyword={keyword}&gbCode=TOT&target=total"
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        prod_info = soup.find_all("a", attrs={"class": "prod_info"})
        
        if len(prod_info):
            answer = "추천 도서는 아래와 같습니다.\n"
            
        for prod in prod_info[:5]:
            title = prod.text.strip().replace("\n", "")       
            link = prod.get("href")
            answer = answer + f"{title}, URL: {link}\n\n"
    
    return answer

@tool
def get_current_time(format: str=f"%Y-%m-%d %H:%M:%S")->str:
    """Returns the current date and time in the specified format"""
    # f"%Y-%m-%d %H:%M:%S"
    
    format = format.replace('\'','')
    timestr = datetime.datetime.now(timezone('Asia/Seoul')).strftime(format)
    logger.info(f"timestr: {timestr}") 
    
    return timestr

@tool
def get_weather_info(city: str) -> str:
    """
    retrieve weather information by city name and then return weather statement.
    city: the English name of city to retrieve
    return: weather statement
    """    
    
    city = city.replace('\n','')
    city = city.replace('\'','')
    city = city.replace('\"','')
                
    chat = get_chat(extended_thinking="Disable")
    if isKorean(city):
        place = traslation(chat, city, "Korean", "English")
        logger.info(f"city (translated): {place}") 
    else:
        place = city
        city = traslation(chat, city, "English", "Korean")
        logger.info(f"city (translated): {city}") 
        
    logger.info(f"place: {place}") 
    
    weather_str: str = f"{city}에 대한 날씨 정보가 없습니다."
    if weather_api_key: 
        apiKey = weather_api_key
        lang = 'en' 
        units = 'metric' 
        api = f"https://api.openweathermap.org/data/2.5/weather?q={place}&APPID={apiKey}&lang={lang}&units={units}"
        # print('api: ', api)
                
        try:
            result = requests.get(api)
            result = json.loads(result.text)
            logger.info(f"result: {result}") 
        
            if 'weather' in result:
                overall = result['weather'][0]['main']
                current_temp = result['main']['temp']
                min_temp = result['main']['temp_min']
                max_temp = result['main']['temp_max']
                humidity = result['main']['humidity']
                wind_speed = result['wind']['speed']
                cloud = result['clouds']['all']
                
                weather_str = f"{city}의 현재 날씨의 특징은 {overall}이며, 현재 온도는 {current_temp} 입니다. 현재 습도는 {humidity}% 이고, 바람은 초당 {wind_speed} 미터 입니다. 구름은 {cloud}% 입니다."                
                #weather_str = f"{city}의 현재 날씨의 특징은 {overall}이며, 현재 온도는 {current_temp}도 이고, 최저온도는 {min_temp}도, 최고 온도는 {max_temp}도 입니다. 현재 습도는 {humidity}% 이고, 바람은 초당 {wind_speed} 미터 입니다. 구름은 {cloud}% 입니다."
                #weather_str = f"Today, the overall of {city} is {overall}, current temperature is {current_temp} degree, min temperature is {min_temp} degree, highest temperature is {max_temp} degree. huminity is {humidity}%, wind status is {wind_speed} meter per second. the amount of cloud is {cloud}%."            
        except Exception:
            err_msg = traceback.format_exc()
            logger.info(f"error message: {err_msg}")                                 
            # raise Exception ("Not able to request to LLM")    
        
    logger.info(f"weather_str: {weather_str}")
    return weather_str

# user defined tavily tool
@tool
def search_by_tavily(keyword: str) -> str:
    """
    Search general information by keyword and then return the result as a string.
    keyword: search keyword
    return: the information of keyword
    """    
    global reference_docs    
    answer = ""
    
    if tavily_key:
        keyword = keyword.replace('\'','')
        
        search = TavilySearchResults(
            max_results=3,
            include_answer=True,
            include_raw_content=True,
            api_wrapper=tavily_api_wrapper,
            search_depth="advanced", # "basic"
            # include_domains=["google.com", "naver.com"]
        )
                    
        try: 
            output = search.invoke(keyword)
            logger.info(f"tavily output: {output}")
            
            for result in output:
                logger.info(f"result: {result}")
                if result:
                    content = result.get("content")
                    url = result.get("url")
                    
                    reference_docs.append(
                        Document(
                            page_content=content,
                            metadata={
                                'name': 'WWW',
                                'url': url,
                                'from': 'tavily'
                            },
                        )
                    )                
                    answer = answer + f"{content}, URL: {url}\n"
        
        except Exception:
            err_msg = traceback.format_exc()
            logger.info(f"error message: {err_msg}")                    
            # raise Exception ("Not able to request to tavily")   
    
    if answer == "":
        # answer = "No relevant documents found." 
        answer = "관련된 정보를 찾지 못하였습니다."

    return answer

@tool
def stock_data_lookup(ticker, country):
    """
    Retrieve accurate stock data for a given ticker.
    country: the english country name of the stock
    ticker: the ticker to retrieve price history for. In South Korea, a ticker is a 6-digit number.
    return: the information of ticker
    """ 
    com = re.compile('[a-zA-Z]') 
    alphabet = com.findall(ticker)
    logger.info(f"alphabet: {alphabet}")

    logger.info(f"country: {country}")

    if len(alphabet)==0:
        if country == "South Korea":
            ticker += ".KS"
        elif country == "Japan":
            ticker += ".T"
    logger.info(f"ticker: {ticker}")
    
    try: 
        stock = yf.Ticker(ticker)
    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")
    
    # get the price history for past 1 month
    history = stock.history(period="1mo")
    logger.info(f"history: {history}")
    
    result = f"## Trading History\n{history}"
    #history.reset_index().to_json(orient="split", index=False, date_format="iso")    
    
    result += f"\n\n## Financials\n{stock.financials}"    
    logger.info(f"financials: {stock.financials}")

    result += f"\n\n## Major Holders\n{stock.major_holders}"
    logger.info(f"major_holders: {stock.major_holders}")

    logger.info(f"result: {result}")

    return result

def generate_short_uuid(length=8):
    full_uuid = uuid.uuid4().hex
    return full_uuid[:length]

from rizaio import Riza
@tool
def code_drawer(code):
    """
    Execute a Python script for draw a graph.
    Since Python runtime cannot use external APIs, necessary data must be included in the code.
    The graph should use English exclusively for all textual elements.
    Do not save pictures locally bacause the runtime does not have filesystem.
    When a comparison is made, all arrays must be of the same length.
    code: the Python code was written in English
    return: the url of graph
    """ 
    # The Python runtime does not have filesystem access, but does include the entire standard library.
    # Make HTTP requests with the httpx or requests libraries.
    # Read input from stdin and write output to stdout."    
        
    code = re.sub(r"seaborn", "classic", code)
    code = re.sub(r"plt.savefig", "#plt.savefig", code)
    
    pre = f"os.environ[ 'MPLCONFIGDIR' ] = '/tmp/'\n"  # matplatlib
    post = """\n
import io
import base64
buffer = io.BytesIO()
plt.savefig(buffer, format='png')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.getvalue()).decode()

print(image_base64)
"""
    code = pre + code + post    
    logger.info(f"code: {code}")
    
    result = ""
    try:     
        client = Riza()

        resp = client.command.exec(
            runtime_revision_id=code_interpreter_id,
            language="python",
            code=code,
            env={
                "DEBUG": "true",
            }
        )
        output = dict(resp)
        # print(f"output: {output}") # includling exit_code, stdout, stderr

        if resp.exit_code > 0:
            logger.debug(f"non-zero exit code {resp.exit_code}")

        base64Img = resp.stdout
        
        if base64Img:
            byteImage = BytesIO(base64.b64decode(base64Img))

            image_name = generate_short_uuid()+'.png'
            url = upload_to_s3(byteImage, image_name)
            logger.info(f"url: {url}")

            file_name = url[url.rfind('/')+1:]
            logger.info(f"file_name: {file_name}")

            global image_url
            image_url.append(path+'/'+s3_image_prefix+'/'+parse.quote(file_name))
            logger.info(f"image_url: {image_url}")
            result = f"생성된 그래프의 URL: {image_url}"

            # im = Image.open(BytesIO(base64.b64decode(base64Img)))  # for debuuing
            # im.save(image_name, 'PNG')

    except Exception:
        result = "그래프 생성에 실패했어요. 다시 시도해주세요."
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")

    logger.info(f"result: {result}")
    return result

@tool
def code_interpreter(code):
    """
    Execute a Python script to solve a complex question.    
    Since Python runtime cannot use external APIs, necessary data must be included in the code.
    The Python runtime does not have filesystem access, but does include the entire standard library.
    code: the Python code was written in English
    return: the stdout value
    """ 
    # Make HTTP requests with the httpx or requests libraries.
    # Read input from stdin and write output to stdout."  
        
    code = re.sub(r"seaborn", "classic", code)
    code = re.sub(r"plt.savefig", "#plt.savefig", code)
    
    pre = f"os.environ[ 'MPLCONFIGDIR' ] = '/tmp/'\n"  # matplatlib
    post = """"""
    # code = pre + code + post    
    code = pre + code
    logger.info(f"code: {code}")
    
    result = ""
    try:     
        client = Riza()

        resp = client.command.exec(
            runtime_revision_id=code_interpreter_id,
            language="python",
            code=code,
            env={
                "DEBUG": "true",
            }
        )
        output = dict(resp)
        print(f"output: {output}") # includling exit_code, stdout, stderr

        if resp.exit_code > 0:
            logger.debug(f"non-zero exit code {resp.exit_code}")

        resp.stdout        
        result = f"프로그램 실행 결과: {resp.stdout}"

    except Exception:
        result = "프로그램 실행에 실패했습니다. 다시 시도해주세요."
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")

    logger.info(f"result: {result}")
    return result

repl = PythonAstREPLTool()

@tool
def repl_coder(code):
    """
    Use this to execute python code and do math. 
    If you want to see the output of a value, you should print it out with `print(...)`. This is visible to the user.
    code: the Python code was written in English
    """
    try:
        result = repl.run(code)
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    
    if result is None:
        result = "It didn't return anything."

    return result

@tool
def repl_drawer(code):
    """
    Execute a Python script for draw a graph.
    Since Python runtime cannot use external APIs, necessary data must be included in the code.
    The graph should use English exclusively for all textual elements.
    Do not save pictures locally bacause the runtime does not have filesystem.
    When a comparison is made, all arrays must be of the same length.
    code: the Python code was written in English
    return: the url of graph
    """ 
        
    code = re.sub(r"seaborn", "classic", code)
    code = re.sub(r"plt.savefig", "#plt.savefig", code)
    code = re.sub(r"plt.show", "#plt.show", code)

    post = """\n
import io
import base64
buffer = io.BytesIO()
plt.savefig(buffer, format='png')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.getvalue()).decode()

print(image_base64)
"""
    code = code + post    
    logger.info(f"code: {code}")
    
    result = ""
    try:     
        resp = repl.run(code)

        base64Img = resp
        
        if base64Img:
            byteImage = BytesIO(base64.b64decode(base64Img))

            image_name = generate_short_uuid()+'.png'
            url = upload_to_s3(byteImage, image_name)
            logger.info(f"url: {url}")

            file_name = url[url.rfind('/')+1:]
            logger.info(f"file_name: {file_name}")

            global image_url
            image_url.append(path+'/'+s3_image_prefix+'/'+parse.quote(file_name))
            logger.info(f"image_url: {image_url}")
            result = f"생성된 그래프의 URL: {image_url}"

            # im = Image.open(BytesIO(base64.b64decode(base64Img)))  # for debuuing
            # im.save(image_name, 'PNG')

    except Exception:
        result = "그래프 생성에 실패했어요. 다시 시도해주세요."
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")

    logger.info(f"result: {result}")
    return result

# tools = [get_current_time, get_book_list, get_weather_info, search_by_tavily, stock_data_lookup, code_drawer, code_interpreter]
tools = [get_current_time, get_book_list, get_weather_info, search_by_tavily, stock_data_lookup, repl_drawer, repl_coder]

def run_agent_executor(query, historyMode, st):
    chatModel = get_chat(reasoning_mode)     
    model = chatModel.bind_tools(tools)

    class State(TypedDict):
        # messages: Annotated[Sequence[BaseMessage], operator.add]
        messages: Annotated[list, add_messages]

    tool_node = ToolNode(tools)

    def should_continue(state: State) -> Literal["continue", "end"]:
        logger.info(f"###### should_continue ######")

        # logger.info(f"state: {state}")
        messages = state["messages"]    

        last_message = messages[-1]
        # logger.info(f"last_message: {last_message}")
                
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            logger.info(f"{last_message.content}")
            if debug_mode=='Enable' and last_message.content:
                st.info(f"last_message: {last_message.content}")

            for message in last_message.tool_calls:
                args = message['args']
                if debug_mode=='Enable': 
                    if "code" in args:                    
                        state_msg = f"tool name: {message['name']}"
                        utils.status(st, state_msg)                    
                        utils.stcode(st, args['code'])
                    
                    elif model_type=='claude':
                        state_msg = f"tool name: {message['name']}, args: {message['args']}"
                        utils.status(st, state_msg)
            
            logger.info("--- CONTINUE: {last_message.tool_calls[-1]['name']} ---")
            return "continue"
        
        #if not last_message.tool_calls:
        else:
            # utils.status(st, last_message.content)            
            logger.info(f"--- END ---")
            return "end"
           
    def call_model(state: State, config):
        logger.info(f"###### call_model ######")
        # logger.info(f"state: {state['messages']}")
                
        if isKorean(state["messages"][0].content)==True:
            system = (
                "당신의 이름은 서연이고, 질문에 친근한 방식으로 대답하도록 설계된 대화형 AI입니다."
                "상황에 맞는 구체적인 세부 정보를 충분히 제공합니다."
                "모르는 질문을 받으면 솔직히 모른다고 말합니다."
                "한국어로 답변하세요."
            )
        else: 
            system = (            
                "You are a conversational AI designed to answer in a friendly way to a question."
                "If you don't know the answer, just say that you don't know, don't try to make up an answer."
            )
                
        for attempt in range(5):   
            # logger.info(f"attempt: {attempt}")
            try:
                prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", system),
                        MessagesPlaceholder(variable_name="messages"),
                    ]
                )
                chain = prompt | model
                    
                response = chain.invoke(state["messages"])
                logger.info(f"call_model response: {response}")

                # extended thinking
                if debug_mode=="Enable":
                    show_extended_thinking(st, response)
            
                if isinstance(response.content, list):      
                    for re in response.content:
                        if "type" in re:
                            if re['type'] == 'text':
                                logger.info(f"call_model: (text) --> {re['type']}: {re['text']}")

                                status = re['text']
                                # logger.info(f"status: {status}")
                                
                                status = status.replace('`','')
                                status = status.replace('\"','')
                                status = status.replace("\'",'')
                                
                                # logger.info(f"status: {status}")
                                if status.find('<thinking>') != -1:
                                    # logger.info(f"Remove <thinking> tag.")
                                    status = status[status.find('<thinking>')+10:status.find('</thinking>')]
                                    # logger.info(f"status without <thinking> tag: {status}")

                                if debug_mode=="Enable":
                                    utils.status(st, status)
                                
                            elif re['type'] == 'tool_use':                
                                logger.info(f"call_model: (tool_use) --> {re['type']}: {re['name']}, {re['input']}")

                                if debug_mode=="Enable":
                                    utils.status(st, f"{re['type']}: {re['name']}, {re['input']}")
                            else:
                                logger.info(f"{re}")
                        else: # answer
                            logger.info(f"{response.content}")
                break
            except Exception:
                response = AIMessage(content="답변을 찾지 못하였습니다.")

                err_msg = traceback.format_exc()
                logger.info(f"error message: {err_msg}")
                # raise Exception ("Not able to request to LLM")

        return {"messages": [response]}        

    def buildChatAgent():
        workflow = StateGraph(State)

        workflow.add_node("agent", call_model)
        workflow.add_node("action", tool_node)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "continue": "action",
                "end": END,
            },
        )
        workflow.add_edge("action", "agent")

        return workflow.compile()

    def buildChatAgentWithHistory():
        workflow = StateGraph(State)

        workflow.add_node("agent", call_model)
        workflow.add_node("action", tool_node)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "continue": "action",
                "end": END,
            },
        )
        workflow.add_edge("action", "agent")

        return workflow.compile(
            checkpointer=checkpointer,
            store=memorystore
        )

    # initiate
    global reference_docs, contentList, image_url
    reference_docs = []
    contentList = []
    image_url = []
            
    inputs = [HumanMessage(content=query)]

    if historyMode == "Enable":
        app = buildChatAgentWithHistory()
        config = {
            "recursion_limit": 50,
            "configurable": {"thread_id": userId}
        }
    else:
        app = buildChatAgent()
        config = {
            "recursion_limit": 50
        }

    # msg = message.content
    result = app.invoke({"messages": inputs}, config)
    #print("result: ", result)

    msg = result["messages"][-1].content
    logger.info(f"msg: {msg}")

    if historyMode == "Enable":
        snapshot = app.get_state(config)
        # logger.info(f"snapshot.values: {snapshot.values}")
        messages = snapshot.values["messages"]
        for i, m in enumerate(messages):
            logger.info(f"{i} --> {m.content}")
        logger.info(f"userId: {userId}")

    reference = "" 
    if reference_docs:
        reference = get_references(reference_docs)

    for i, doc in enumerate(reference_docs):
        logger.info(f"--> reference {i}: {doc}")
        
    reference = ""
    if reference_docs:
        reference = get_references(reference_docs)

    msg = extract_thinking_tag(msg, st)
    
    return msg+reference, image_url, reference_docs

"""
def run_agent_executor2(query, st, debug_mode, model_name):        
    class State(TypedDict):
        messages: Annotated[list, add_messages]
        answer: str

    tool_node = ToolNode(tools)
            
    def create_agent(chat, tools):        
        tool_names = ", ".join([tool.name for tool in tools])
        logger.info(f"tool_names: {tool_names}")

        system = (
            "당신의 이름은 서연이고, 질문에 친근한 방식으로 대답하도록 설계된 대화형 AI입니다."
            "상황에 맞는 구체적인 세부 정보를 충분히 제공합니다."
            "모르는 질문을 받으면 솔직히 모른다고 말합니다."

            "Use the provided tools to progress towards answering the question."
            "If you are unable to fully answer, that's OK, another assistant with different tools "
            "will help where you left off. Execute what you can to make progress."
            "You have access to the following tools: {tool_names}."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system",system),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        
        prompt = prompt.partial(tool_names=tool_names)
        
        return prompt | chat.bind_tools(tools)
    
    def agent_node(state, agent, name):
        logger.info(f"###### agent_node:{name} ######")

        last_message = state["messages"][-1]
        logger.info(f"last_message: {last_message}")
        if isinstance(last_message, ToolMessage) and last_message.content=="":    
            logger.info(f"last_message is empty")
            answer = get_basic_answer(state["messages"][0].content)  
            return {
                "messages": [AIMessage(content=answer)],
                "answer": answer
            }
        
        response = agent.invoke(state["messages"])
        logger.info(f"response: {response}")

        if "answer" in state:
            answer = state['answer']
        else:
            answer = ""

        for re in response.content:
            if "type" in re:
                if re['type'] == 'text':
                    logger.info(f"--> {re['type']}: {re['text']}")

                    status = re['text']
                    if status.find('<thinking>') != -1:
                        logger.info(f"Remove <thinking> tag.")
                        status = status[status.find('<thinking>')+10:status.find('</thinking>')]
                        logger.info(f"agent_thinking: {status}")

                    if debug_mode=="Enable":
                        utils.status(st, status)

                elif re['type'] == 'tool_use':                
                    logger.info(f"--> {re['type']}: name: {re['name']}, input: {re['input']}")

                    if debug_mode=="Enable":
                        utils.status(st, f"{re['type']}: name: {re['name']}, input: {re['input']}")
                else:
                    print(re)
                    logger.info(f"{re}")
            else: # answer
                answer += '\n'+response.content
                print(response.content)
                logger.info(f"{response.content}")
                break

        response = AIMessage(**response.dict(exclude={"type", "name"}), name=name)     
        logger.info(f"message: {response}")
        
        return {
            "messages": [response],
            "answer": answer
        }
    
    def final_answer(state):
        logger.info(f"###### final_answer ######")   

        answer = ""        
        if "answer" in state:
            answer = state['answer']            
        else:
            answer = state["messages"][-1].content

        if answer.find('<thinking>') != -1:
            logger.info(f"Remove <thinking> tag.")
            answer = answer[answer.find('</thinking>')+12:]
        logger.info(f"answer: {answer}")
        
        return {
            "answer": answer
        }
    
    chat = get_chat(reasoning_mode)
    
    execution_agent = create_agent(chat, tools)
    
    execution_agent_node = functools.partial(agent_node, agent=execution_agent, name="execution_agent")
    
    def should_continue(state: State, config) -> Literal["continue", "end"]:
        logger.info(f"###### should_continue ######")
        messages = state["messages"]    
        # print('(should_continue) messages: ', messages)
        
        last_message = messages[-1]        
        if not last_message.tool_calls:
            logger.info(f"Final: {last_message.content}")
            logger.info(f"--- END ---")
            return "end"
        else:      
            logger.info(f"tool_calls: {last_message.tool_calls}")

            for message in last_message.tool_calls:
                logger.info(state_msg)
                # update_state_message(f"calling... {message['name']}", config)
                
                args = message['args']
                if debug_mode=='Enable': 
                    if "code" in args:                    
                        state_msg = f"tool name: {message['name']}"
                        utils.status(st, state_msg)                    
                        utils.stcode(st, args['code'])
                    
                    elif model_type=='claude':
                        state_msg = f"tool name: {message['name']}, args: {message['args']}"
                        utils.status(st, state_msg)
                    

            logger.info(f"--- CONTINUE: {last_message.tool_calls[-1]['name']} ---")
            return "continue"

    def buildAgentExecutor():
        workflow = StateGraph(State)

        workflow.add_node("agent", execution_agent_node)
        workflow.add_node("action", tool_node)
        workflow.add_node("final_answer", final_answer)
        
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "continue": "action",
                "end": "final_answer",
            },
        )
        workflow.add_edge("action", "agent")
        workflow.add_edge("final_answer", END)

        return workflow.compile()

    app = buildAgentExecutor()
            
    inputs = [HumanMessage(content=query)]
    config = {"recursion_limit": 50}
    
    msg = ""
    # for event in app.stream({"messages": inputs}, config, stream_mode="values"):   
    #     # print('event: ', event)
        
    #     if "answer" in event:
    #         msg = event["answer"]
    #     else:
    #         msg = event["messages"][-1].content
    #     # print('message: ', message)

    output = app.invoke({"messages": inputs}, config)
    logger.info(f"output: {output}")

    msg = output['answer']

    return msg

def get_basic_answer(query):
    logger.info(f"#### get_basic_answer ####")
    chat = get_chat(reasoning_mode)

    if isKorean(query)==True:
        system = (
            "당신의 이름은 서연이고, 질문에 대해 친절하게 답변하는 사려깊은 인공지능 도우미입니다."
            "상황에 맞는 구체적인 세부 정보를 충분히 제공합니다." 
            "모르는 질문을 받으면 솔직히 모른다고 말합니다."
        )
    else: 
        system = (
            "You will be acting as a thoughtful advisor."
            "Using the following conversation, answer friendly for the newest question." 
            "If you don't know the answer, just say that you don't know, don't try to make up an answer."     
        )    
    
    human = "Question: {input}"    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system), 
        ("human", human)
    ])    
    
    chain = prompt | chat    
    output = chain.invoke({"input": query})
    logger.info(f"output.content: {output.content}")

    return output.content
"""

####################### LangChain #######################
# Translation (English)
#########################################################

def translate_text(text, model_name, st):
    global llmMode
    llmMode = model_name

    chat = get_chat(extended_thinking="Disable")

    system = (
        "You are a helpful assistant that translates {input_language} to {output_language} in <article> tags. Put it in <result> tags."
    )
    human = "<article>{text}</article>"
    
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])
    # print('prompt: ', prompt)
    
    if isKorean(text)==False :
        input_language = "English"
        output_language = "Korean"
    else:
        input_language = "Korean"
        output_language = "English"
                        
    chain = prompt | chat    
    try: 
        result = chain.invoke(
            {
                "input_language": input_language,
                "output_language": output_language,
                "text": text,
            }
        )

        # extended thinking
        if debug_mode=="Enable":
            show_extended_thinking(st, result)

        msg = result.content
        logger.info(f"translated text: {msg}")
    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")                    
        raise Exception ("Not able to request to LLM")

    if msg.find('<result>') != -1:
        msg = msg[msg.find('<result>')+8:msg.find('</result>')] # remove <result> tag
    if msg.find('<article>') != -1:
        msg = msg[msg.find('<article>')+9:msg.find('</article>')] # remove <article> tag

    return msg

####################### LangChain #######################
# Translation (Japanese)
#########################################################

def translate_text_for_japanese(text, model_name, st):
    global llmMode
    llmMode = model_name

    chat = get_chat(extended_thinking="Disable")

    system = (
        "You are a helpful assistant that translates {input_language} to {output_language} in <article> tags. Put it in <result> tags."
    )
    human = "<article>{text}</article>"
    
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])
    # print('prompt: ', prompt)
    
    input_language = "Japanese"
    output_language = "Korean"
                        
    chain = prompt | chat    
    try: 
        result = chain.invoke(
            {
                "input_language": input_language,
                "output_language": output_language,
                "text": text,
            }
        )

        # extended thinking
        if debug_mode=="Enable":
            show_extended_thinking(st, result)

        msg = result.content
        logger.info(f"translated text from Japanese: {msg}")
    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")                    
        raise Exception ("Not able to request to LLM")

    if msg.find('<result>') != -1:
        msg = msg[msg.find('<result>')+8:msg.find('</result>')] # remove <result> tag
    if msg.find('<article>') != -1:
        msg = msg[msg.find('<article>')+9:msg.find('</article>')] # remove <article> tag

    return msg

####################### LangChain #######################
# Grammer Check
#########################################################
    
def check_grammer(text, model_name, st):
    global llmMode
    llmMode = model_name

    chat = get_chat(extended_thinking="Disable")

    if isKorean(text)==True:
        system = (
            "다음의 <article> tag안의 문장의 오류를 찾아서 설명하고, 오류가 수정된 문장을 답변 마지막에 추가하여 주세요."
        )
    else: 
        system = (
            "Here is pieces of article, contained in <article> tags. Find the error in the sentence and explain it, and add the corrected sentence at the end of your answer."
        )
        
    human = "<article>{text}</article>"
    
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])
    # print('prompt: ', prompt)
    
    chain = prompt | chat    
    try: 
        result = chain.invoke(
            {
                "text": text
            }
        )

        # extended thinking
        if debug_mode=="Enable":
            show_extended_thinking(st, result)
        
        msg = result.content
        logger.info(f"result of grammer correction: {msg}")
    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")                    
        raise Exception ("Not able to request to LLM")
    
    return msg

####################### LangChain #######################
# Image Analysis
#########################################################

def upload_to_s3(file_bytes, file_name):
    """
    Upload a file to S3 and return the URL
    """
    try:
        s3_client = boto3.client(
            service_name='s3',
            region_name=bedrock_region
        )
        # Generate a unique file name to avoid collisions
        #timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        #unique_id = str(uuid.uuid4())[:8]
        #s3_key = f"uploaded_images/{timestamp}_{unique_id}_{file_name}"

        content_type = utils.get_contents_type(file_name)       
        logger.info(f"content_type: {content_type}") 

        if content_type == "image/jpeg" or content_type == "image/png":
            s3_key = f"{s3_image_prefix}/{file_name}"
        else:
            s3_key = f"{s3_prefix}/{file_name}"
        
        user_meta = {  # user-defined metadata
            "content_type": content_type,
            "model_name": model_name
        }
        
        response = s3_client.put_object(
            Bucket=s3_bucket, 
            Key=s3_key, 
            ContentType=content_type,
            Metadata = user_meta,
            Body=file_bytes            
        )
        logger.info(f"upload response: {response}")

        url = f"https://{s3_bucket}.s3.amazonaws.com/{s3_key}"
        return url
    
    except Exception as e:
        err_msg = f"Error uploading to S3: {str(e)}"
        logger.info(f"{err_msg}")
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
            err_msg = f"Error downloading image from S3: {str(e)}"
            print(err_msg)
            logger.info(f"{err_msg}")
            continue
    return images

def tavily_search(query, k):
    docs = []    
    try:
        tavily_client = TavilyClient(api_key=tavily_key)
        response = tavily_client.search(query, max_results=k)
        # print('tavily response: ', response)
            
        for r in response["results"]:
            name = r.get("title")
            if name is None:
                name = 'WWW'
            
            docs.append(
                Document(
                    page_content=r.get("content"),
                    metadata={
                        'name': name,
                        'url': r.get("url"),
                        'from': 'tavily'
                    },
                )
            )                   
    except Exception as e:
        logger.debug(f"Exception: {e}")

    return docs

####################### LangChain #######################
# Image Summarization
#########################################################
    
def get_image_summarization(object_name, prompt, st):
    # load image
    s3_client = boto3.client(
        service_name='s3',
        region_name=bedrock_region
    )

    if debug_mode=="Enable":
        status = "이미지를 가져옵니다."
        logger.info(f"status: {status}")
        st.info(status)
                
    image_obj = s3_client.get_object(Bucket=s3_bucket, Key=s3_image_prefix+'/'+object_name)
    # print('image_obj: ', image_obj)
    
    image_content = image_obj['Body'].read()
    img = Image.open(BytesIO(image_content))
    
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
    if debug_mode=="Enable":
        status = "이미지에서 텍스트를 추출합니다."
        logger.info(f"status: {status}")
        st.info(status)

    text = extract_text(img_base64)
    logger.info(f"extracted text: {text}")

    if text.find('<result>') != -1:
        extracted_text = text[text.find('<result>')+8:text.find('</result>')] # remove <result> tag
        # print('extracted_text: ', extracted_text)
    else:
        extracted_text = text
    
    if debug_mode=="Enable":
        status = f"### 추출된 텍스트\n\n{extracted_text}"
        logger.info(f"status: {status}")
        st.info(status)
    
    if debug_mode=="Enable":
        status = "이미지의 내용을 분석합니다."
        logger.info(f"status: {status}")
        st.info(status)

    image_summary = summary_image(img_base64, prompt)
    logger.info(f"image summary:: {image_summary}")
        
    if len(extracted_text) > 10:
        contents = f"## 이미지 분석\n\n{image_summary}\n\n## 추출된 텍스트\n\n{extracted_text}"
    else:
        contents = f"## 이미지 분석\n\n{image_summary}"
    logger.info(f"image contents: {contents}")

    return contents

def extract_text(img_base64):
    multimodal = get_chat(extended_thinking="Disable")
    query = "텍스트를 추출해서 markdown 포맷으로 변환하세요. <result> tag를 붙여주세요."
    
    messages = [
        HumanMessage(
            content=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}", 
                    },
                },
                {
                    "type": "text", "text": query
                },
            ]
        )
    ]
    
    for attempt in range(5):
        logger.info(f"attempt: {attempt}")
        try: 
            result = multimodal.invoke(messages)
            
            extracted_text = result.content
            # print('result of text extraction from an image: ', extracted_text)
            break
        except Exception:
            err_msg = traceback.format_exc()
            logger.debug(f"error message: {err_msg}")                    
            # raise Exception ("Not able to request to LLM")
        
    logger.info(f"extracted_text: {extracted_text}")
    if len(extracted_text)<10:
        extracted_text = "텍스트를 추출하지 못하였습니다."
    
    return extracted_text

def summary_image(img_base64, prompt):
    chat = get_chat(extended_thinking="Disable")

    if prompt:        
        query = f"{prompt}. markdown 포맷으로 답변을 작성합니다."
    else:
        query = "이미지가 의미하는 내용을 풀어서 자세히 알려주세요. markdown 포맷으로 답변을 작성합니다."
    
    messages = [
        HumanMessage(
            content=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}", 
                    },
                },
                {
                    "type": "text", "text": query
                },
            ]
        )
    ]
    
    for attempt in range(5):
        logger.info(f"attempt: {attempt}")
        try: 
            result = chat.invoke(messages)
            
            summary = result.content
            # print('summary from an image: ', summary)
            break
        except Exception:
            err_msg = traceback.format_exc()
            logger.debug(f"error message: {err_msg}")                    
            raise Exception ("Not able to request to LLM")
    
    logger.info(f"summary: {summary}")
    if len(summary)<10:
        summary = "이미지의 내용을 분석하지 못하였습니다."

    return summary
