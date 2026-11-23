#!/usr/bin/env python3
"""
wiki_query.py — 「查詢 Wiki」節點（改寫自 HW3 rag_query.py 的 keyword 模式）

流程
  1. 先查 Wiki：把每一行有內容的 Wiki 句子當成一個檢索單位，用 BM25 排序
     （分詞沿用 rag_query.tokenize；中文逐字、英文逐詞）。
  2. 判斷是否「Wiki 缺口」：
       a. 問題指定了公司＋季度，但 Wiki 沒有 ingest 那一份 → gap（period-not-ingested）
       b. 最高分太低 → gap（low-score）
  3. 有缺口就退回 raw：呼叫 rag_query.build_keyword_index / keyword_search 在
     data/processed 的原始 chunk 裡找，並把結果與缺口寫進 wiki/log.md，
     提醒「要不要回去補 ingest」。

用法
  python wiki_query.py "KO Q4 的 price/mix 為什麼只有 1%"
  python wiki_query.py "Kraft Heinz Q3 2025 organic sales" --log
  python wiki_query.py "..." --raw          # 強制同時查 raw
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent
WIKI = ROOT / "wiki"
sys.path.insert(0, str(ROOT))

from rag_query import tokenize, expand_company_mentions  # noqa: E402  (HW3 的分詞與公司別名)
from wiki_lint import EVID_RE, parse_frontmatter  # noqa: E402

GAP_SCORE = 6.0  # 經驗門檻：低於此分數視為 Wiki 沒有好答案

ALIASES = {
    "銷量": "volume unit", "價格": "price pricing", "組合": "mix", "基期": "base period",
    "有機": "organic", "指引": "guidance expect outlook", "關稅": "tariffs",
    "成本": "cost commodity input", "促銷": "promotional promo", "通路": "club channel",
    "廣告": "advertising", "會員": "membership", "季": "quarter", "市占": "share",
}


def load_units() -> List[Dict]:
    units: List[Dict] = []
    for p in sorted(WIKI.rglob("*.md")):
        rel = str(p.relative_to(WIKI))[:-3]
        if rel.split("/")[0] not in ("sources", "concepts", "entities"):
            continue
        text = p.read_text(encoding="utf-8")
        fm, start = parse_frontmatter(text)
        title = fm.get("title", rel)
        for off, line in enumerate(text.split("\n")[start:]):
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("```"):
                continue
            quotes = " ".join(q for _, q in EVID_RE.findall(s))
            claim = EVID_RE.sub("", s)
            toks = tokenize(claim + " " + quotes + " " + title)
            if not toks:
                continue
            units.append({
                "page": rel, "line": start + off + 1, "title": title, "claim": claim.strip(),
                "quote": quotes, "tokens": toks, "tf": Counter(toks),
                "has_evidence": bool(quotes),
            })
    return units


def expand_query(q: str) -> List[str]:
    toks = tokenize(q)
    extra = []
    for k, v in ALIASES.items():
        if k in q:
            extra += tokenize(v)
    return list(dict.fromkeys(toks + extra))


def bm25(units: List[Dict], qtoks: List[str], k1: float = 1.5, b: float = 0.75) -> List[Dict]:
    N = len(units)
    df: Counter = Counter()
    for u in units:
        for t in set(u["tokens"]):
            df[t] += 1
    avgdl = sum(len(u["tokens"]) for u in units) / max(N, 1)
    out = []
    for u in units:
        s = 0.0
        for t in qtoks:
            f = u["tf"].get(t, 0)
            if not f:
                continue
            idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(u["tokens"]) / avgdl))
        if s > 0:
            out.append({**u, "score": round(s * (1.15 if u["has_evidence"] else 1.0), 3)})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def source_registry() -> List[Dict]:
    reg = []
    for p in sorted((WIKI / "sources").glob("*.md")):
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        reg.append(fm)
    return reg


def detect_period_gap(q: str, reg: List[Dict]) -> str:
    """問題指定了「公司＋季度」但 Wiki 沒有那一份 → 回傳說明；否則空字串。"""
    companies = expand_company_mentions(q)
    ql = q.lower()
    qs = re.findall(r"\bq([1-4])\b", ql)
    yrs = re.findall(r"\b(20\d\d)\b", ql)
    if not companies or not qs:
        return ""
    for c in companies:
        for f in reg:
            per = f.get("period", "").lower()
            if f.get("company") == c and any(f"q{x}" in per for x in qs) and (not yrs or any(y in per for y in yrs)):
                return ""
    return f"Wiki 沒有 ingest {','.join(companies)} 的 Q{'/'.join(qs)} {'/'.join(yrs)} 文件"


def raw_search(q: str, top_k: int = 3) -> List[Dict]:
    from rag_query import build_keyword_index, keyword_search, load_manifest
    manifest = load_manifest(ROOT / "data" / "manifest.json")
    entries = build_keyword_index(ROOT / "data" / "processed", manifest)
    res = keyword_search(q, entries, top_k=top_k, max_sources=3)
    return [{
        "source": r["metadata"].get("source_file"), "company": r["metadata"].get("company"),
        "period": r["metadata"].get("period"), "chunk": r["metadata"].get("chunk_index"),
        "score": r["score"], "text": re.sub(r"\s+", " ", r["text"])[:300],
    } for r in res]


_UNITS_CACHE: List[Dict] = []


def rank_pages(q: str, top_n: int = 5) -> List[str]:
    """只查 Wiki、不碰 raw：回傳最相關的頁面（簡報檢查用）。"""
    if not _UNITS_CACHE:
        _UNITS_CACHE.extend(load_units())
    ranked = bm25(_UNITS_CACHE, expand_query(q))
    pages: Dict[str, float] = defaultdict(float)
    for u in ranked[:12]:
        pages[u["page"]] += u["score"]
    return [p for p, _ in sorted(pages.items(), key=lambda kv: kv[1], reverse=True)[:top_n]]


def query(q: str, top_k: int = 5, force_raw: bool = False) -> Dict:
    units = load_units()
    ranked = bm25(units, expand_query(q))
    pages: Dict[str, float] = defaultdict(float)
    for u in ranked[:12]:
        pages[u["page"]] += u["score"]
    page_rank = sorted(pages.items(), key=lambda kv: kv[1], reverse=True)
    top = ranked[:top_k]
    gap = detect_period_gap(q, source_registry())
    if not gap and (not top or top[0]["score"] < GAP_SCORE):
        gap = f"low-score（最高分 {top[0]['score'] if top else 0} < {GAP_SCORE}）"
    raw = raw_search(q) if (gap or force_raw) else []
    return {"query": q, "top_units": top, "pages": page_rank[:5], "gap": gap, "raw": raw}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--raw", action="store_true", help="即使 Wiki 命中也同時查 raw")
    ap.add_argument("--log", action="store_true", help="把查詢（與缺口）寫進 wiki/log.md 與 logs/runs.jsonl")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = query(a.question, a.top, a.raw)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    else:
        print(f"問題：{r['query']}")
        print("頁面排名：" + "、".join(f"{p}({s:.1f})" for p, s in r["pages"]))
        for u in r["top_units"]:
            print(f"\n[{u['score']:>6}] {u['page']} L{u['line']}\n  {u['claim'][:120]}")
            if u["quote"]:
                print(f"  原文：{u['quote'][:140]}")
        if r["gap"]:
            print(f"\n⚠ Wiki 缺口：{r['gap']}  → 退回 raw 查詢")
        for x in r["raw"]:
            print(f"  raw[{x['score']}] {x['source']} chunk {x['chunk']}: {x['text'][:160]}")
    if a.log:
        ts = time.strftime("%Y-%m-%d %H:%M")
        note = f"問題：{a.question}\n- Wiki 命中頁面：{', '.join(p for p, _ in r['pages'][:3]) or '無'}"
        if r["gap"]:
            note += f"\n- **Wiki 缺口**：{r['gap']}；raw 命中：" + "；".join(f"{x['source']} chunk {x['chunk']}" for x in r["raw"])
        with (WIKI / "log.md").open("a", encoding="utf-8") as f:
            f.write(f"\n## [{ts}] query | {'gap' if r['gap'] else 'hit'}\n{note}\n")
        with (ROOT / "logs" / "runs.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "stage": "wiki-query", "query": a.question,
                                "gap": r["gap"], "top_page": r["pages"][0][0] if r["pages"] else None,
                                "top_score": r["top_units"][0]["score"] if r["top_units"] else 0}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
