"""
Web UI for the Test Plan Agent, built with Streamlit.

Start it from the project folder:
    streamlit run app.py

How Streamlit works (useful to know when you change this file):
  * The whole script runs top to bottom on every click.
  * Anything that must survive a click (the generated plan) is kept in
    st.session_state, otherwise it would be lost on the next run.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

import config
from agent import run_agent
from export_csv import get_test_cases, rows_to_csv_text
from tools import analyze_page

st.set_page_config(page_title="Test Plan Agent", page_icon="🧪", layout="wide")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_url(raw: str) -> str | None:
    """Add https:// if missing; return None if it still isn't a valid web address."""
    raw = raw.strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    return raw if parsed.netloc and "." in parsed.netloc else None


def save_to_output(url: str, plan: str, csv_text: str) -> Path:
    """Keep a copy in output/, like the command line does."""
    out_dir = Path(config.OUTPUT_DIR)
    out_dir.mkdir(exist_ok=True)
    domain = urlparse(url).netloc.replace(":", "_") or "site"
    # Build the names as strings: Path.with_suffix() would treat ".com_2026..."
    # in "books.toscrape.com_2026..." as a file extension and cut it off.
    stem = f"test_plan_{domain}_{datetime.now():%Y%m%d_%H%M}"
    md_path = out_dir / f"{stem}.md"
    md_path.write_text(plan, encoding="utf-8")
    if csv_text:
        (out_dir / f"{stem}.csv").write_text(csv_text, encoding="utf-8-sig", newline="")
    return md_path


# ---------------------------------------------------------------------------
# Sidebar: settings for this run
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Settings")
    max_pages = st.slider("Pages the agent may open", 1, 8, config.MAX_PAGES,
                          help="More pages give a fuller plan but take longer.")
    max_steps = st.slider("Max agent steps", 2, 15, config.MAX_STEPS,
                          help="How many think → act rounds before it must answer.")
    separator = st.radio("CSV separator", ["Comma (,)", "Semicolon (;)"],
                         help="Choose semicolon if Excel with German settings "
                              "puts everything in one column.")
    delimiter = ";" if separator.startswith("Semicolon") else ","

    st.divider()
    st.caption("Model")
    st.code(f"{config.LLM_MODEL}\n{urlparse(config.LLM_BASE_URL).netloc}", language=None)
    st.caption("Change the model in the .env file, then restart the app.")


# ---------------------------------------------------------------------------
# Header and input
# ---------------------------------------------------------------------------

st.title("🧪 Test Plan Agent")
st.write("Enter a website. The agent opens a few of its pages, looks at the forms, "
         "buttons and links, and writes a QA test plan you can download as CSV.")

with st.form("run_form"):
    url_input = st.text_input("Website URL", placeholder="https://books.toscrape.com/",
                              key="url_input")
    col_run, col_preview, _ = st.columns([1, 1, 1])
    run_clicked = col_run.form_submit_button("Generate plan", type="primary",
                                             width="stretch")
    preview_clicked = col_preview.form_submit_button("Preview page",
                                                     width="stretch",
                                                     help="Shows what the agent sees on the "
                                                          "first page. No LLM call.")

if run_clicked or preview_clicked:
    url = normalize_url(url_input)
    if url is None:
        st.error("That doesn't look like a website address. Try something like "
                 "https://books.toscrape.com/")
        st.stop()

    # Apply this run's settings (tools.py and agent.py read them from config).
    config.MAX_PAGES = max_pages
    config.MAX_STEPS = max_steps

    if preview_clicked:
        with st.spinner(f"Opening {url} …"):
            summary = json.loads(analyze_page(url))
        if "error" in summary:
            st.error(summary["error"])
        else:
            st.subheader("What the agent sees on this page")
            st.json(summary)
        st.stop()

    # --- Run the agent, showing each step live ------------------------------
    steps: list[str] = []
    started = time.time()
    with st.status(f"Analyzing {url} …", expanded=True) as status:
        def show_step(text: str) -> None:
            steps.append(text)
            status.write(text)

        try:
            plan = run_agent(url, verbose=False, on_step=show_step)
        except SystemExit as exc:          # missing API key (raised in agent.py)
            status.update(label="Could not start the agent", state="error")
            st.error(str(exc))
            st.stop()
        except Exception as exc:           # LLM or network errors
            status.update(label="The agent stopped with an error", state="error")
            st.error(f"{type(exc).__name__}: {exc}")
            st.info("Check that your model is running (Ollama) or that your API key "
                    "and model name in .env are correct.")
            st.stop()

        seconds = time.time() - started
        status.update(label=f"Done in {seconds:.0f} seconds", state="complete", expanded=False)

    rows = get_test_cases(plan)
    saved = save_to_output(url, plan, rows_to_csv_text(rows, delimiter) if len(rows) > 1 else "")

    st.session_state["result"] = {
        "url": url,
        "plan": plan,
        "rows": rows,
        "steps": steps,
        "saved": str(saved),
        "seconds": seconds,
    }


# ---------------------------------------------------------------------------
# Results (kept in session_state so downloads don't wipe them)
# ---------------------------------------------------------------------------

result = st.session_state.get("result")

if not result:
    st.info("Results appear here. Good sites to practise on: books.toscrape.com, "
            "quotes.toscrape.com/login, the-internet.herokuapp.com")
    st.stop()

rows = result["rows"]
has_table = len(rows) > 1
df = pd.DataFrame(rows[1:], columns=rows[0]) if has_table else pd.DataFrame()

st.divider()
st.subheader(f"Test plan for {result['url']}")

# Summary numbers
pages_opened = sum(1 for s in result["steps"] if "analyze_page" in s)
priority_col = next((c for c in df.columns if c.lower() == "priority"), None)
high_count = int((df[priority_col].str.lower() == "high").sum()) if priority_col else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Test cases", len(df))
m2.metric("High priority", high_count)
m3.metric("Page lookups", pages_opened,
          help="analyze_page calls, including ones that failed or hit the page limit")
m4.metric("Time", f"{result['seconds']:.0f} s")

# Downloads
file_stem = Path(result["saved"]).name.removesuffix(".md")
d1, d2, _ = st.columns([1, 1, 1])
d1.download_button(
    "⬇ Download CSV",
    data=rows_to_csv_text(rows, delimiter).encode("utf-8-sig"),
    file_name=f"{file_stem}.csv",
    mime="text/csv",
    type="primary",
    disabled=not has_table,
    width="stretch",
)
d2.download_button(
    "⬇ Download Markdown",
    data=result["plan"].encode("utf-8"),
    file_name=f"{file_stem}.md",
    mime="text/markdown",
    width="stretch",
)
st.caption(f"Also saved to {result['saved']}")

tab_cases, tab_plan, tab_steps = st.tabs(["Test cases", "Full plan", "Agent steps"])

with tab_cases:
    if not has_table:
        st.warning("The model didn't write a test-case table, so there's nothing to export. "
                   "Try again, or switch to a larger model in .env.")
    else:
        filtered = df
        filter_cols = [c for c in df.columns if c.lower() in ("priority", "type")]
        if filter_cols:
            fcols = st.columns(len(filter_cols))
            for col, name in zip(fcols, filter_cols):
                options = sorted(v for v in df[name].unique() if v)
                chosen = col.multiselect(name, options, default=options, key=f"filter_{name}")
                filtered = filtered[filtered[name].isin(chosen) | (filtered[name] == "")]
        st.dataframe(filtered, width="stretch", hide_index=True)
        st.caption(f"Showing {len(filtered)} of {len(df)} test cases. "
                   "Filters only change this view; the CSV always has all of them.")

with tab_plan:
    st.markdown(result["plan"])

with tab_steps:
    st.write("Each line is one tool call the LLM asked for. This is the agent loop from agent.py.")
    for s in result["steps"]:
        st.code(s, language=None)
