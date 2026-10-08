"""Ask the bot a version-specific coding question.

    python -m versionguard.ask "How do I add a row to a DataFrame?" --library pandas

The documentation is read from the copy of the library installed in the
current environment, so the answer is grounded in that exact version.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from versionguard.bot import Bot
from versionguard.llm import check_connection
from versionguard.store import load_api_docs


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("question")
    parser.add_argument("--library", required=True, help="distribution name, e.g. pandas")
    parser.add_argument("--version", help="expected version (checked against what is installed)")
    parser.add_argument("--docs", help="JSONL of documentation entries to use instead of the installed library")
    parser.add_argument("--model", help="Ollama model tag (default: OLLAMA_MODEL)")
    parser.add_argument("--retriever", choices=["vector", "bm25"], help="lookup method")
    parser.add_argument("--k", type=int, help="number of documentation entries to retrieve")
    parser.add_argument("--no-docs", action="store_true", help="answer without documentation lookup")
    parser.add_argument("--show-docs", action="store_true", help="print the retrieved entries in full")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--code", type=Path, help="Python source file to repair (requires --error-log)")
    parser.add_argument("--error-log", type=Path, help="failed build or execution log to use for repair")
    args = parser.parse_args(argv)
    if (args.code is None) != (args.error_log is None):
        parser.error("--code and --error-log must be supplied together")

    bot = Bot(model=args.model, retriever_kind=args.retriever, k=args.k)
    if not bot.llm.model.startswith("fake:"):
        status = check_connection(model=bot.llm.model)
        if not status["connected"]:
            print(f"Ollama is not reachable at {status['base_url']}: {status.get('error')}", file=sys.stderr)
            return 2
        if not status["is_configured_model_available"]:
            print(f"Model {bot.llm.model} is not pulled. Run: ollama pull {bot.llm.model}", file=sys.stderr)
            return 2

    try:
        docs = load_api_docs(args.docs) if args.docs else None
        code = args.code.read_text(encoding="utf-8") if args.code else None
        error_log = args.error_log.read_text(encoding="utf-8") if args.error_log else None
        answer = bot.ask(args.question, args.library, args.version, docs, use_docs=not args.no_docs,
                         code=code, error_log=error_log, program_name=args.code.name if args.code else "prog.py")
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(answer.as_dict(), indent=2))
        return 1 if answer.guard["status"] == "failed" else 0
    print(f"[{answer.library} {answer.version} | model {bot.llm.model}]\n")
    print(answer.text.strip())
    if answer.sources:
        print("\nDocumentation used:")
        for doc in answer.sources:
            print(f"  - {doc.qualname}{doc.signature[:90]}")
            if args.show_docs:
                print(f"      {doc.doc[:300]}")
    print(f"\nStatic guard: {answer.guard['status']} (does not run tests)")
    if answer.guard.get("reason"):
        print(answer.guard["reason"])
    for finding in answer.guard["findings"]:
        print(f"  {finding['code']}: {finding['message']}")
    return 1 if answer.guard["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
