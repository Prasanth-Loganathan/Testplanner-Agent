"""
Command-line entry point.

    python main.py https://example.com            # run the agent, save the plan (.md) and test cases (.csv)
    python main.py https://example.com --dry-run  # only show what the tools see (no LLM, no key)
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import config


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a test plan for a website.")
    parser.add_argument("url", help="Start URL, e.g. https://example.com")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the page summary the agent would see, without calling the LLM")
    parser.add_argument("--quiet", action="store_true", help="Hide the agent's steps")
    args = parser.parse_args()

    url = args.url if args.url.startswith(("http://", "https://")) else "https://" + args.url

    if args.dry_run:
        from tools import analyze_page
        print(json.dumps(json.loads(analyze_page(url)), indent=2))
        return

    from agent import run_agent

    print(f"Analyzing {url} with {config.LLM_MODEL} ...")
    plan = run_agent(url, verbose=not args.quiet)

    out_dir = Path(config.OUTPUT_DIR)
    out_dir.mkdir(exist_ok=True)
    domain = urlparse(url).netloc.replace(":", "_") or "site"
    out_file = out_dir / f"test_plan_{domain}_{datetime.now():%Y%m%d_%H%M}.md"
    out_file.write_text(plan, encoding="utf-8")
    print(f"\nSaved: {out_file}")

    # Also save the test-case table as CSV (opens in Excel / Google Sheets).
    from export_csv import export_csv
    csv_file = export_csv(out_file)
    if csv_file:
        print(f"Saved: {csv_file}")
    else:
        print("No test-case table found in the plan, so no CSV was written.")


if __name__ == "__main__":
    main()
