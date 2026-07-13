import uuid
from typing import Any

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from langgraph_backend_rag_yt import (
    chatbot,
    retrieve_all_threads,
    ingest_pdf,
    ingest_youtube,
    thread_document_metadata,
)

import logging
import traceback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("streamlit_frontend")

# =========================================================
# Utilities
# =========================================================

def generate_thread_id() -> str:
    return f"{st.session_state['user_id']}::{uuid.uuid4()}"


def add_thread(thread_id: str) -> None:
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


def load_conversation(thread_id: str) -> list:
    """Load LangGraph messages saved for a thread."""

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    state = chatbot.get_state(config=config)
    return state.values.get("messages", [])


def convert_messages_for_ui(messages: list) -> list[dict[str, str]]:
    """
    Convert LangChain messages into Streamlit-compatible chat history.

    Tool messages and internal messages are intentionally excluded.
    """

    ui_messages = []

    for message in messages:
        if isinstance(message, HumanMessage):
            content = extract_text_content(message.content)

            if content:
                ui_messages.append(
                    {
                        "role": "user",
                        "content": content,
                    }
                )

        elif isinstance(message, AIMessage):
            content = extract_text_content(message.content)

            if content:
                ui_messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                    }
                )

    return ui_messages


def extract_text_content(content: Any) -> str:
    """
    Normalize LangChain message content into plain text.

    Some providers return strings, while others return content-block lists.
    """

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if isinstance(block, str):
                text_parts.append(block)

            elif isinstance(block, dict):
                text = block.get("text")

                if isinstance(text, str):
                    text_parts.append(text)

        return "".join(text_parts)

    return str(content) if content is not None else ""


def switch_thread(thread_id: str) -> None:
    """Switch the active conversation and load its saved messages."""

    st.session_state["thread_id"] = thread_id

    saved_messages = load_conversation(thread_id)

    st.session_state["message_history"] = convert_messages_for_ui(
        saved_messages
    )

    st.session_state["ingested_docs"].setdefault(
        str(thread_id),
        {},
    )


def reset_chat() -> None:
    """Create and activate a new chat thread."""

    new_thread_id = generate_thread_id()

    st.session_state["thread_id"] = new_thread_id
    st.session_state["message_history"] = []

    add_thread(new_thread_id)

    st.session_state["ingested_docs"].setdefault(
        new_thread_id,
        {},
    )


# =========================================================
# Session initialization
# =========================================================

if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())

user_id = st.session_state["user_id"]


if "message_history" not in st.session_state:
    st.session_state["message_history"] = []


if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = generate_thread_id()


if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = retrieve_all_threads(user_id)


if "ingested_docs" not in st.session_state:
    st.session_state["ingested_docs"] = {}

if "pdf_uploader_versions" not in st.session_state:
    st.session_state["pdf_uploader_versions"] = {}


add_thread(st.session_state["thread_id"])

thread_key = str(st.session_state["thread_id"])

if thread_key not in st.session_state["pdf_uploader_versions"]:
    st.session_state["pdf_uploader_versions"][thread_key] = 0

thread_docs = st.session_state["ingested_docs"].setdefault(
    thread_key,
    {},
)
# Thread-specific YouTube URL state
youtube_url_key = f"youtube-url-{thread_key}"

if youtube_url_key not in st.session_state:
    st.session_state[youtube_url_key] = ""


# =========================================================
# Sidebar
# =========================================================

st.sidebar.title("Agentic RAG Chatbot...")


if st.sidebar.button(
    "New Chat",
    use_container_width=True,
    # type="primary",
):
    reset_chat()
    st.rerun()


# -------------------- Current document --------------------

backend_doc_metadata = thread_document_metadata(thread_key)

if backend_doc_metadata:
    source_type = backend_doc_metadata.get("source_type")

    if source_type == "youtube":
        st.sidebar.success(
            "YouTube video indexed\n\n"
            f"Video ID: `{backend_doc_metadata.get('video_id')}`\n\n"
            f"{backend_doc_metadata.get('chunks', 0)} chunks from "
            f"{backend_doc_metadata.get('segments', 0)} transcript segments"
        )

    else:
        st.sidebar.success(
            f"Using `{backend_doc_metadata.get('filename')}`\n\n"
            f"{backend_doc_metadata.get('chunks', 0)} chunks from "
            f"{backend_doc_metadata.get('documents', 0)} pages"
        )

else:
    st.sidebar.info(
        "No PDF or YouTube video indexed for this chat."
    )


# -------------------- PDF uploader --------------------

uploaded_pdf = st.sidebar.file_uploader(
    "Upload a PDF for this chat...",
    type=["pdf"],
    key=(
        f"pdf-uploader-{thread_key}-"
        f"{st.session_state['pdf_uploader_versions'][thread_key]}"
    ),
)

if uploaded_pdf is not None:
    already_processed = uploaded_pdf.name in thread_docs

    if already_processed:
        st.sidebar.info(
            f"`{uploaded_pdf.name}` is already processed for this chat."
        )

    else:
        try:
            with st.sidebar.status(
                "Indexing PDF...",
                expanded=True,
            ) as status_box:

                summary = ingest_pdf(
                    file_bytes=uploaded_pdf.getvalue(),
                    thread_id=thread_key,
                    filename=uploaded_pdf.name,
                )

                # The backend currently supports one active retriever
                # per thread. Clear old UI metadata to match that behavior.
                thread_docs.clear()
                thread_docs[uploaded_pdf.name] = summary

                status_box.update(
                    label="PDF indexed",
                    state="complete",
                    expanded=False,
                )

            st.rerun()

        except Exception as error:
            st.sidebar.error(
                f"Failed to index the PDF: {error}"
            )


# -------------------- YouTube video --------------------

youtube_url = st.sidebar.text_input(
    "YouTube Video URL",
    placeholder="https://www.youtube.com/watch?v=...",
    key=youtube_url_key,
)

process_youtube = st.sidebar.button(
    "Process YouTube Video",
    use_container_width=True,
    key=f"process-youtube-{thread_key}",
)

if process_youtube:
    if not youtube_url.strip():
        st.sidebar.warning(
            "Please enter a YouTube video URL."
        )

    else:
        try:
            with st.sidebar.status(
                "Processing YouTube video...",
                expanded=True,
            ) as status_box:
                # st.sidebar.status("ingesting youtube video url...")
                logger.info("Calling backend YouTube ingestion function")
                summary = ingest_youtube(
                    youtube_url=youtube_url.strip(),
                    thread_id=thread_key,
                )

                thread_docs.clear()
                thread_docs[
                    f"youtube::{summary['video_id']}"
                ] = summary

                status_box.update(
                    label="YouTube video indexed",
                    state="complete",
                    expanded=False,
                )

            st.sidebar.success(
                f"Transcript indexed into "
                f"{summary.get('chunks', 0)} chunks."
            )

             # Clear the PDF uploader after YouTube becomes active
            st.session_state["pdf_uploader_versions"][thread_key] += 1

            st.rerun()

        except Exception as error:
            st.sidebar.error(
                f"Failed to process YouTube video: {error}"
            )

# -------------------- Conversations --------------------

st.sidebar.header("My Conversations")

threads = list(reversed(st.session_state["chat_threads"]))

if not threads:
    st.sidebar.write("No past conversations yet.")

else:
    for index, thread_id in enumerate(threads, start=1):
        is_current_thread = (
            str(thread_id) == str(st.session_state["thread_id"])
        )

        button_label = (
            f"Current chat"
            if is_current_thread
            else f"Conversation {len(threads) - index + 1}"
        )

        if st.sidebar.button(
            button_label,
            key=f"side-thread-{thread_id}",
            use_container_width=True,
            disabled=is_current_thread,
        ):
            switch_thread(thread_id)
            st.rerun()


# =========================================================
# Main UI
# =========================================================

st.title("Agentic RAG Chatbot")


# -------------------- Render chat history --------------------

for message in st.session_state["message_history"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# -------------------- User input --------------------

user_input = st.chat_input(
    "Ask about your PDF or anything else"
)


if user_input:
    st.session_state["message_history"].append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_input)


    config = {
        "configurable": {
            "thread_id": thread_key,
        },
        "metadata": {
            "thread_id": thread_key,
        },
        "run_name": "chat_turn",
    }


    with st.chat_message("assistant"):
        status_holder = {
            "box": None,
            "tool_names": [],
        }


        def ai_only_stream():
            for message_chunk, metadata in chatbot.stream(
                {
                    "messages": [
                        HumanMessage(content=user_input)
                    ]
                },
                config=config,
                stream_mode="messages",
            ):
                # Tool execution output
                if isinstance(message_chunk, ToolMessage):
                    tool_name = (
                        getattr(message_chunk, "name", None)
                        or "tool"
                    )

                    if tool_name not in status_holder["tool_names"]:
                        status_holder["tool_names"].append(tool_name)

                    if status_holder["box"] is None:
                        status_holder["box"] = st.status(
                            f"Using `{tool_name}`...",
                            expanded=True,
                        )
                    else:
                        status_holder["box"].update(
                            label=f"Using `{tool_name}`...",
                            state="running",
                            expanded=True,
                        )

                    continue

                # Only stream messages generated by chat_node.
                graph_node = metadata.get("langgraph_node")

                if graph_node and graph_node != "chat_node":
                    continue

                if isinstance(message_chunk, AIMessage):
                    text = extract_text_content(
                        message_chunk.content
                    )

                    if text:
                        yield text


        try:
            ai_message = st.write_stream(ai_only_stream())

            # st.write_stream returns the complete string when
            # the generator produces text-only output.
            if not isinstance(ai_message, str):
                ai_message = extract_text_content(ai_message)

            if not ai_message:
                ai_message = (
                    "I could not generate a response. "
                    "Please try again."
                )

            if status_holder["box"] is not None:
                tools_used = ", ".join(
                    status_holder["tool_names"]
                )

                status_holder["box"].update(
                    label=f"Tool finished: {tools_used}",
                    state="complete",
                    expanded=False,
                )

        except Exception as error:
            ai_message = f"An error occurred: {error}"

            st.error(ai_message)

            if status_holder["box"] is not None:
                status_holder["box"].update(
                    label="Tool execution failed",
                    state="error",
                    expanded=True,
                )


    st.session_state["message_history"].append(
        {
            "role": "assistant",
            "content": ai_message,
        }
    )


# -------------------- Current document caption --------------------

source_meta = thread_document_metadata(thread_key)

if source_meta:
    if source_meta.get("source_type") == "youtube":
        st.caption(
            f"YouTube video indexed · "
            f"Video ID: {source_meta.get('video_id')} · "
            f"{source_meta.get('chunks', 0)} chunks"
        )

    else:
        st.caption(
            f"PDF indexed: {source_meta.get('filename')} · "
            f"{source_meta.get('chunks', 0)} chunks · "
            f"{source_meta.get('documents', 0)} pages"
        )