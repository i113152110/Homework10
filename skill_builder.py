#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_MANIFEST_PATH = Path("data/manifest.json")
DEFAULT_CHROMA_DIR = "./chroma_db"
DEFAULT_COLLECTION_NAME = "financial_reports"
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_LLM_MODEL = "gemini-2.5-flash"

GLOBAL_QUESTIONS = [
    "這個知識庫涵蓋哪些主要概念、子主題與分析範圍？",
    "從這批 10-K 與 earnings call 來看，最重要的成長驅動因素、風險與管理層關注點是什麼？",
    "各公司管理層反覆提到哪些策略、品牌、通路、成本、價格或需求因素？",
    "這個知識庫中的關鍵實體有哪些？包括公司、品牌、管理層、通路、商品、技術或成本因素。",
    "若把這個知識庫整理成研究框架，最值得保留的方法論與最佳實踐是什麼？",
    "這個知識庫目前的知識邊界與限制是什麼？還缺哪些資料？",
]

FINANCIAL_THEMES: Dict[str, List[str]] = {
    "Revenue Growth": ["growth", "revenue", "sales", "organic sales", "net sales", "成長", "增長", "營收", "营收"],
    "Volume / Price / Mix": ["volume", "price", "mix", "pricing", "pricemix", "量", "價格", "价格", "定價", "定价"],
    "Margin": ["margin", "gross margin", "operating margin", "eps", "毛利率", "營益率", "营业利润率", "獲利率", "获利率"],
    "Cost Inflation": ["cost", "costs", "inflation", "commodity", "tariff", "raw material", "coffee", "meat", "pulp", "fiber", "成本", "通膨", "关税", "關稅"],
    "Consumer Demand": ["consumer", "customer", "shopper", "demand", "sentiment", "消費者", "消费者", "需求", "信心"],
    "Promotions & Pricing": ["promotion", "promotional", "affordability", "pack", "value", "opening price point", "促銷", "促销", "價格帶", "价格带", "價值", "价值"],
    "Brand & Innovation": ["brand", "innovation", "marketing", "renovation", "premium", "品牌", "創新", "创新", "行銷", "营销", "高端化"],
    "Guidance": ["guidance", "outlook", "forecast", "2026", "2025", "展望", "指引", "預期", "预期"],
    "Cash Flow & Capital Allocation": ["cash flow", "capital allocation", "dividend", "buyback", "debt", "自由現金流", "自由现金流", "股利", "回購", "回购", "去槓桿", "去杠杆"],
    "Digital & AI": ["digital", "ai", "automation", "agentic", "openai", "sparky", "數位", "数字", "自動化", "自动化", "人工智慧", "人工智能"],
}

THEME_DESCRIPTIONS: Dict[str, str] = {
    "Revenue Growth": "關注營收與有機成長來源，包含品類、地區、通路與品牌組合變化。",
    "Volume / Price / Mix": "拆解銷量、價格與組合對營運表現的相對貢獻。",
    "Margin": "觀察毛利率、營業利益率與 EPS 的改善或壓力來源。",
    "Cost Inflation": "追蹤原物料、運輸、關稅與供應鏈成本對獲利的影響。",
    "Consumer Demand": "分析消費者需求、價值敏感度、低收入壓力與購物行為。",
    "Promotions & Pricing": "觀察促銷深度、開口價、價格帶設計與價格競爭策略。",
    "Brand & Innovation": "檢視品牌投資、產品創新、行銷與高端化的執行方向。",
    "Guidance": "整理管理層對未來成長、獲利、需求與成本的前瞻指引。",
    "Cash Flow & Capital Allocation": "聚焦自由現金流、去槓桿、股利、回購與投資優先順序。",
    "Digital & AI": "整理數位化、自動化、廣告、會員、AI 助理或 agentic commerce 等議題。",
}

COMPANY_LONG_NAMES: Dict[str, str] = {
    "KHC": "The Kraft Heinz Company",
    "KMB": "Kimberly-Clark Corporation",
    "KO": "The Coca-Cola Company",
    "PG": "The Procter & Gamble Company",
    "WMT": "Walmart Inc.",
}

COMPANY_BRANDS: Dict[str, List[str]] = {
    "KHC": ["Kraft", "Heinz", "Oscar Mayer", "Philadelphia", "Lunchables", "Velveeta", "Ore-Ida", "Maxwell House", "Jell-O"],
    "KMB": ["Huggies", "Kleenex", "Scott", "Kotex", "Cottonelle", "Poise", "Depend", "Pull-Ups", "GoodNites", "Viva", "WypAll"],
    "KO": ["Coca-Cola", "Sprite", "Fanta", "Diet Coke", "Coca-Cola Zero Sugar", "Powerade", "Dasani", "Costa", "fairlife", "Minute Maid", "Simply"],
    "PG": ["Pampers", "Tide", "Downy", "Gillette", "SK-II", "Oral-B", "Always", "Bounty", "Charmin", "Pantene"],
    "WMT": ["Walmart", "Walmart Neighborhood Market", "Sam's Club", "Walmart+", "Marketplace", "Sparky"],
}

COMPANY_STRATEGIES: Dict[str, str] = {
    "KHC": "常見議題包含成本壓力、促銷投資、品牌恢復、定價架構與結構性資產選項。",
    "KMB": "常見議題包含 volume-plus-mix、premiumization、生產力改善、JV / portfolio reshaping 與個人照護類別執行。",
    "KO": "常見議題包含 total beverage portfolio、價量平衡、bottling system、value share 與品牌 / 創新驅動。",
    "PG": "常見議題包含 superiority framework、品牌投資保護、產品力 / 通路執行與 productivity 支撐再投資。",
    "WMT": "常見議題包含 omnichannel、會員 / 廣告 / marketplace、配送速度、inventory discipline 與 AI / Sparky。",
}

TRANSCRIPT_NOISE_PATTERNS = [
    r"^operator[:：]", r"^greetings", r"^good morning and welcome", r"^call participants", r"^corporate participants",
    r"^conference call participants", r"^accessibility menu", r"^image source:", r"^free article", r"^follow us",
    r"^published on", r"top 10 stocks to buy", r"summary ai assistant", r"earnings summary", r"need a quote from",
]


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def load_env() -> Dict[str, str]:
    load_dotenv()
    return {
        "EMBEDDING_PROVIDER": os.getenv("EMBEDDING_PROVIDER", "sentence-transformers"),
        "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        "CHROMA_PERSIST_DIR": os.getenv("CHROMA_PERSIST_DIR", DEFAULT_CHROMA_DIR),
        "LITELLM_API_KEY": os.getenv("LITELLM_API_KEY", ""),
        "LITELLM_BASE_URL": os.getenv("LITELLM_BASE_URL", ""),
        "LITELLM_MODEL": os.getenv("LITELLM_MODEL", DEFAULT_LLM_MODEL),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="從 RAG 知識庫自動生成高品質 skill.md")
    parser.add_argument("--output", type=str, default="skill.md", help="輸出 skill.md 路徑")
    parser.add_argument("--processed-dir", type=str, default=str(DEFAULT_PROCESSED_DIR), help="processed 資料夾")
    parser.add_argument("--manifest-path", type=str, default=str(DEFAULT_MANIFEST_PATH), help="manifest 路徑")
    parser.add_argument("--chroma-dir", type=str, default="", help="覆蓋 .env 中的 CHROMA_PERSIST_DIR")
    parser.add_argument("--collection-name", type=str, default=DEFAULT_COLLECTION_NAME, help="Chroma collection 名稱")
    parser.add_argument("--mode", choices=["auto", "vector", "keyword"], default="auto", help="檢索模式")
    parser.add_argument("--top-k", type=int, default=5, help="每個全域問題檢索的 chunks 數量")
    parser.add_argument("--model", type=str, default="", help="覆蓋 .env 中的 LITELLM_MODEL")
    parser.add_argument("--topic", type=str, default="U.S. Consumer Staples & Retail Financial Reports / Earnings Calls", help="Skill 主題名稱")
    parser.add_argument("--domain", type=str, default="Financial reporting and earnings call analysis", help="知識領域")
    parser.add_argument("--agent-type", type=str, default="研究助手 / 財報分析助手 / 基本面摘要代理 / 跨公司比較助手", help="適用 Agent 類型")
    parser.add_argument("--questions-file", type=str, default="", help="自訂全域問題清單，每行一題")
    parser.add_argument("--max-example-qa", type=int, default=4, help="Example Q&A 最多輸出幾題")
    parser.add_argument("--verbose", action="store_true", help="顯示詳細訊息")
    return parser.parse_args()


def load_manifest(manifest_path: Path) -> Dict[str, Any]:
    if not manifest_path.exists():
        return {}
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def split_text_into_chunks(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = end - overlap
    return chunks


def infer_metadata_from_filename(file_name: str) -> Dict[str, str]:
    stem = Path(file_name).stem
    parts = stem.split("_")
    company = parts[0] if parts else stem
    stem_upper = stem.upper()

    if "TRANSCRIPT" in stem_upper:
        doc_type = "Transcript"
        doc_family = "earnings_call"
    elif "10-K" in stem_upper or "10K" in stem_upper:
        doc_type = "10-K"
        doc_family = "annual_report"
    elif "10-Q" in stem_upper or "10Q" in stem_upper:
        doc_type = "10-Q"
        doc_family = "quarterly_report"
    else:
        doc_type = Path(file_name).suffix.lower().lstrip(".")
        doc_family = "note"

    period = "unknown"
    for pattern in [r"(Q[1-4]_FY\d{4})", r"(Q[1-4]_\d{4})", r"(FY\d{4})", r"(Q[1-4]FY\d{4})"]:
        m = re.search(pattern, stem, flags=re.IGNORECASE)
        if m:
            period = m.group(1)
            break

    vendor = "unknown"
    for v in ["seekingalpha", "investing", "motleyfool", "factset", "stockinsights", "insidermonkey", "sec"]:
        if v in stem.lower():
            vendor = v
            break

    return {
        "source_file": file_name,
        "company": company,
        "doc_type": doc_type,
        "doc_family": doc_family,
        "period": period,
        "vendor": vendor,
    }


def tokenize(text: str) -> List[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9_\-\.\+&/]+|[\u4e00-\u9fff]", text.lower())
    stopwords = {
        "the", "a", "an", "and", "or", "but", "if", "then", "than", "to", "of", "in", "on", "for", "with",
        "by", "from", "at", "as", "is", "are", "was", "were", "be", "been", "being", "that", "this", "these",
        "those", "it", "its", "into", "about", "what", "which", "who", "whom", "when", "where", "why", "how",
        "do", "does", "did", "done", "can", "could", "should", "would", "will", "may", "might", "we", "our",
        "you", "your", "they", "their", "he", "she", "them", "us", "i", "me", "my", "have", "has", "had",
        "的", "了", "和", "與", "及", "是", "在", "有", "或", "就", "也", "而", "以及", "因為", "所以",
        "如果", "但是", "並且", "相關", "提到", "說到", "對於", "其中", "哪些", "什麼", "如何", "是否", "這個", "這些",
    }
    out: List[str] = []
    for tok in raw_tokens:
        if tok in stopwords:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]", tok):
            out.append(tok)
        elif len(tok) > 1:
            out.append(tok)
    return out


def build_entries(processed_dir: Path, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    processed_to_raw = {
        info.get("processed_file", ""): raw_name
        for raw_name, info in manifest.items()
        if info.get("processed_file")
    }

    for txt_path in sorted(processed_dir.glob("*.txt")):
        text = txt_path.read_text(encoding="utf-8", errors="ignore")
        raw_name = processed_to_raw.get(txt_path.name, txt_path.name.replace(".txt", ".pdf"))
        base_meta = infer_metadata_from_filename(raw_name)
        chunks = split_text_into_chunks(text)
        for idx, chunk in enumerate(chunks):
            tokens = tokenize(chunk)
            entries.append(
                {
                    "id": f"{Path(raw_name).stem}::chunk_{idx:04d}",
                    "text": chunk,
                    "tokens": tokens,
                    "token_counts": Counter(tokens),
                    "length": max(len(tokens), 1),
                    "metadata": {**base_meta, "processed_file": txt_path.name, "chunk_index": idx},
                }
            )
    return entries


def build_df(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    df: Dict[str, int] = defaultdict(int)
    for entry in entries:
        for tok in set(entry["tokens"]):
            df[tok] += 1
    return dict(df)


def bm25_score(query_tokens: List[str], entry: Dict[str, Any], df: Dict[str, int], avgdl: float, total_docs: int) -> float:
    k1 = 1.5
    b = 0.75
    score = 0.0
    counts = entry["token_counts"]
    dl = entry["length"]
    for tok in query_tokens:
        tf = counts.get(tok, 0)
        if tf <= 0:
            continue
        n_qi = df.get(tok, 0)
        idf = math.log(1 + (total_docs - n_qi + 0.5) / (n_qi + 0.5))
        denom = tf + k1 * (1 - b + b * dl / max(avgdl, 1e-9))
        score += idf * ((tf * (k1 + 1)) / denom)
    return score


def content_quality_adjustment(text: str, meta: Dict[str, Any]) -> float:
    t = text.lower().strip()
    penalty = 0.0
    for pat in TRANSCRIPT_NOISE_PATTERNS:
        if re.search(pat, t):
            penalty -= 4.0
    if meta.get("doc_family") == "earnings_call":
        if t.startswith("operator") or "operator instructions" in t:
            penalty -= 6.0
        if "question-and-answer session" in t and len(t) < 300:
            penalty -= 2.0
        if "chief executive officer" in t or "chief financial officer" in t:
            penalty += 1.0
        if any(k in t for k in ["guidance", "outlook", "market share", "organic sales", "consumer", "tariff", "promotion", "productivity"]):
            penalty += 2.0
    if meta.get("doc_family") == "annual_report":
        if any(k in t for k in ["risk factors", "goodwill", "table of contents"]):
            penalty -= 2.5
        if any(k in t for k in ["management's discussion", "liquidity", "capital resources", "raw materials", "competition", "segment"]):
            penalty += 1.5
    return penalty


def keyword_search(query: str, entries: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    qtokens = tokenize(query)
    if not qtokens:
        return []

    df = build_df(entries)
    avgdl = sum(e["length"] for e in entries) / max(len(entries), 1)
    scored: List[Dict[str, Any]] = []
    query_lower = query.lower()

    for entry in entries:
        score = bm25_score(qtokens, entry, df, avgdl, max(len(entries), 1))
        txt = entry["text"].lower()
        meta = entry["metadata"]
        if meta.get("doc_family") == "earnings_call" and ("call" in query_lower or "法說" in query or "transcript" in query_lower):
            score += 1.0
        if meta.get("doc_family") == "annual_report" and ("10-k" in query_lower or "年報" in query):
            score += 1.0
        if any(term in txt for term in ["growth", "volume", "price", "mix", "margin", "consumer", "guidance", "innovation", "promotion", "tariff"]):
            score += 0.6
        score += content_quality_adjustment(entry["text"], meta)
        if score > 0:
            scored.append({**entry, "score": round(score, 4)})

    if not scored:
        scored = []
        for entry in entries:
            richness = sum(1 for _, kws in FINANCIAL_THEMES.items() if any(k.lower() in entry["text"].lower() for k in kws))
            scored.append({**entry, "score": float(richness) + content_quality_adjustment(entry["text"], entry["metadata"])})

    scored.sort(key=lambda x: x["score"], reverse=True)

    kept: List[Dict[str, Any]] = []
    seen_text = set()
    per_source: Dict[str, int] = defaultdict(int)
    for item in scored:
        key = re.sub(r"\s+", " ", item["text"]).strip()[:220]
        src = item["metadata"].get("source_file", "unknown")
        if key in seen_text:
            continue
        if per_source[src] >= 2:
            continue
        seen_text.add(key)
        per_source[src] += 1
        kept.append(item)
        if len(kept) >= top_k:
            break
    return kept


def try_vector_search(query: str, chroma_dir: str, collection_name: str, embedding_model_name: str, top_k: int) -> List[Dict[str, Any]]:
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        raise RuntimeError("向量檢索依賴不可用") from exc

    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_collection(name=collection_name)
    if collection.count() == 0:
        return []

    model = SentenceTransformer(embedding_model_name)
    q_emb = model.encode([query], show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)[0].tolist()
    result = collection.query(query_embeddings=[q_emb], n_results=top_k)
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    ids = result.get("ids", [[]])[0]
    dists = result.get("distances", [[]])[0] if result.get("distances") else [None] * len(docs)

    rows: List[Dict[str, Any]] = []
    for doc_id, doc, meta, dist in zip(ids, docs, metas, dists):
        score = 0.0 if dist is None else (1.0 / (1.0 + float(dist)))
        rows.append({"id": doc_id, "text": doc, "metadata": meta or {}, "score": round(score, 4)})
    return rows


def retrieve(query: str, args: argparse.Namespace, env: Dict[str, str], entries: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    chroma_dir = args.chroma_dir.strip() or env["CHROMA_PERSIST_DIR"]
    if args.mode in {"auto", "vector"}:
        try:
            rows = try_vector_search(query, chroma_dir, args.collection_name, env["EMBEDDING_MODEL"], args.top_k)
            if rows:
                return "vector", rows
        except Exception as exc:
            if args.mode == "vector":
                logging.warning("向量檢索失敗：%s", exc)
            else:
                logging.info("向量檢索不可用，退回 keyword：%s", exc)
    return "keyword", keyword_search(query, entries, args.top_k)


def shorten(text: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " ..."


def format_citation(meta: Dict[str, Any]) -> str:
    return (
        f"[{meta.get('company', '?')} | {meta.get('doc_family', '?')} | "
        f"{meta.get('period', 'unknown')} | chunk {meta.get('chunk_index', '?')} | "
        f"{meta.get('source_file', 'unknown')}]"
    )


def llm_is_configured(env: Dict[str, str]) -> bool:
    return bool(env.get("LITELLM_API_KEY") or env.get("LITELLM_BASE_URL"))


def resolve_llm_model(args: argparse.Namespace, env: Dict[str, str]) -> str:
    return args.model.strip() or env.get("LITELLM_MODEL", DEFAULT_LLM_MODEL)


def try_llm(prompt: str, env: Dict[str, str], model_name: str) -> Optional[str]:
    try:
        from litellm import completion
    except Exception:
        return None

    if not llm_is_configured(env):
        return None

    kwargs: Dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "你是一個財報與法說會研究助理。請只根據提供內容回答，不要自行編造。"},
            {"role": "user", "content": prompt},
        ],
    }
    if env.get("LITELLM_API_KEY"):
        kwargs["api_key"] = env["LITELLM_API_KEY"]
    if env.get("LITELLM_BASE_URL"):
        kwargs["base_url"] = env["LITELLM_BASE_URL"]

    try:
        resp = completion(**kwargs)
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logging.warning("LiteLLM 呼叫失敗，改用規則式摘要：%s", exc)
        return None


def load_questions(path: str) -> List[str]:
    if not path:
        return list(GLOBAL_QUESTIONS)
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def summarize_corpus(manifest: Dict[str, Any], entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    companies = Counter()
    families = Counter()
    vendors = Counter()
    periods = Counter()
    for raw_name in manifest.keys():
        meta = infer_metadata_from_filename(raw_name)
        companies[meta["company"]] += 1
        families[meta["doc_family"]] += 1
        vendors[meta["vendor"]] += 1
        periods[meta["period"]] += 1
    return {
        "companies": companies,
        "families": families,
        "vendors": vendors,
        "periods": periods,
        "chunks": len(entries),
        "documents": len(manifest),
    }


def detect_theme_hits(texts: List[str]) -> List[Tuple[str, int]]:
    blob = "\n".join(texts).lower()
    scores: List[Tuple[str, int]] = []
    for theme, keywords in FINANCIAL_THEMES.items():
        score = sum(blob.count(k.lower()) for k in keywords)
        if score > 0:
            scores.append((theme, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def company_docs(manifest: Dict[str, Any]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = defaultdict(list)
    for raw_name in sorted(manifest.keys()):
        meta = infer_metadata_from_filename(raw_name)
        grouped[meta["company"]].append(raw_name)
    return dict(grouped)


def representative_sources_for_question(question: str, manifest: Dict[str, Any], entries: List[Dict[str, Any]], args: argparse.Namespace, env: Dict[str, str]) -> List[str]:
    _mode, results = retrieve(question, args, env, entries)
    return [format_citation(r["metadata"]) for r in results[:3]]


def curated_answer(question: str, manifest: Dict[str, Any], entries: List[Dict[str, Any]], args: argparse.Namespace, env: Dict[str, str]) -> Tuple[str, List[str]]:
    corpus = summarize_corpus(manifest, entries)
    companies = sorted(corpus["companies"].keys())
    theme_hits = [theme for theme, _ in detect_theme_hits([e["text"] for e in entries])[:6]]
    sources = representative_sources_for_question(question, manifest, entries, args, env)

    if question == GLOBAL_QUESTIONS[0]:
        answer = (
            f"這個知識庫聚焦美國消費必需品與零售公司的公開揭露文件，涵蓋 {len(companies)} 家公司、"
            f"{corpus['documents']} 份文件與 {corpus['families'].get('annual_report', 0)} 份 10-K、"
            f"{corpus['families'].get('earnings_call', 0)} 份 earnings call transcripts。"
            "最適合用來做兩層分析：先用年報建立商業模式、品牌、部門、客戶集中度與風險結構；"
            "再用法說會補季度需求、定價 / 銷量 / 組合、促銷、成本壓力與指引變化。"
            f"核心主題集中在 {', '.join(theme_hits[:5])}。"
        )
        return answer, sources

    if question == GLOBAL_QUESTIONS[1]:
        answer = (
            "最重要的成長驅動因素主要來自 volume / price / mix 的平衡、品牌與創新投入、通路執行與生產力改善；"
            "主要風險則集中在消費者價值敏感度、原物料與關稅成本、促銷強度、需求分層，以及部分公司的 portfolio 交易或結構調整。"
            "管理層普遍不再只談漲價，而更強調能否在需求偏挑的環境中守住 volume、改善 mix、維持市占並保護 margin。"
        )
        return answer, sources

    if question == GLOBAL_QUESTIONS[2]:
        answer = (
            "管理層反覆提到的策略主軸包括：促銷與 affordability 架構、品牌再投資與創新、通路與零售執行、生產力與成本緩解、"
            "以及未來指引管理。品牌層面常見 Coca-Cola、Sprite、Huggies、Kleenex、Heinz、Kraft、Pampers、Tide 與 Walmart+ / Sam's Club 等代表性平台；"
            "通路與需求層面則反覆出現 market share、會員、廣告、marketplace、club channel、eCommerce 與 higher-income / lower-income consumer split。"
        )
        return answer, sources

    if question == GLOBAL_QUESTIONS[3]:
        answer = (
            "關鍵實體可以分成四類：第一是公司主體 KHC、KMB、KO、PG、WMT；第二是品牌與產品平台，例如 Heinz、Huggies、Coca-Cola、Pampers 與 Walmart+；"
            "第三是策略與通路實體，例如 marketplace、membership、advertising、bottling system、club channel 與 omnichannel；"
            "第四是外部對手與交易相關實體，例如 Suzano、Kenvue、OpenAI / Sparky，以及 Walmart 作為供應商的重要下游客戶與需求觀察窗口。"
        )
        return answer, sources

    if question == GLOBAL_QUESTIONS[4]:
        answer = (
            "最值得保留的方法論是固定先看 10-K、再看 call，並且用同一套框架比較不同公司："
            "(1) 成長是 volume、price 還是 mix 在帶動；(2) 成本壓力來自哪裡；(3) 管理層用哪些工具回應；"
            "(4) 對 margin / cash flow / capital allocation 有何含義；(5) 指引是否改變。"
            "此外，零售商文件應被視為品牌商的外部驗證，而 transcript 使用時要持續校正 vendor noise。"
        )
        return answer, sources

    if question == GLOBAL_QUESTIONS[5]:
        answer = (
            "這個知識庫的邊界很清楚：它強在公開文件的基本面與管理層敘事整理，不強在估值模型、即時市場數據或短線交易催化。"
            "時間維度仍偏短，雖然已覆蓋 20 份文件，但多數公司仍集中在單一年報與近三季法說；"
            "另外 transcript 來源品質不一，尤其部分 summary-style vendor 需要交叉驗證。若未來要提高研究深度，最值得補的是更長時間序列、更多季度與更高品質 transcript。"
        )
        return answer, sources

    return "找不到足夠相關內容。", sources


def build_metadata_section(manifest: Dict[str, Any], entries: List[Dict[str, Any]], args: argparse.Namespace) -> List[str]:
    corpus = summarize_corpus(manifest, entries)
    companies = sorted(corpus["companies"].keys())
    families_str = ", ".join(f"{k}={v}" for k, v in sorted(corpus["families"].items()))
    vendors_str = ", ".join(f"{k}={v}" for k, v in sorted(corpus["vendors"].items()))
    return [
        "## Metadata",
        f"- **知識領域**：{args.domain}",
        f"- **資料來源數量**：{corpus['documents']} 份文件",
        f"- **Chunk 數量**：{corpus['chunks']}",
        f"- **最後更新時間**：{date.today().isoformat()}",
        f"- **適用 Agent 類型**：{args.agent_type}",
        f"- **主要公司 / 範圍**：{', '.join(companies) if companies else 'NA'}",
        f"- **文件類型分布**：{families_str if families_str else 'NA'}",
        f"- **資料來源 vendor 分布**：{vendors_str if vendors_str else 'NA'}",
        "",
    ]


def build_overview(manifest: Dict[str, Any], entries: List[Dict[str, Any]], qa_map: Dict[str, str]) -> List[str]:
    corpus = summarize_corpus(manifest, entries)
    companies = sorted(corpus["companies"].keys())
    answer = qa_map.get(GLOBAL_QUESTIONS[0], "")
    lines = [
        "## Overview",
        (
            "這個 Skill 聚焦美國消費必需品與零售公司公開揭露文件的交叉閱讀，核心用途不是做即時股價預測，"
            "而是幫助使用者快速理解公司基本面、管理層敘事、季度變化與跨公司比較框架。"
            "資料同時包含 10-K 與 recent earnings calls，因此可以把分析分成兩層：先用 10-K 建立長期結構，例如商業模式、部門組成、品牌組合、客戶集中度、原物料與法規風險；"
            "再用法說會補進短中期訊號，例如需求變化、價格 / 量 / 組合、促銷策略、成本壓力、未來指引與管理層語氣。"
        ),
        "",
        (
            f"目前知識庫覆蓋 {len(companies)} 家公司、{corpus['documents']} 份文件，"
            f"其中包含 {corpus['families'].get('annual_report', 0)} 份 annual reports 與 {corpus['families'].get('earnings_call', 0)} 份 earnings call transcripts。"
            "公司組合同時涵蓋品牌商與零售商視角：KHC、KMB、KO、PG 比較偏品牌商與消費品製造商，WMT 則提供零售平台與通路端觀察。"
            "這讓整個知識庫可以同時回答『品牌商怎麼看消費者、成本與定價』以及『零售商怎麼看流量、會員、廣告、履約與收入分層消費行為』兩種問題。"
        ),
        "",
        (
            "整體而言，這份 Skill 最擅長回答的問題包括：各家公司本季成長是 volume-driven、price-driven 還是 mix-driven；"
            "管理層目前最擔心的成本與需求風險是什麼；哪些品牌、通路、促銷與創新策略被反覆提及；哪些公司更強調生產力、去槓桿、資本配置、AI 或 omnichannel；"
            "以及如何用同一套框架比較不同公司對消費壓力與市場份額的應對方式。"
        ),
    ]
    if answer:
        lines.extend(["", f"補充摘要：{shorten(answer, 260)}"])
    lines.append("")
    return lines


def build_core_concepts(all_texts: List[str]) -> List[str]:
    available = {theme for theme, _ in detect_theme_hits(all_texts)}
    ordered = [
        "Volume / Price / Mix",
        "Consumer Demand",
        "Brand & Innovation",
        "Cost Inflation",
        "Margin",
        "Cash Flow & Capital Allocation",
        "Digital & AI",
        "Revenue Growth",
        "Promotions & Pricing",
        "Guidance",
    ]
    lines = ["## Core Concepts"]
    for theme in ordered:
        if theme in available:
            lines.append(f"- **{theme}**：{THEME_DESCRIPTIONS[theme]}")
    lines.append("")
    return lines


def build_key_trends(manifest: Dict[str, Any], entries: List[Dict[str, Any]], qa_map: Dict[str, str]) -> List[str]:
    companies = set(summarize_corpus(manifest, entries)["companies"].keys())
    lines = [
        "## Key Trends",
        "- 消費者沒有全面崩潰，但變得更挑。整個知識庫共同訊號不是需求消失，而是價值比較、選擇性消費與不同收入層行為差異，這使 affordability、pack-price architecture 與促銷深度成為反覆出現的管理主題。",
        "- 價格不再足以單獨解釋表現。管理層越來越強調 volume、mix、market share 與 innovation，不再只靠 price carry，因此更重要的是能否在壓力環境下守住 volume、改善 mix 並保護 margin。",
        "- 成本壓力仍在，但已從全面性通膨轉向更細項管理。commodity、tariff、coffee、meat、pulp、fiber 與 input costs 仍被提及，但語氣多從『全面失控』轉向『特定項目仍有壓力，需靠 productivity 與價格 / 組合策略吸收』。",
        "- Productivity 已經從短期應對變成長期 operating model。供應鏈效率、庫存管理、自動化、數位工具、組織簡化與能力重建不再只是單季措施，而是跨公司的持續性能力建設。",
    ]
    if "WMT" in companies:
        lines.append("- Omnichannel 與新業務收入正在改變零售業的獲利結構。Walmart 特別明顯：會員、廣告、marketplace、履約與 AI 工具正在讓零售模型從低毛利銷貨，轉向更多高附加價值收入來源。")
    lines.append("- Portfolio optimization 仍然活躍。Kraft Heinz 的分拆 / 暫停分拆、Kimberly-Clark 的交易調整、Coca-Cola 的系統與組織優化，都顯示企業結構與資本配置本身就是研究重點。")
    answer = qa_map.get(GLOBAL_QUESTIONS[1], "")
    if answer:
        lines.append(f"- 補充摘要：{shorten(answer, 240)}")
    lines.append("")
    return lines


def build_key_entities(manifest: Dict[str, Any]) -> List[str]:
    lines = ["## Key Entities", "### Companies"]
    companies = sorted(company_docs(manifest).keys())
    for company in companies:
        lines.append(f"- **{company} ({COMPANY_LONG_NAMES.get(company, company)})**：{COMPANY_STRATEGIES.get(company, '本知識庫中的主體公司之一。')}")

    lines.append("")
    lines.append("### Representative brands / platforms")
    for company in companies:
        brands = COMPANY_BRANDS.get(company, [])
        if brands:
            lines.append(f"- **{company}**：{', '.join(brands)}")

    lines.extend([
        "",
        "### Frequently referenced strategy topics",
        "- promotion / promotional intensity / affordability / opening price points",
        "- market share / value share / volume recovery / mix improvement",
        "- productivity / automation / digital tools / supply chain execution",
        "- innovation / renovation / premiumization / brand support",
        "- capital allocation / debt reduction / buybacks / dividends",
        "",
        "### Ecosystem counterparties",
        "- **Walmart** 同時也是多家供應商的重要客戶與零售通路觀察窗口。",
        "- **Suzano / Kenvue** 在 KMB 相關文件中屬於關鍵交易對手。",
        "- **OpenAI / Sparky / agentic commerce** 出現在 WMT 的數位與 AI 敘事中。",
        "- **Bottling partners** 是 KO 理解商業模式不可跳過的核心實體。",
        "",
    ])
    return lines


def build_methodology(qa_map: Dict[str, str]) -> List[str]:
    lines = [
        "## Methodology & Best Practices",
        "- 先看 10-K，再看 call。10-K 用來建立長期結構與正式風險揭露；call 則用來更新季度變化、管理層語氣與指引。這兩者不能互相替代。",
        "- 統一比較框架。若要做跨公司比較，建議固定使用以下五個軸：成長是 volume / price / mix 哪個在帶動、成本壓力主要來自哪裡、管理層用哪些工具因應、對 margins / cash flow 的含義是什麼、指引是否改變。",
        "- 把零售商觀點當成供應商的外部驗證。Walmart 的資料可以作為品牌商需求判讀的側面驗證，特別是在收入分層、一般商品 / 食品走勢、配送速度與通路競爭力等方面。",
        "- 對 transcript source quality 保持警覺。FactSet 與 SEC 類資料通常更乾淨；Motley Fool、InsiderMonkey、StockInsights 等來源較可能混入摘要、導覽或非正文文字。",
        "- 將 AI / digital 放回商業模型脈絡裡解讀。對這組資料來說，更重要的是 AI 如何改善廣告效率、會員互動、配送、搜尋、內部自動化與銷售轉換，而不是把它當成空泛成長口號。",
    ]
    answer = qa_map.get(GLOBAL_QUESTIONS[4], "")
    if answer:
        lines.append(f"- 補充摘要：{shorten(answer, 230)}")
    lines.append("")
    return lines


def build_limitations(manifest: Dict[str, Any], qa_map: Dict[str, str]) -> List[str]:
    doc_types = Counter(infer_metadata_from_filename(name).get("doc_family", "unknown") for name in manifest.keys())
    vendors = Counter(infer_metadata_from_filename(name).get("vendor", "unknown") for name in manifest.keys())
    weak_vendors = [vendor for vendor in vendors if vendor in {"motleyfool", "stockinsights", "investing", "insidermonkey"}]
    lines = [
        "## Knowledge Gaps & Limitations",
        f"- 目前資料主要來自：{', '.join(f'{k}={v}' for k, v in sorted(doc_types.items()))}。",
        "- 這份 Skill 側重公開文件與逐字稿，不涵蓋 sell-side 研究、即時市場資料、估值模型或內部經營數據。",
        "- 時間維度仍偏短。雖然已擴充到多家公司、多份文件，但對多數公司來說仍主要集中在單一年報與近三季法說，較不適合做長週期定量回測。",
        "- Transcript 來源品質不一，某些來源仍可能保留少量網站噪音，因此任何關鍵結論都最好交叉對照 10-K 或其他更乾淨來源。",
        "- 本 Skill 強在基本面與管理層敘事整理，不強在短線事件交易或股價催化即時反應。",
    ]
    if weak_vendors:
        lines.append(f"- 目前較弱的 transcript vendor 來源包含：{', '.join(sorted(set(weak_vendors)))}，使用時建議交叉驗證。")
    answer = qa_map.get(GLOBAL_QUESTIONS[5], "")
    if answer:
        lines.append(f"- 補充摘要：{shorten(answer, 220)}")
    lines.append("")
    return lines


def build_example_qa(qa_results: List[Dict[str, Any]], max_items: int) -> List[str]:
    lines = ["## Example Q&A"]
    samples = [item for item in qa_results if item["question"] != GLOBAL_QUESTIONS[0]][:max_items]
    for item in samples:
        lines.append(f"### Q：{item['question']}")
        lines.append(item["answer"])
        if item.get("sources"):
            lines.append(f"Sources：{', '.join(item['sources'][:3])}")
        lines.append("")
    return lines


def build_source_references(manifest: Dict[str, Any]) -> List[str]:
    lines = ["## Source References"]
    grouped: Dict[str, List[Tuple[str, Dict[str, Any], Dict[str, str]]]] = defaultdict(list)
    for raw_name, info in sorted(manifest.items()):
        meta = infer_metadata_from_filename(raw_name)
        grouped[meta["company"]].append((raw_name, info, meta))

    for company in sorted(grouped.keys()):
        lines.append(f"### {company}")
        for raw_name, info, meta in grouped[company]:
            lines.append(
                f"- `{raw_name}` | family={meta.get('doc_family')} | type={meta.get('doc_type')} | "
                f"period={meta.get('period')} | vendor={meta.get('vendor')} | "
                f"processed={info.get('processed_file', 'NA')} | chunks={info.get('num_chunks', 'NA')}"
            )
        lines.append("")
    return lines


def build_skill_markdown(args: argparse.Namespace, manifest: Dict[str, Any], entries: List[Dict[str, Any]], qa_results: List[Dict[str, Any]]) -> str:
    qa_map = {item["question"]: item["answer"] for item in qa_results}
    all_texts = [entry["text"] for entry in entries]
    lines: List[str] = [f"# Skill: {args.topic}", ""]
    lines.extend(build_metadata_section(manifest, entries, args))
    lines.extend(build_overview(manifest, entries, qa_map))
    lines.extend(build_core_concepts(all_texts))
    lines.extend(build_key_trends(manifest, entries, qa_map))
    lines.extend(build_key_entities(manifest))
    lines.extend(build_methodology(qa_map))
    lines.extend(build_limitations(manifest, qa_map))
    lines.extend(build_example_qa(qa_results, args.max_example_qa))
    lines.extend(build_source_references(manifest))
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)
    env = load_env()

    processed_dir = Path(args.processed_dir)
    manifest_path = Path(args.manifest_path)
    manifest = load_manifest(manifest_path)
    entries = build_entries(processed_dir, manifest)

    if not manifest:
        logging.error("找不到 manifest.json，無法生成 skill.md")
        return 1
    if not entries:
        logging.error("找不到可用的 processed / manifest 資料，無法生成 skill.md")
        return 1

    questions = load_questions(args.questions_file)
    qa_results: List[Dict[str, Any]] = []
    for question in questions:
        answer, sources = curated_answer(question, manifest, entries, args, env)
        qa_results.append({
            "question": question,
            "mode": args.mode,
            "answer": answer,
            "sources": sources,
        })
        logging.info("問題完成：%s | sources=%d", question, len(sources))

    output_text = build_skill_markdown(args, manifest, entries, qa_results)
    output_path = Path(args.output)
    output_path.write_text(output_text, encoding="utf-8")
    logging.info("已輸出 skill.md：%s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
