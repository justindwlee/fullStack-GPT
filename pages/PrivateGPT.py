import streamlit as st
from langchain.chat_models import ChatOllama
from langchain.document_loaders import UnstructuredFileLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import OllamaEmbeddings, CacheBackedEmbeddings
from langchain.storage import LocalFileStore
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain.callbacks.base import BaseCallbackHandler
from langchain.memory import ConversationBufferWindowMemory

st.set_page_config(page_title="PrivateGPT", page_icon="❗")

class ChatCallbackHandler(BaseCallbackHandler):

    message = ""
    

    def on_llm_start(self, *args, **kwargs):
        self.message_box = st.empty()

    def on_llm_end(self, *args, **kwargs):
        save_message(self.message, "ai")

    def on_llm_new_token(self, token, *args, **kwargs):
        self.message += token
        self.message_box.markdown(self.message)
        

llm = ChatOllama(
    model="mistral:latest",
    temperature=0.1,
    streaming=True,
    callbacks=[
        ChatCallbackHandler(),
    ]
)

#Created a separate llm for memory, so it would not invoke callbacks when summarizing the history of the chat
memory_llm = ChatOllama(
    model="mistral:latest",
    temperature=0.1,
)


@st.cache_resource(show_spinner="Embedding file...")
def embed_file(file):
    file_content = file.read()
    file_path = f"./.cache/private_files/{file.name}"
    with open(file_path, "wb") as f:
        f.write(file_content)

    cache_dir = LocalFileStore(f"./.cache/private_embeddings/{file.name}")

    splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=600,
        chunk_overlap=100,
    )

    loader = UnstructuredFileLoader(file_path)
    docs = loader.load_and_split(text_splitter=splitter)

    embeddings = OllamaEmbeddings(
        model="mistral:latest"
    )
    cached_embeddings = CacheBackedEmbeddings.from_bytes_store(embeddings, cache_dir)

    vectorstore = Chroma.from_documents(docs, cached_embeddings)
    retriever = vectorstore.as_retriever()
    return retriever

def load_memory(_):
    return memory.load_memory_variables({})["history"]

def save_message(message, role):
    st.session_state["messages"].append({"message": message, "role": role})

def send_message(message, role, save=True):
    with st.chat_message(role):
        st.markdown(message)
    if save:
        save_message(message, role)


def paint_history():
    for message in st.session_state["messages"]:
        send_message(
            message["message"], 
            message["role"], 
            save=False
        )

def format_docs(docs):
    return "\n\n".join(document.page_content for document in docs)

def invoke_chain(message):
    result = chain.invoke(message)
    memory.save_context(
        {"input": message},
        {"output": result.content}
    )



prompt = ChatPromptTemplate.from_messages([
    ("system",
    """
    Answer the question using ONLY the following context. If you don't know the answer just say you don't know. DON't make anything up.
    If the user tells you anything about himself, such as his name, try to remember his personal information so you can give a friendly impression.

    Context: {context}
    """
    ),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{question}")
])



st.title("PrivateGPT")

st.markdown(
    """
    Welcome!
            
    Use this chatbot to ask questions to an AI about your files!
            
    Upload the files on the sidebar.
"""
)

with st.sidebar:
    file = st.file_uploader(
        "Upload a .txt .pdf or .docx file", type=["pdf", "txt", "docx"]
    )

if file:
    retriever = embed_file(file)
    send_message("Ask anything about the file you uploaded!", "ai", save=False)
    paint_history()
    message = st.chat_input("Ask anything about your file...")
    if message:
        memory = st.session_state.memory
        send_message(message, "human")
        chain = {
            "context": retriever | RunnableLambda(format_docs),
            "history": load_memory,
            "question": RunnablePassthrough()
        } | prompt | llm
        with st.chat_message("ai"):
            invoke_chain(message)
else:
    st.session_state["messages"] = []
    st.session_state.memory = ConversationBufferWindowMemory(
        return_messages=True,
        k=6,
    )



