import uuid
import json
import streamlit as st
from langchain.llms import Bedrock
from langchain.vectorstores import FAISS
from langchain.embeddings import BedrockEmbeddings
from langchain.chat_models import BedrockChat
from langchain.schema import HumanMessage, AIMessage
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.memory.chat_message_histories import DynamoDBChatMessageHistory
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ChatSessionTable')

llm = Bedrock(model_id='anthropic.claude-instant-v1')
chat_model = BedrockChat(model_id="anthropic.claude-instant-v1", model_kwargs={"temperature":0.1})
embeddings = BedrockEmbeddings(model_id='amazon.titan-embed-text-v1')
vector_store = FAISS.load_local('./vector_db', embeddings)
response = None


# ------ User Input ------ #
with st.sidebar:
    st.title('Bedrock Chat')
    scan_params = {
        'TableName': 'ChatSessionTable',
        'ProjectionExpression': 'SessionId',
    }
    response = table.scan(**scan_params)
    session_ids = [i['SessionId'] for i in response['Items']]
    if "last_session_id" not in st.session_state and len(session_ids)>=1:
        st.session_state.last_session_id = session_ids[0]

    new_id = st.button('New Session')
    if new_id or len(session_ids)==0:
        sess_id = str(uuid.uuid4())[:8]
        st.session_state.last_session_id = sess_id
    session_ids = [st.session_state.last_session_id] + list(set(session_ids).difference([st.session_state.last_session_id]))
    sess_id = st.selectbox('Session ID', session_ids)

query = st.chat_input("Ask me about Amazon SageMaker...")

if query:
# --------- Chat --------- #
    with st.spinner('Generating...'):
        history = DynamoDBChatMessageHistory(table_name="ChatSessionTable", session_id=sess_id)
        memory_chain = ConversationBufferMemory(
            memory_key="chat_history", chat_memory=history, return_messages=True
        )
        qa = ConversationalRetrievalChain.from_llm(
            llm=llm, 
            retriever=vector_store.as_retriever(), 
            memory=memory_chain,
            verbose=False, 
            chain_type='stuff'
        )
        response = qa.run({'question': query})
    
data = table.get_item(Key={"SessionId": sess_id})
chat_history = data['Item']['History'] if 'Item' in data else []
messages = [m['data'] for m in chat_history]
with st.container():
    for message in messages:
        with st.chat_message(message['type']):
            st.write(message['content'].strip())