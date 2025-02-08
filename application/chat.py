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
import logging
import sys

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
from botocore.exceptions import ClientError
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import START, END, StateGraph
from typing import Any, List, Tuple, Dict, Optional, cast, Literal, Sequence, Union
from typing_extensions import Annotated, TypedDict
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger()
logger.setLevel(logging.INFO)
#formatter = logging.Formatter('%(asctime)s | %(filename)s:%(lineno)d | %(levelname)s | %(message)s')
formatter = logging.Formatter('%(asctime)s | %(filename)s:%(lineno)d | %(message)s')

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
stdout_handler.setFormatter(formatter)

userId = "demo"
map_chain = dict() 

enableLoggerChat = False
print('enableLoggerChat: ', enableLoggerChat)

enableLoggerApp = False
def get_logger_state():
    global enableLoggerApp
    if not enableLoggerApp:
        enableLoggerApp = True
    return enableLoggerApp

def initiate():
    global userId
    global memory_chain
    global enableLogger

    userId = uuid.uuid4().hex
    logger.info(f"userId: {userId}")

    if userId in map_chain:  
            # print('memory exist. reuse it!')
            memory_chain = map_chain[userId]
    else: 
        # print('memory does not exist. create new one!')        
        memory_chain = ConversationBufferWindowMemory(memory_key="chat_history", output_key='answer', return_messages=True, k=5)
        map_chain[userId] = memory_chain

    if not enableLoggerChat:
        logger.addHandler(stdout_handler)        
        try:
            with open("/home/config.json", "r", encoding="utf-8") as f:        
                file_handler = logging.FileHandler('/var/log/application/logs.log')
                file_handler.setLevel(logging.INFO)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)

                logger.info("Ready to write log (chat)!")

                enableLoggerChat = True
                print('enableLoggerChat: ', enableLoggerChat)
        except Exception:
            print("Not available to write application log (chat)")

initiate()
 
try:
    with open("/home/config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        # print(f"config: {config}")
        logger.info(f"config: {config}")
except Exception:
    print("use local configuration")
    with open("application/config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        # print('config: ', config)
        logger.info(f"config: {config}")
        
bedrock_region = "us-west-2"
projectName = config["projectName"] if "projectName" in config else "bedrock-agent"

accountId = config["accountId"] if "accountId" in config else None
if accountId is None:
    raise Exception ("No accountId")

region = config["region"] if "region" in config else "us-west-2"
print('region: ', region)
logger.info(f"region: {region}")

bucketName = config["bucketName"] if "bucketName" in config else f"storage-for-{projectName}-{accountId}-{region}" 
print('bucketName: ', bucketName)
logger.info(f"bucketName: {bucketName}")

s3_prefix = 'docs'

MSG_LENGTH = 100



model_name = "Nova Pro"
model_type = "nova"
multi_region = 'Enable'
contextual_embedding = "Disable"
debug_mode = "Enable"

models = info.get_model_info(model_name)
number_of_models = len(models)
selected_chat = 0

def update(modelName, debugMode, multiRegion):    
    global model_name, debug_mode, multi_region
    global selected_chat, models, number_of_models
    
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

def clear_chat_history():
    memory_chain = []
    map_chain[userId] = memory_chain

def save_chat_history(text, msg):
    memory_chain.chat_memory.add_user_message(text)
    if len(msg) > MSG_LENGTH:
        memory_chain.chat_memory.add_ai_message(msg[:MSG_LENGTH])                          
    else:
        memory_chain.chat_memory.add_ai_message(msg) 

def get_chat():
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
                'max_attempts': 30
            }
        )
    )
    parameters = {
        "max_tokens":maxOutputTokens,     
        "temperature":0.1,
        "top_k":250,
        "top_p":0.9,
        "stop_sequences": [STOP_SEQUENCE]
    }
    # print('parameters: ', parameters)

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

    return msg[msg.find('<result>')+8:len(msg)-9] # remove <result> tag

def extract_thinking_tag(response, st):
    if response.find('<thinking>') != -1:
        status = response[response.find('<thinking>')+11:response.find('</thinking>')]
        logger.info(f"agent_thinking: {status}")                
        
        if debug_mode=="Enable":
            st.info(status)

        if response.find('<thinking>') == 0:
            msg = response[response.find('</thinking>')+13:]
        else:
            msg = response[:response.find('<thinking>')]
        logger.info(f"msg: {msg}")    
    else:
        msg = response

    return msg

def revise_question(query, st):    
    logger.info(f"###### revise_question ######")    

    chat = get_chat()
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

####################### LangChain #######################
# General Conversation
#########################################################

def general_conversation(query):
    chat = get_chat()

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

    chain = prompt | chat | StrOutputParser()
    try: 
        stream = chain.stream(
            {
                "history": history,
                "input": query,
            }
        )  
            
    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")  
        raise Exception ("Not able to request to LLM: "+err_msg)
        
    return stream

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
        logger.info(f"excerpt(quotation removed): {excerpt}")
        
        if page:                
            reference = reference + f"{i+1}. {page}page in [{name}]({url})), {excerpt[:40]}...\n"
        else:
            reference = reference + f"{i+1}. [{name}]({url}), {excerpt[:40]}...\n"
    return reference

####################### LangGraph #######################
# Agentic Workflow: Tool Use
#########################################################

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
    city: the name of city to retrieve
    return: weather statement
    """    
    
    city = city.replace('\n','')
    city = city.replace('\'','')
    city = city.replace('\"','')
                
    chat = get_chat()
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


# Tavily Tool
# tavily_tool = TavilySearchResults(max_results=3,
#     include_answer=True,
#     include_raw_content=True,
#     api_wrapper=tavily_api_wrapper,
#     search_depth="advanced", # "basic"
#     include_domains=["google.com", "naver.com"]
# )

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
    Retrieve accurate stock trends for a given ticker.
    ticker: the ticker to retrieve price history for
    country: the english country name of the stock
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
    
    stock = yf.Ticker(ticker)
    
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

tools = [get_current_time, get_book_list, get_weather_info, search_by_tavily, stock_data_lookup]        

def run_agent_executor(query, st):
    chatModel = get_chat()     
    model = chatModel.bind_tools(tools)

    class State(TypedDict):
        # messages: Annotated[Sequence[BaseMessage], operator.add]
        messages: Annotated[list, add_messages]

    tool_node = ToolNode(tools)

    def should_continue(state: State) -> Literal["continue", "end"]:
        logger.info(f"###### should_continue ######")

        logger.info(f"state: ', state")
        messages = state["messages"]    

        last_message = messages[-1]
        logger.info(f"last_message: ', last_message")
        
        # print('last_message: ', last_message)
        
        # if not isinstance(last_message, ToolMessage):
        #     return "end"
        # else:                
        #     return "continue"
        if isinstance(last_message, ToolMessage) or last_message.tool_calls:
            logger.info(f"tool_calls: {last_message.tool_calls}")

            for message in last_message.tool_calls:
                logger.info(f"tool name: {message['name']}, args: {message['args']}")
                # update_state_message(f"calling... {message['name']}", config)

            logger.info("--- CONTINUE: {last_message.tool_calls[-1]['name']} ---")
            return "continue"
        
        #if not last_message.tool_calls:
        else:
            print()
            logger.info(f"Final: {last_message.content}")
            logger.info(f"--- END ---")
            return "end"
           
    def call_model(state: State, config):
        logger.info(f"###### call_model ######")
        logger.info(f"state: {state['messages']}")
                
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
                
        for attempt in range(20):   
            logger.info(f"attempt: {attempt}")
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
            
                if isinstance(response.content, list):      
                    for re in response.content:
                        if "type" in re:
                            if re['type'] == 'text':
                                logger.info(f"--> {re['type']}: {re['text']}")

                                status = re['text']
                                logger.info(f"status: {status}")
                                
                                status = status.replace('`','')
                                status = status.replace('\"','')
                                status = status.replace("\'",'')
                                
                                logger.info(f"status: {status}")
                                if status.find('<thinking>') != -1:
                                    logger.info(f"rRemove <thinking> tag.")
                                    status = status[status.find('<thinking>')+11:status.find('</thinking>')]
                                    logger.info(f"status without <thinking> tag: {status}")

                                if debug_mode=="Enable":
                                    st.info(status)
                                
                            elif re['type'] == 'tool_use':                
                                logger.info(f"--> {re['type']}: {re['name']}, {re['input']}")

                                if debug_mode=="Enable":
                                    st.info(f"{re['type']}: {re['name']}, {re['input']}")
                            else:
                                logger.info(f"{re}")
                        else: # answer
                            print(response.content)
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

    # initiate
    global reference_docs, contentList
    reference_docs = []
    contentList = []

    app = buildChatAgent()
            
    inputs = [HumanMessage(content=query)]
    config = {
        "recursion_limit": 50
    }
    
    # msg = message.content
    result = app.invoke({"messages": inputs}, config)
    #print("result: ", result)

    msg = result["messages"][-1].content
    logger.info(f"msg: {msg}")

    reference = ""
    if reference_docs:
        reference = get_references(reference_docs)

    for i, doc in enumerate(reference_docs):
        logger.info(f"--> reference {i}: {doc}")
        
    reference = ""
    if reference_docs:
        reference = get_references(reference_docs)

    msg = extract_thinking_tag(msg, st)
    
    return msg+reference, reference_docs

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
                        status = status[status.find('<thinking>')+11:status.find('</thinking>')]
                        logger.info(f"agent_thinking: {status}")

                    if debug_mode=="Enable":
                        st.info(status)

                elif re['type'] == 'tool_use':                
                    logger.info(f"--> {re['type']}: name: {re['name']}, input: {re['input']}")

                    if debug_mode=="Enable":
                        st.info(f"{re['type']}: name: {re['name']}, input: {re['input']}")
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
    
    chat = get_chat()
    
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
                logger.info(f"tool name: {message['name']}, args: {message['args']}")
                # update_state_message(f"calling... {message['name']}", config)

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
    chat = get_chat()

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

####################### LangChain #######################
# Translation (English)
#########################################################

def translate_text(text, model_name):
    global llmMode
    llmMode = model_name

    chat = get_chat()

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

def translate_text_for_japanese(text, model_name):
    global llmMode
    llmMode = model_name

    chat = get_chat()

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
    
def check_grammer(text, model_name):
    global llmMode
    llmMode = model_name

    chat = get_chat()

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
        s3_key = f"{s3_prefix}/{file_name}"

        content_type = (
            "image/jpeg"
            if file_name.lower().endswith((".jpg", ".jpeg"))
            else "image/png"
        )

        s3_client.put_object(
            Bucket=bucketName, Key=s3_key, Body=file_bytes, ContentType=content_type
        )

        url = f"https://{bucketName}.s3.amazonaws.com/{s3_key}"
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
                
    image_obj = s3_client.get_object(Bucket=bucketName, Key=s3_prefix+'/'+object_name)
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
    multimodal = get_chat()
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
            raise Exception ("Not able to request to LLM")
        
    logger.info(f"extracted_text: {extracted_text}")
    if len(extracted_text)<10:
        extracted_text = "텍스트를 추출하지 못하였습니다."
    
    return extracted_text

def summary_image(img_base64, prompt):
    chat = get_chat()

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
