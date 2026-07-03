import pytest

from talk_to_your_docs.agent import docs_url_to_mcp_url, normalize_docs_url


def test_normalize_docs_url_adds_https():
    assert normalize_docs_url("mintlify.com/docs") == "https://mintlify.com/docs"


def test_docs_url_to_mcp_url_appends_mcp_to_docs_path():
    assert docs_url_to_mcp_url("https://mintlify.com/docs") == "https://mintlify.com/docs/mcp"


def test_docs_url_to_mcp_url_keeps_direct_mcp_endpoint():
    assert docs_url_to_mcp_url("https://docs.agno.com/mcp") == "https://docs.agno.com/mcp"


def test_normalize_docs_url_rejects_invalid_url():
    with pytest.raises(ValueError):
        normalize_docs_url("not a url")

