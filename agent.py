"""
The agent loop, written by hand so you can see every step.

An "agent" is just this loop:
    1. Send the conversation + tool descriptions to the LLM.
    2. If the LLM asks for tools -> run them, add the results, go to 1.
    3. If the LLM answers with text -> that's the final result.

Frameworks like LangGraph and CrewAI wrap this same loop.
Set a breakpoint inside run_agent() in VS Code to watch it happen.
"""

import json
from typing import Callable

from openai import OpenAI

import config
import prompts
from tools import TOOL_FUNCTIONS, TOOL_SCHEMAS, reset_visited


def make_client() -> OpenAI:
    if not config.LLM_API_KEY:
        raise SystemExit(
            "LLM_API_KEY is empty. Copy .env.example to .env and put your Groq key in it "
            "(or see README for Ollama)."
        )
    return OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)


def call_tool(name: str, raw_arguments: str) -> str:
    """Run one tool the LLM asked for and return its result as text."""
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return json.dumps({"error": f"Unknown tool '{name}'"})
    try:
        arguments = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "Tool arguments were not valid JSON"})
    try:
        return function(**arguments)
    except TypeError as exc:  # wrong or missing arguments
        return json.dumps({"error": f"Bad arguments for {name}: {exc}"})


def run_agent(url: str, verbose: bool = True,
              on_step: Callable[[str], None] | None = None) -> str:
    """
    Run the agent on one website and return the Markdown test plan.

    on_step: optional function called with a short message at every step.
             The web UI (app.py) uses it to show progress live; the
             command line just prints.
    """
    def log(text: str) -> None:
        if verbose:
            print(f"  {text}")
        if on_step:
            on_step(text)

    client = make_client()
    reset_visited()

    system = prompts.SYSTEM_PROMPT.format(max_pages_minus_one=max(config.MAX_PAGES - 1, 0))
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompts.USER_PROMPT.format(url=url)},
    ]

    for step in range(1, config.MAX_STEPS + 1):
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=config.LLM_TEMPERATURE,
        )
        message = response.choices[0].message

        # No tool calls -> the LLM has written its final answer.
        if not message.tool_calls:
            log(f"step {step}: writing the test plan")
            return message.content or ""

        # Keep the assistant's tool request in the history (the API requires it).
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in message.tool_calls
            ],
        })

        # Run each requested tool and send its result back.
        for call in message.tool_calls:
            log(f"step {step}: {call.function.name}({call.function.arguments})")
            result = call_tool(call.function.name, call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    # Out of steps: ask for the final answer without tools.
    log("step limit reached, asking for the final test plan")
    messages.append({"role": "user", "content": prompts.FINISH_NOW_PROMPT})
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=config.LLM_TEMPERATURE,
    )
    return response.choices[0].message.content or ""
