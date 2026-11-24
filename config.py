"""
Settings for the agent, read from the .env file.

Change values in .env (not here) to switch model or provider.
Groq, Ollama and OpenAI all speak the same "OpenAI-compatible" API,
so only these three values decide which LLM you talk to.
"""

import os

from dotenv import load_dotenv

# Reads .env in the project folder into os.environ.
# override=True: values in .env win over variables already set in the terminal.
load_dotenv(override=True)

# --- LLM connection -------------------------------------------------------
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:latest")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

# --- Agent limits ---------------------------------------------------------
# MAX_STEPS: how many think -> act rounds the agent may take before it must answer.
# MAX_PAGES: how many pages of the website the agent may open in total.
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "4"))

# --- Web fetching ---------------------------------------------------------
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
USER_AGENT = os.getenv("USER_AGENT", "TestPlanAgent/0.1 (learning project)")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")

# Column separator for the CSV export. Excel with German regional settings
# expects ";" (set CSV_DELIMITER=; in .env if everything lands in one column).
CSV_DELIMITER = os.getenv("CSV_DELIMITER", ",")
