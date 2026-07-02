from __future__ import annotations

import requests

# Wikipedia REST API — summary endpoint
# Docs: https://en.wikipedia.org/api/rest_v1/#/Page%20content/get_page_summary__title_
_API = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"

# Search endpoint to resolve free-text queries to canonical page titles
_SEARCH = "https://{lang}.wikipedia.org/w/api.php"

_TIMEOUT = 10  # seconds


def search_wikipedia(query: str, language: str = "en") -> dict:
    """Search Wikipedia and return a summary for the best matching article.

    Parameters
    ----------
    query:
        Free-text search term.
    language:
        Wikipedia language code, e.g. ``"en"`` or ``"de"``.

    Returns
    -------
    dict
        ``{"title", "summary", "url"}`` on success, or ``{"error": "..."}``
        on failure / disambiguation.
    """
    lang = language or "en"

    # Step 1: resolve the query to a canonical page title via the search API.
    try:
        search_resp = requests.get(
            _SEARCH.format(lang=lang),
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 1,
                "format": "json",
            },
            timeout=_TIMEOUT,
            headers={"User-Agent": "ochat/1.0"},
        )
        search_resp.raise_for_status()
        results = search_resp.json().get("query", {}).get("search", [])
    except requests.RequestException as exc:
        return {"error": f"Wikipedia search request failed: {exc}"}
    except Exception as exc:
        return {"error": f"Wikipedia search error: {exc}"}

    if not results:
        return {"error": f"No Wikipedia page found for '{query}'"}

    title = results[0]["title"]

    # Step 2: fetch the summary for the resolved title.
    try:
        summary_resp = requests.get(
            _API.format(lang=lang, title=requests.utils.quote(title, safe="")),
            timeout=_TIMEOUT,
            headers={"User-Agent": "ochat/1.0"},
        )
        summary_resp.raise_for_status()
        data = summary_resp.json()
    except requests.RequestException as exc:
        return {"error": f"Wikipedia summary request failed: {exc}"}
    except Exception as exc:
        return {"error": f"Wikipedia summary error: {exc}"}

    page_type = data.get("type", "")
    if page_type == "disambiguation":
        return {
            "error": f"'{title}' is a disambiguation page — please be more specific",
            "suggestions": [e.get("title") for e in data.get("pages", [])],
        }

    extract = data.get("extract") or data.get("extract_html") or ""
    return {
        "title": data.get("title", title),
        "summary": extract,
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
    }
