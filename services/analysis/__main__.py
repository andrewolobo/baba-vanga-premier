"""Match analysis from the published call (docs/ANALYSIS_PLAN.md).

    python -m services.analysis pack --fixture 1234             # the evidence pack, as JSON
    python -m services.analysis analyse --fixture 1234 [5678]   # write it, print it, store nothing
    python -m services.analysis run [--dry-run]                 # today's calls, stored (the cycle step)
    python -m services.analysis rerun --fixture 1234            # retry a fallback before kick-off
    python -m services.analysis metrics [--since D] [--json F]  # how the writing is doing

All of them read whatever `BVP_DATABASE_URL` names, so a development check
against the production copy is one environment variable away
(ANALYSIS_PLAN.md section 3). `pack` and `metrics` only read; the others
call the configured Foundry deployment and spend tokens. `rerun` only turns a fallback into an
ok. It never writes a first analysis (that is the cycle's job) and never
replaces an ok.
"""

from __future__ import annotations

import argparse
import json
import sys

from engine import config, db
from services.analysis import jobs, llm, metrics
from services.analysis.analyse import ANALYSIS_PROMPT, SUMMARY_PROMPT, analyse
from services.analysis.pack import build_pack


def _report(fixture_id: int, outcome) -> dict:
    return {
        "fixture_id": fixture_id,
        "status": outcome.status,
        "prompt_versions": [SUMMARY_PROMPT, ANALYSIS_PROMPT],
        "summaries": {side: s.model_dump() for side, s in outcome.summaries.items()},
        "analysis": outcome.analysis.model_dump() if outcome.analysis else None,
        "attempts": [vars(a) for a in outcome.attempts],
        "warnings": outcome.warnings,
        "tokens": {"input": outcome.input_tokens, "output": outcome.output_tokens},
    }


def _summary(report: jobs.RunReport) -> int:
    tokens_in, tokens_out = report.tokens
    for fixture_id, outcome in sorted(report.outcomes.items()):
        print(f"  {fixture_id}: {outcome.status} ({len(outcome.attempts)} request(s))")
    for fixture_id, why in sorted(report.refused.items()):
        print(f"  {fixture_id}: no pack -- {why}")
    print(f"{report.count('ok')} ok, {report.count('fallback')} fallback, "
          f"{report.written} stored; tokens {tokens_in} in / {tokens_out} out")
    return 2 if report.count("fallback") or report.refused else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m services.analysis", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    pack = commands.add_parser("pack", help="print one fixture's evidence pack as JSON")
    pack.add_argument("--fixture", type=int, required=True)
    show = commands.add_parser("analyse", help="write the analysis and print it; stores nothing")
    show.add_argument("--fixture", type=int, nargs="+", required=True)
    run = commands.add_parser("run", help="analyse and store today's calls (the cycle step)")
    run.add_argument("--dry-run", action="store_true", help="ask the model, store nothing")
    rerun = commands.add_parser("rerun", help="retry a fallback, before kick-off")
    rerun.add_argument("--fixture", type=int, required=True)
    report = commands.add_parser("metrics", help="first-pass rate, rejections, fallbacks, cost")
    report.add_argument("--since", help="first day, YYYY-MM-DD (UTC)")
    report.add_argument("--until", help="last day, YYYY-MM-DD (UTC)")
    report.add_argument("--price-in", type=float, help="price per million input tokens")
    report.add_argument("--price-out", type=float, help="price per million output tokens")
    report.add_argument("--json", help="also write the summaries to this file")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")   # the prose is UTF-8 whatever the console is

    conn = db.connect()
    return {"pack": _pack, "analyse": _analyse, "run": _store, "rerun": _store,
            "metrics": _metrics}[args.command](conn, args)


def _metrics(conn, args) -> int:
    summaries = metrics.compute(conn, args.since, args.until, args.price_in, args.price_out)
    print(metrics.describe(summaries))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(summaries, f, indent=2)
    return 0


def _pack(conn, args) -> int:
    try:
        print(build_pack(conn, args.fixture).model_dump_json(indent=2))
    except (LookupError, ValueError) as exc:
        print(exc)
        return 2
    return 0


def _analyse(conn, args) -> int:
    api, cache, worst = llm.client(), {}, 0
    for fixture_id in args.fixture:
        try:
            built = build_pack(conn, fixture_id)
        except (LookupError, ValueError) as exc:
            print(exc)
            worst = 2
            continue
        outcome = analyse(built, api, cache)
        print(json.dumps(_report(fixture_id, outcome), indent=2, ensure_ascii=False))
        if outcome.status != "ok":
            worst = 2
    return worst


def _store(conn, args) -> int:
    db.migrate(conn)
    if args.command == "run":
        fixtures = jobs.pending(conn)
        if not fixtures:
            print("nothing to analyse")
            return 0
    else:
        why = jobs.rerunnable(conn, args.fixture)
        if why:
            print(why)
            return 2
        fixtures = [args.fixture]
    dry_run = getattr(args, "dry_run", False)
    code = _summary(jobs.run(conn, fixtures, llm.client(), llm_model=config.AZURE_MODEL,
                             dry_run=dry_run))
    if dry_run:
        print("(dry run -- nothing stored)")
    return code

if __name__ == "__main__":
    raise SystemExit(main())
