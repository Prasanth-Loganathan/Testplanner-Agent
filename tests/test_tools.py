"""
Unit tests for the parsing code. No network and no LLM needed.

Run:  pytest
"""

import json

import config
import tools

SAMPLE_HTML = """
<html>
  <head>
    <title>Demo Shop</title>
    <meta name="description" content="A demo shop for testing">
  </head>
  <body>
    <h1>Welcome</h1>
    <h2>Sign in</h2>
    <form action="/login" method="post">
      <input type="email" name="email" required placeholder="you@example.com">
      <input type="password" name="password" required>
      <input type="hidden" name="csrf" value="x">
      <button type="submit">Log in</button>
    </form>
    <input type="search" name="q">
    <a href="/products">Products</a>
    <a href="/products#top">Products again</a>
    <a href="https://other-site.com/">External</a>
    <img src="a.png" alt="Logo">
    <img src="b.png">
  </body>
</html>
"""

URL = "https://shop.example.com/"


def test_summary_reads_title_and_headings():
    summary = tools.summarize_html(SAMPLE_HTML, URL)
    assert summary["title"] == "Demo Shop"
    assert summary["meta_description"] == "A demo shop for testing"
    assert summary["headings"] == ["Welcome", "Sign in"]


def test_summary_reads_form_fields_and_skips_hidden():
    form = tools.summarize_html(SAMPLE_HTML, URL)["forms"][0]
    assert form["method"] == "post"
    names = [f["name"] for f in form["fields"]]
    assert names == ["email", "password"]          # hidden csrf field is skipped
    assert all(f["required"] for f in form["fields"])


def test_summary_accessibility_and_security_hints():
    summary = tools.summarize_html(SAMPLE_HTML, URL)
    assert summary["images_total"] == 2
    assert summary["images_missing_alt"] == 1
    assert summary["has_search"] is True
    assert summary["uses_https"] is True
    assert "Log in" in summary["buttons"]


def test_internal_links_are_same_domain_and_unique():
    links = tools.internal_links_from_html(SAMPLE_HTML, URL)
    assert links == ["https://shop.example.com/products"]


def test_page_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(config, "MAX_PAGES", 1)
    monkeypatch.setattr(tools, "fetch_html", lambda url: SAMPLE_HTML)
    tools.reset_visited()

    first = json.loads(tools.analyze_page("https://shop.example.com/"))
    second = json.loads(tools.analyze_page("https://shop.example.com/products"))

    assert first["title"] == "Demo Shop"
    assert "Page limit" in second["error"]
