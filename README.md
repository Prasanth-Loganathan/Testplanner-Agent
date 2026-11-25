# Test Plan Agent

A small AI agent that opens a website, inspects its pages (forms, fields, buttons,
links) and writes a QA test plan in Markdown.

It is written without an agent framework on purpose, so you can read every line
and see how an agent works: the LLM decides which tool to call, Python runs the
tool, and the result goes back to the LLM until it writes the plan.

```
you ──url──▶ app.py (web UI) ─┐
             main.py (CLI) ───┴─▶ agent.py (loop) ◀──▶ LLM (Groq / Ollama)
                                       │
                                       ▼
                                   tools.py  ──▶ website (requests + BeautifulSoup)
                                       │
                                       ▼
                    output/test_plan_<site>.md  +  .csv (export_csv.py)
```

## Files

| File | What it does | Good first change |
|------|--------------|-------------------|
| `app.py` | Web UI (Streamlit): enter a URL, watch the steps, download CSV / Markdown | Add a "Run again" button |
| `main.py` | Command line: reads the URL, runs the agent, saves the plan | Add a `--pages` option |
| `export_csv.py` | Turns the test-case table into CSV | Map columns for a Jira/Xray import |
| `agent.py` | The agent loop: LLM → tool → LLM → … → answer | Print token usage per step |
| `tools.py` | What the agent can do: analyze a page, list links | Add a new tool |
| `prompts.py` | The instructions and the test plan template | Change the output format |
| `config.py` | Settings loaded from `.env` | Add a new setting |
| `tests/test_tools.py` | Unit tests for the HTML parsing (no network) | Add a test for your new tool |

## Setup in VS Code (Windows)

1. Unzip the folder and open it: **File → Open Folder…**
2. Open a terminal: **Terminal → New Terminal**, then create a virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   If PowerShell blocks the activate script, run
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.
3. Pick the interpreter: **Ctrl+Shift+P → Python: Select Interpreter → .venv**
4. Copy `.env.example` to `.env` and paste your Groq API key into `LLM_API_KEY`.
   Get a free key at https://console.groq.com/keys

## Run the web app

```powershell
streamlit run app.py
```

Your browser opens at http://localhost:8501. Enter a website and click
**Generate plan**. You'll see each agent step live, then the test cases as a
filterable table, the full plan, and buttons to **download CSV** or Markdown.
**Preview page** shows what the agent sees on the first page, without calling
the LLM. Stop the app with **Ctrl+C** in the terminal.

Tip: Streamlit re-runs `app.py` from top to bottom on every click. That's why the
result is kept in `st.session_state`. Read the comments in `app.py` to see how.

## Run it from the command line

```powershell
# 1. See what the agent "sees" on a page. No LLM call and no key needed.
python main.py https://books.toscrape.com/ --dry-run

# 2. Run the full agent. The plan is saved in the output/ folder.
python main.py https://books.toscrape.com/

# 3. Run the unit tests.
pytest
```

Good practice sites: `https://books.toscrape.com/`, `https://quotes.toscrape.com/login`,
`https://the-internet.herokuapp.com/`, `https://www.saucedemo.com/`.

**Debugging:** the **Run and Debug** panel has two ready launch configs.
Put a breakpoint inside the `for step in ...` loop in `agent.py` and inspect
`messages` to see the whole conversation between the agent and the LLM.

## Use Ollama instead of Groq (free, offline)

Install Ollama, run `ollama pull llama3.1`, then in `.env` switch to the Ollama
block shown in `.env.example`. Nothing else changes, because both speak the
OpenAI-compatible API.

## Exercises (in rough order of difficulty)

1. **Change the output.** In `prompts.py`, ask for test cases in Gherkin
   (Given / When / Then) instead of a table.
2. **Add a setting.** Add `--pages` to `main.py` that overrides `config.MAX_PAGES`.
3. **Add a tool.** Write `check_broken_links(url)` in `tools.py` that sends a HEAD
   request to each internal link and reports non-200 responses. Register it in
   `TOOL_SCHEMAS` and `TOOL_FUNCTIONS`, and add a unit test.
4. **Structured output.** Ask the LLM for JSON test cases, validate them with a
   Pydantic model, and also export them to CSV for Jira or Excel.
5. **JavaScript sites.** `requests` only sees the HTML the server sends, so
   single-page apps (React, Angular) look almost empty. Replace `fetch_html` with
   Playwright (`page.content()` after `page.goto(url)`).
6. **Generate code.** Add a second step that turns each High-priority test case
   into a Playwright Python test file.
7. **Rebuild it with LangGraph.** Re-create `agent.py` as a LangGraph graph and
   compare. You'll see the same loop with state and checkpoints added.
8. **Evaluate it.** Write a checklist of what a good plan for one site must contain
   and score each run automatically. This is how real teams test LLM apps.

## Known limits

- Only static HTML is read (see exercise 5).
- Pages behind a login are not reachable.
- The LLM can still invent details. The prompt asks it to label assumptions,
  but always review the plan before using it.
- Be polite to websites: keep `MAX_PAGES` small, and test only sites you are
  allowed to test.
