from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from talk_to_your_docs.agent import (  # noqa: E402
    DEFAULT_DOCS_URL,
    DEFAULT_MODEL_ID,
    ChatMessage,
    ask_documentation_agent,
    docs_url_to_mcp_url,
)

load_dotenv()

EXAMPLE_QUESTIONS = [
    "How do I migrate documentation from my current platform to Mintlify?",
    "What are the key AI-native documentation features?",
    "How do I set up authentication?",
    "What are the best practices for documentation?",
]


def get_default_api_key() -> str:
    """Read an API key from Streamlit secrets or local environment variables."""

    try:
        return st.secrets.get("NEBIUS_API_KEY", "")
    except Exception:
        return os.getenv("NEBIUS_API_KEY", "")


def run_async(coro):
    """Run an async Agno/MCP request from Streamlit's synchronous render loop."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


st.set_page_config(
    page_title="Talk to Your Docs",
    page_icon=":books:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background: #f8faf9;
    }
    [data-testid="stSidebar"] {
        background: #101820;
    }
    [data-testid="stSidebar"] * {
        color: #f7fafc;
    }
    [data-testid="stSidebar"] input {
        color: #101820;
    }
    .hero-title {
        font-size: clamp(2.2rem, 5vw, 4.7rem);
        line-height: 1;
        font-weight: 800;
        letter-spacing: 0;
        margin-bottom: 0.75rem;
        color: #101820;
    }
    .hero-copy {
        max-width: 760px;
        color: #51606b;
        font-size: 1.08rem;
        line-height: 1.7;
        margin-bottom: 1.2rem;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        border: 1px solid #d5e3df;
        border-radius: 999px;
        padding: 0.35rem 0.75rem;
        color: #17483f;
        background: #edf8f4;
        font-size: 0.9rem;
        margin-bottom: 1.1rem;
    }
    .small-muted {
        color: #6a7882;
        font-size: 0.92rem;
    }
    div[data-testid="stChatMessage"] {
        border-radius: 8px;
        border: 1px solid #e3e8e5;
        background: #ffffff;
        box-shadow: 0 8px 24px rgba(16, 24, 32, 0.06);
    }
    .stButton > button {
        border-radius: 8px;
        border-color: #d5e3df;
        color: #101820;
        background: #ffffff;
        min-height: 2.7rem;
        text-align: left;
        white-space: normal;
    }
    .stButton > button:hover {
        border-color: #1f8a70;
        color: #0e5f4e;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Add your Nebius API key, choose a documentation URL, and ask me "
                "what you want to know. I will use the docs MCP server before answering."
            ),
        }
    ]

with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input(
        "Nebius API key",
        value=get_default_api_key(),
        type="password",
        placeholder="nbs_...",
        help="Stored only in this Streamlit session unless you provide it via environment secrets.",
    )
    docs_url = st.text_input(
        "Documentation URL",
        value=DEFAULT_DOCS_URL,
        placeholder="https://mintlify.com/docs",
        help="Use a docs URL or a direct MCP endpoint ending in /mcp.",
    )
    model_id = st.text_input(
        "Nebius model",
        value=DEFAULT_MODEL_ID,
        help="Default: DeepSeek-V3-0324 on Nebius AI Studio.",
    )

    try:
        st.caption(f"MCP endpoint: `{docs_url_to_mcp_url(docs_url)}`")
    except ValueError:
        st.caption("MCP endpoint: enter a valid documentation URL")

    st.divider()
    st.subheader("Example questions")
    selected_example = None
    for question in EXAMPLE_QUESTIONS:
        if st.button(question, use_container_width=True):
            selected_example = question

    st.divider()
    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.markdown(
    """
    <div class="status-pill">MCP documentation search + Nebius AI + Streamlit</div>
    <div class="hero-title">Talk to Your Docs</div>
    <div class="hero-copy">
        Ask natural-language questions about any MCP-enabled documentation site.
        The agent connects to the docs, searches the source material, and returns
        focused answers you can act on.
    </div>
    """,
    unsafe_allow_html=True,
)

chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

prompt = selected_example or st.chat_input("Ask a question about the documentation")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not api_key:
            answer = "Add your Nebius API key in the sidebar, then ask again."
            st.warning(answer)
        else:
            try:
                history = [
                    ChatMessage(role=item["role"], content=item["content"])
                    for item in st.session_state.messages[:-1]
                ]
                with st.spinner("Searching the documentation MCP server..."):
                    answer, mcp_url = run_async(
                        ask_documentation_agent(
                            question=prompt,
                            docs_url=docs_url,
                            api_key=api_key,
                            history=history,
                            model_id=model_id,
                        )
                    )
                st.markdown(answer)
                st.caption(f"Answered using `{mcp_url}`")
            except Exception as exc:
                answer = (
                    "I could not complete that request. Check the API key, model ID, "
                    "and whether the documentation site exposes a public MCP endpoint.\n\n"
                    f"`{exc}`"
                )
                st.error(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
