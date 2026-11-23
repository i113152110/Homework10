#!/usr/bin/env python3
"""
wiki_pipeline.py — LLM Wiki → 教學簡報 流程的「調度器」

這支程式不呼叫 LLM。LLM（Claude）負責「寫」的節點（討論稿、Wiki 頁面、簡報內容），
本程式負責其餘確定性的節點，並把每一次執行都記到 logs/runs.jsonl：

  extract : 取得資料   — 重用 HW3 data_update.py（PDF → data/processed/*.txt，--skip-embedding）
  check   : 檢查 Wiki  — wiki_lint.py（引文逐字比對、數字比對、連結、index、log、sha256）
  slides  : 產生簡報   — build_slides.py（Wiki → HTML）＋ 簡報檢查（數字溯源、頁面對應、覆蓋率）
  log     : 寫 wiki/log.md（用真實時間戳記）

用法
  python wiki_pipeline.py extract
  python wiki_pipeline.py check --label batch1-round1
  python wiki_pipeline.py slides --label deck-round1
  python wiki_pipeline.py log ingest ko-q4-2025 "batch 1：新增 source 頁，更新 concepts/volume ..."
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = "logs/runs.jsonl"


def cmd_extract(_: argparse.Namespace) -> int:
    return subprocess.call([sys.executable, "data_update.py", "--skip-embedding"], cwd=ROOT)


def cmd_check(a: argparse.Namespace) -> int:
    import wiki_lint
    res = wiki_lint.run(label=a.label, record=RUNS)
    return 0 if res["summary"]["passed"] else 1


def cmd_slides(a: argparse.Namespace) -> int:
    import build_slides
    return build_slides.main_with(label=a.label, record=RUNS)


def cmd_log(a: argparse.Namespace) -> int:
    ts = time.strftime("%Y-%m-%d %H:%M")
    entry = f"\n## [{ts}] {a.kind} | {a.ref}\n{a.note}\n"
    log = ROOT / "wiki" / "log.md"
    with log.open("a", encoding="utf-8") as f:
        f.write(entry)
    print(f"logged: [{ts}] {a.kind} | {a.ref}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("extract").set_defaults(fn=cmd_extract)
    p = sub.add_parser("check"); p.add_argument("--label", default=""); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("slides"); p.add_argument("--label", default=""); p.set_defaults(fn=cmd_slides)
    p = sub.add_parser("log"); p.add_argument("kind"); p.add_argument("ref"); p.add_argument("note"); p.set_defaults(fn=cmd_log)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
