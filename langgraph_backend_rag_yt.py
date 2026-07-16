import os
import sqlite3
import tempfile
from typing import TypedDict, Annotated, Any, Dict, Optional

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.tools import TavilySearchResults

from langchain_community.vectorstores import FAISS
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_community.tools import tool

# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
# from langchain_ollama import ChatOllama

from langgraph.graph import StateGraph, START, END



# from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from dotenv import load_dotenv



from langgraph.prebuilt import ToolNode, tools_condition
import requests    


from langchain_huggingface import HuggingFaceEmbeddings

from youtube_loader import get_youtube_transcript

from functools import lru_cache

import streamlit as st


load_dotenv()

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")


# -------------------
# 1. LLM
# -------------------

# llm = ChatOllama(
#     # model="qwen2.5-coder:14b",
#     model="qwen3:4b",
#     temperature=0.2,
#     num_ctx=4096,
#     keep_alive="30m",
# )
llm = ChatGroq(
    # model="llama-3.1-8b-instant", 
    model = "llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.7, 
    max_tokens=1000
    )
# embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

@st.cache_resource(show_spinner="Loading embedding model...")
def get_embeddings() -> HuggingFaceEmbeddings:
    # print("[EMBEDDINGS] Loading embedding model...", flush=True)

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # print("[EMBEDDINGS] Model loaded successfully", flush=True)

    return embeddings

# llm = ChatGoogleGenerativeAI(
#     model="gemini-3.5-flash", 
# )
# -------------------
# 2. PDF retriever store (per thread)
# -------------------
_THREAD_RETRIEVERS: Dict[str, Any] = {}
_THREAD_METADATA: Dict[str, dict] = {}


def _get_retriever(thread_id: Optional[str]):
    """Fetch the retriever for a thread if available."""
    if thread_id and thread_id in _THREAD_RETRIEVERS:
        return _THREAD_RETRIEVERS[thread_id]
    return None


def ingest_pdf(file_bytes: bytes, thread_id: str, filename: Optional[str] = None) -> dict:
    """
    Build a FAISS retriever for the uploaded PDF and store it for the thread.

    Returns a summary dict that can be surfaced in the UI.
    """
    if not file_bytes:
        raise ValueError("No bytes received for ingestion.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(file_bytes)
        temp_path = temp_file.name

    try:
        loader = PyPDFLoader(temp_path)
        docs = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", " ", ""]
        )
        chunks = splitter.split_documents(docs)

        vector_store = FAISS.from_documents(chunks, get_embeddings())
        retriever = vector_store.as_retriever(
            search_type="similarity", search_kwargs={"k": 4}
        )

        thread_key = str(thread_id)

        _THREAD_RETRIEVERS[thread_key] = retriever

        _THREAD_METADATA[thread_key] = {
            "source_type": "pdf",
            "filename": filename or os.path.basename(temp_path),
            "documents": len(docs),
            "chunks": len(chunks),
        }

        return {
            "filename": filename or os.path.basename(temp_path),
            "documents": len(docs),
            "chunks": len(chunks),
        }
    finally:
        # The FAISS store keeps copies of the text, so the temp file is safe to remove.
        try:
            os.remove(temp_path)
        except OSError:
            pass


def ingest_youtube(
    youtube_url: str,
    thread_id: str,
) -> dict:
    transcript = get_youtube_transcript(youtube_url)

    transcript_text = transcript["text"]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.create_documents(
        [transcript_text]
    )

    vector_store = FAISS.from_documents(
        chunks,
        get_embeddings(),
    )

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4},
    )

    thread_key = str(thread_id)

    _THREAD_RETRIEVERS[thread_key] = retriever

    _THREAD_METADATA[thread_key] = {
        "source_type": "youtube",
        "video_id": transcript["video_id"],
        "segments": transcript["segments"],
        "chunks": len(chunks),
        "youtube_url": youtube_url,
    }

    # print("=" * 50)
    # print("VIDEO ID :", transcript["video_id"])
    # print("SEGMENTS :", transcript["segments"])
    # print("CHUNKS   :", len(chunks))
    # print("FAISS INDEX CREATED")
    # print("=" * 50)

    return {
        "video_id": transcript["video_id"],
        "segments": transcript["segments"],
        "chunks": len(chunks),
    }
# -------------------
# 2. Tools
# -------------------
# Tools
# search_tool = DuckDuckGoSearchRun(region="us-en")
search_tool = TavilySearchResults(max_results=3)

@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}
        
        return {"first_num": first_num, "second_num": second_num, "operation": operation, "result": result}
    except Exception as e:
        return {"error": str(e)}




@tool
def get_stock_price(symbol: str) -> str:
    """
    Fetch the latest stock price for a given stock symbol.
    """
    url = (
        f"https://www.alphavantage.co/query"
        f"?function=GLOBAL_QUOTE"
        f"&symbol={symbol}"
        f"&apikey={ALPHAVANTAGE_API_KEY}"
    )

    data = requests.get(url).json()

    quote = data.get("Global Quote", {})

    if not quote:
        return f"Could not fetch stock price for {symbol}."

    price = quote.get("05. price")
    date = quote.get("07. latest trading day")

    return f"The latest stock price of {symbol} is ${price} (as of {date})."

@tool
def rag_tool(query: str, thread_id: Optional[str] = None) -> dict:
    """
    Retrieve relevant information from the currently active indexed source.

    The active source is the most recently indexed PDF or YouTube video.
    Always include the thread_id when calling this tool.
    """

    if not thread_id:
        return {
            "error": "thread_id is required.",
            "query": query,
        }

    thread_key = str(thread_id)

    retriever = _THREAD_RETRIEVERS.get(thread_key)

    if retriever is None:
        return {
            "error": "No PDF or YouTube video is indexed for this chat.",
            "query": query,
        }

    result = retriever.invoke(query)

    return {
        "query": query,
        "context": [doc.page_content for doc in result],
        "metadata": [doc.metadata for doc in result],
        "source": _THREAD_METADATA.get(thread_key, {}),
    }



tools = [search_tool, get_stock_price, calculator, rag_tool]
llm_with_tools = llm.bind_tools(tools)


# -------------------
# 3. State
# -------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# -------------------
# 4. Nodes
# -------------------
def chat_node(state: ChatState, config=None):
    """LLM node that may answer or request a tool call."""
    thread_id = None
    if config and isinstance(config, dict):
        thread_id = config.get("configurable", {}).get("thread_id")

    system_message = SystemMessage(
        content=(
            "You are a helpful assistant. "
            "The current chat may contain an uploaded PDF or an indexed "
            "YouTube transcript. "

            "For questions about the PDF, document, YouTube video, transcript, "
            "speaker, or video content, call `rag_tool` and include the exact "
            f"thread_id `{thread_id}`. "

            "Answer using the retrieved context. "
            "If the answer is not present in the retrieved context, say that "
            "the answer was not found in the indexed source. "
            
            "You can also use web search, stock price, and calculator tools "
            "for unrelated questions."

            "if you do not have any question's answer, do the web search."
        )
    )

    messages = [system_message, *state["messages"]]
    response = llm_with_tools.invoke(messages, config=config)
    return {"messages": [response]}

tool_node = ToolNode(tools)
# -------------------
# 5. Checkpointer
# -------------------
conn = sqlite3.connect(database='chatbot.db', check_same_thread=False)
# Checkpointer
checkpointer = SqliteSaver(conn=conn)


# -------------------
# 6. Graph
# -------------------

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node('tools', tool_node)

graph.add_edge(START, 'chat_node')
graph.add_conditional_edges('chat_node',tools_condition)
graph.add_edge('tools', 'chat_node')
# graph.add_edge("chat_node", END)

chatbot = graph.compile(checkpointer=checkpointer)


# -------------------
# 7. Helper
# -------------------
def retrieve_all_threads(user_id: str) -> list:
    user_threads = []
    for checkpoint in checkpointer.list(None):
        thread_id = checkpoint.config['configurable']['thread_id']
        if thread_id.startswith(f"{user_id}::"):
            user_threads.append(thread_id)

    return user_threads

def thread_has_document(thread_id: str) -> bool:
    return str(thread_id) in _THREAD_RETRIEVERS


def thread_document_metadata(thread_id: str) -> dict:
    return _THREAD_METADATA.get(str(thread_id), {})

# from dotenv import load_dotenv
# import os

# load_dotenv()

# print(os.getenv("LANGSMITH_TRACING"))
# print(os.getenv("LANGSMITH_PROJECT"))
# print(os.getenv("LANGSMITH_API_KEY")[:10])


# from langsmith import traceable

# @traceable
# def test_trace(x):
#     return x + 1

# test_trace(10)