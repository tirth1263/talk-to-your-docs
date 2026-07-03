"""Agent helpers for the Talk to Your Docs Streamlit app."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from textwrap import dedent
from urllib.parse import urlparse

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.mcp import MCPTools

DEFAULT_DOCS_URL = "https://mintlify.com/docs"
DEFAULT_MODEL_ID = "deepseek-ai/DeepSeek-V3-0324"


@dataclass(frozen=True)
class ChatMessage:
    """Small typed wrapper for passing recent Streamlit chat history."""

    role: str
    content: str


def normalize_docs_url(url: str) -> str:
    """Normalize a documentation URL while keeping subpaths such as /docs."""

    value = (url or "").strip()
    if not value:
        raise ValueError("Enter a documentation URL.")
    if any(character.isspace() for character in value):
        raise ValueError("Documentation URLs cannot contain spaces.")

    if "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid http(s) documentation URL.")

    return value.rstrip("/")


def docs_url_to_mcp_url(docs_url: str) -> str:
    """Convert a docs URL to the hosted search MCP URL used by Mintlify-style docs."""

    url = normalize_docs_url(docs_url)
    if url.endswith("/mcp") or url.endswith("/authed/mcp"):
        return url
    return f"{url}/mcp"


def format_chat_history(messages: Iterable[ChatMessage], limit: int = 6) -> str:
    """Format the latest chat turns as compact model context."""

    recent_messages = list(messages)[-limit:]
    if not recent_messages:
        return "No previous conversation."

    lines = []
    for message in recent_messages:
        role = "User" if message.role == "user" else "Assistant"
        lines.append(f"{role}: {message.content}")
    return "\n".join(lines)


async def ask_documentation_agent(
    *,
    question: str,
    docs_url: str,
    api_key: str,
    history: Iterable[ChatMessage] | None = None,
    model_id: str = DEFAULT_MODEL_ID,
) -> tuple[str, str]:
    """Ask the configured documentation MCP server using a Nebius-backed Agno agent."""

    if not api_key:
        raise ValueError("Add your Nebius API key before asking a question.")

    mcp_url = docs_url_to_mcp_url(docs_url)
    chat_context = format_chat_history(history or [])

    prompt = dedent(
        f"""
        Documentation source: {docs_url}
        MCP endpoint: {mcp_url}

        Recent conversation:
        {chat_context}

        User question:
        {question}
        """
    ).strip()

    mcp_tools = MCPTools(
        transport="streamable-http",
        url=mcp_url,
        refresh_connection=True,
    )
    await mcp_tools.connect()

    try:
        agent = Agent(
            name="Talk to Your Docs",
            model=Nebius(
                id=model_id,
                api_key=api_key,
            ),
            tools=[mcp_tools],
            instructions=dedent(
                """
                You answer questions by using the connected documentation MCP tools.
                Search and read the docs before giving specific technical guidance.
                Prefer concise, practical answers with source links when the tools
                return URLs. If the documentation does not contain the answer, say so
                clearly and suggest the closest relevant page or next step.
                """
            ).strip(),
            markdown=True,
        )
        response = await agent.arun(input=prompt)
        content = getattr(response, "content", None)
        if content is None:
            content = response
        return str(content), mcp_url
    finally:
        await mcp_tools.close()
