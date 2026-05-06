"""Web search tool for the personal agent, backed by Tavily."""

import os
from typing import List

from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search the web for recent information matching the query.
    Returns a list of results with title, URL, and a short excerpt."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return (
            "Web search is unavailable: TAVILY_API_KEY is not set. "
            "Add it to your .env file and restart."
        )

    try:
        from tavily import TavilyClient
    except ImportError:
        return "Web search is unavailable: install tavily-python (pip install tavily-python)."

    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, max_results=5, search_depth="basic")

    results = response.get("results", [])
    if not results:
        return f"No web results found for: {query}"

    lines = []
    for r in results:
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        snippet = r.get("content", "").strip()[:300]
        lines.append(f"**{title}**\n{url}\n{snippet}")

    return "\n\n---\n\n".join(lines)


def get_web_search_tools() -> List:
    return [web_search]
