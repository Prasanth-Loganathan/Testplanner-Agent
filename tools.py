"""
Tools: the actions the agent is allowed to take.

Each tool is a plain Python function. The LLM never runs code itself:
it only *asks* for a tool by name with arguments, and agent.py calls
the matching function here and sends the result back.

To add a tool:
  1. Write a function below that returns a string (JSON is easiest).
  2. Describe it in TOOL_SCHEMAS so the LLM knows it exists.
  3. Add it to TOOL_FUNCTIONS so agent.py can call it.
"""

import json
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config


# ---------------------------------------------------------------------------
# Helpers (not tools): fetching and parsing HTML
# ---------------------------------------------------------------------------

def fetch_html(url: str) -> str:
    """Download a page and return its HTML. Raises on network/HTTP errors."""
    response = requests.get(
        url,
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def _clean(text: str, limit: int = 80) -> str:
    """Collapse whitespace and cut long text so we don't flood the LLM."""
    text = " ".join((text or "").split())
    return text[:limit]


def summarize_html(html: str, url: str) -> dict:
    """
    Turn raw HTML into a short, structured summary a tester cares about:
    headings, forms and their fields, buttons, links and basic a11y hints.

    This is pure (no network), which makes it easy to unit-test.
    """
    soup = BeautifulSoup(html, "html.parser")

    forms = []
    for form in soup.find_all("form"):
        fields = []
        for field in form.find_all(["input", "select", "textarea"]):
            if field.get("type") == "hidden":
                continue
            fields.append({
                "tag": field.name,
                "type": field.get("type", "text") if field.name == "input" else field.name,
                "name": field.get("name") or field.get("id") or "",
                "required": field.has_attr("required"),
                "placeholder": _clean(field.get("placeholder", ""), 40),
            })
        forms.append({
            "action": form.get("action", ""),
            "method": (form.get("method") or "get").lower(),
            "fields": fields,
        })

    buttons = [
        _clean(b.get_text() or b.get("value", "") or b.get("aria-label", ""), 40)
        for b in soup.find_all(["button"]) + soup.find_all("input", type=["submit", "button"])
    ]

    links = internal_links_from_html(html, url)

    images = soup.find_all("img")
    images_missing_alt = sum(1 for img in images if not img.get("alt"))

    meta_desc = soup.find("meta", attrs={"name": "description"})

    return {
        "url": url,
        "title": _clean(soup.title.get_text() if soup.title else "", 120),
        "meta_description": _clean(meta_desc.get("content", "") if meta_desc else "", 160),
        "headings": [_clean(h.get_text()) for h in soup.find_all(["h1", "h2", "h3"])][:15],
        "forms": forms[:5],
        "buttons": list(dict.fromkeys(b for b in buttons if b))[:20],  # unique, in page order
        "internal_links_sample": links[:15],
        "internal_links_total": len(links),
        "images_total": len(images),
        "images_missing_alt": images_missing_alt,
        "has_search": bool(soup.find("input", type="search")),
        "uses_https": urlparse(url).scheme == "https",
    }


def internal_links_from_html(html: str, url: str) -> list[str]:
    """Return unique links on the same domain as `url`, in page order."""
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(url).netloc
    seen, links = set(), []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"]).split("#")[0]
        parsed = urlparse(href)
        if parsed.scheme in ("http", "https") and parsed.netloc == base_domain and href not in seen:
            seen.add(href)
            links.append(href)
    return links


# ---------------------------------------------------------------------------
# Tools the agent can call
# ---------------------------------------------------------------------------

# Pages already opened in this run. The agent's page budget is enforced here,
# in code, rather than trusting the LLM to stop on its own.
_visited: set[str] = set()


def reset_visited() -> None:
    _visited.clear()


def analyze_page(url: str) -> str:
    """Tool: open one page and return its structured summary as JSON."""
    if url not in _visited and len(_visited) >= config.MAX_PAGES:
        return json.dumps({"error": f"Page limit of {config.MAX_PAGES} reached. Write the test plan now."})
    try:
        html = fetch_html(url)
    except requests.RequestException as exc:
        return json.dumps({"error": f"Could not open {url}: {exc}"})
    _visited.add(url)
    return json.dumps(summarize_html(html, url))


def list_internal_links(url: str, limit: int = 20) -> str:
    """Tool: list same-site links on a page so the agent can pick what to open next."""
    try:
        html = fetch_html(url)
    except requests.RequestException as exc:
        return json.dumps({"error": f"Could not open {url}: {exc}"})
    return json.dumps({"url": url, "links": internal_links_from_html(html, url)[:limit]})


# Descriptions the LLM reads to decide which tool to call (OpenAI tool format).
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_page",
            "description": "Open a web page and get its title, headings, forms with fields, "
                           "buttons, internal links and accessibility hints.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Full URL of the page"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_internal_links",
            "description": "List links on a page that stay on the same website.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL of the page"},
                    "limit": {"type": "integer", "description": "Max links to return (default 20)"},
                },
                "required": ["url"],
            },
        },
    },
]

# Name -> Python function. agent.py looks tools up here.
TOOL_FUNCTIONS = {
    "analyze_page": analyze_page,
    "list_internal_links": list_internal_links,
}
