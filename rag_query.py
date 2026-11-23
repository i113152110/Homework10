#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv


DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_MANIFEST_PATH = Path("data/manifest.json")
DEFAULT_CHROMA_DIR = "./chroma_db"
DEFAULT_COLLECTION_NAME = "financial_reports"
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_HISTORY_TURNS = 3

EN_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "to", "of", "in", "on", "for", "with",
    "by", "from", "at", "as", "is", "are", "was", "were", "be", "been", "being", "that", "this", "these",
    "those", "it", "its", "into", "about", "what", "which", "who", "whom", "when", "where", "why", "how",
    "do", "does", "did", "done", "can", "could", "should", "would", "will", "may", "might", "we", "our",
    "you", "your", "they", "their", "he", "she", "them", "us", "i", "me", "my", "isn", "aren", "wasn",
    "weren", "don", "doesn", "didn", "have", "has", "had", "having", "there", "here", "such", "also"
}
ZH_STOPWORDS = {
    "的", "了", "和", "與", "及", "是", "在", "有", "或", "就", "也", "而", "以及", "因為", "所以",
    "如果", "但是", "並且", "相關", "提到", "說到", "對於", "其中", "哪些", "什麼", "如何", "是否"
}

COMPANY_ALIASES = {
    "KHC": ["kraft heinz", "khc", "kraft-heinz", "卡夫亨氏"],
    "KMB": ["kimberly-clark", "kimberly clark", "kmb", "金佰利"],
    "KO": ["coca-cola", "coca cola", "ko", "可口可樂", "可口可乐"],
    "PG": ["procter & gamble", "procter and gamble", "p&g", "pg", "寶僑", "宝洁", "寶潔"],
    "WMT": ["walmart", "wmt", "沃爾瑪", "沃尔玛"],
}

JUNK_PATTERNS = [
    r"view all earnings call transcripts",
    r"this article was generated",
    r"for more information see our t&c",
    r"technical difficulty",
    r"followers",
    r"published on",
    r"top 10 stocks to buy",
    r"accessibility menu",
    r"enter your email",
    r"get email alerts",
    r"summary eps of",
    r"breaking news",
    r"subscribe with google",
    r"privacy policy",
]

VENDOR_QUALITY = {
    "sec": 1.2,
    "factset": 1.0,
    "seekingalpha": 0.8,
    "motleyfool": 0.4,
    "insidermonkey": 0.1,
    "investing": -0.3,
    "stockinsights": -0.4,
    "unknown": 0.0,
}

CONCEPT_ALIASES = {
    "costs": ["cost", "costs", "inflation", "raw material", "commodity", "tariff", "成本", "通膨", "原物料", "關稅", "关税", "成本壓力", "成本压力"],
    "pricing": ["pricing", "price", "promotion", "promotional", "affordability", "定價", "价格", "促銷", "促销", "價格策略"],
    "ai": ["ai", "artificial intelligence", "agentic", "openai", "sparky", "digital", "automation", "人工智慧", "代理式", "自動化", "自动化"],
    "guidance": ["guidance", "outlook", "2026", "2025 outlook", "展望", "指引", "預期", "预期"],
    "margin": ["margin", "gross margin", "operating margin", "eps", "毛利率", "營益率", "运营利润率", "獲利率", "获利率"],
    "growth": ["growth", "volume", "market share", "share", "revenue", "organic sales", "成長", "增长", "市占", "市佔", "營收", "营收"],
    "consumer": ["consumer", "customer", "shopper", "demand", "sentiment", "消費者", "消费者", "需求", "信心"],
    "innovation": ["innovation", "brand", "marketing", "r&d", "renovation", "創新", "创新", "品牌", "研發", "研发", "行銷", "营销"],
    "separation": ["separation", "spin", "split", "portfolio", "pause", "拆分", "分拆", "暫停", "暂停"],
}


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
        "LITELLM_MODEL": os.getenv("LITELLM_MODEL", "gemini-2.5-flash"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="查詢財報 / 法說會知識庫：預設先走 vector search，失敗時退回 keyword fallback"
    )
    parser.add_argument("--query", type=str, default="", help="要查詢的問題；未提供時會直接進入互動模式")
    parser.add_argument("--interactive", action="store_true", help="進入互動查詢模式（不帶 --query 時也會自動進入）")
    parser.add_argument("--top-k", type=int, default=5, help="檢索前幾個 chunks（預設：5）")
    parser.add_argument("--mode", choices=["auto", "vector", "keyword"], default="auto", help="檢索模式")
    parser.add_argument("--model", type=str, default="", help="覆蓋 .env 中的 LITELLM_MODEL，例如 gemini-2.5-flash")
    parser.add_argument("--processed-dir", type=str, default=str(DEFAULT_PROCESSED_DIR), help="processed 資料夾")
    parser.add_argument("--manifest-path", type=str, default=str(DEFAULT_MANIFEST_PATH), help="manifest 路徑")
    parser.add_argument("--chroma-dir", type=str, default="", help="覆蓋 .env 中的 CHROMA_PERSIST_DIR")
    parser.add_argument("--collection-name", type=str, default=DEFAULT_COLLECTION_NAME, help="Chroma collection 名稱")
    parser.add_argument("--company", type=str, default="", help="只搜尋特定公司，例如 KHC / KO / WMT")
    parser.add_argument("--doc-family", type=str, default="", help="只搜尋 annual_report / earnings_call / quarterly_report")
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="保留相容旗標；若 LiteLLM 已設定，程式本來就會自動嘗試生成答案",
    )
    parser.add_argument("--history-turns", type=int, default=DEFAULT_HISTORY_TURNS, help="互動模式保留最近幾輪對話歷史（預設：3）")
    parser.add_argument("--show-context", action="store_true", help="印出檢索片段")
    parser.add_argument("--show-scores", action="store_true", help="印出各檢索結果分數")
    parser.add_argument("--max-sources", type=int, default=3, help="回答中最多引用幾個來源文件（預設：3）")
    parser.add_argument("--verbose", action="store_true", help="顯示詳細除錯資訊")
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
    for pattern in [r"(Q[1-4]_FY\d{4})", r"(Q[1-4]_\d{4})", r"(FY\d{4})"]:
        m = re.search(pattern, stem, flags=re.IGNORECASE)
        if m:
            period = m.group(1)
            break

    vendor = "unknown"
    vendors = ["seekingalpha", "investing", "motleyfool", "factset", "stockinsights", "insidermonkey", "sec"]
    for v in vendors:
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


def expand_company_mentions(query: str) -> List[str]:
    q = query.lower()
    hits: List[str] = []
    for ticker, aliases in COMPANY_ALIASES.items():
        if ticker.lower() in q or any(alias in q for alias in aliases):
            hits.append(ticker)
    return hits


def expand_concept_tokens(query: str) -> List[str]:
    q = query.lower()
    expanded: List[str] = []
    for aliases in CONCEPT_ALIASES.values():
        if any(alias in q for alias in aliases):
            expanded.extend(aliases)
    return expanded


def tokenize(text: str) -> List[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9_\-\.\+&/]+|[\u4e00-\u9fff]", text.lower())
    out: List[str] = []
    for tok in raw_tokens:
        if re.fullmatch(r"[\u4e00-\u9fff]", tok):
            if tok not in ZH_STOPWORDS:
                out.append(tok)
        else:
            if tok not in EN_STOPWORDS and len(tok) > 1:
                out.append(tok)
    return out


def normalize_query_tokens(query: str) -> List[str]:
    toks = tokenize(query)
    toks.extend(tokenize(" ".join(expand_concept_tokens(query))))
    for company in expand_company_mentions(query):
        toks.append(company.lower())
    seen = set()
    out: List[str] = []
    for tok in toks:
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def strip_entity_and_time_tokens(query_tokens: List[str], query: str) -> List[str]:
    remove = set()
    for company in expand_company_mentions(query):
        remove.add(company.lower())
    remove.update({"q1", "q2", "q3", "q4", "fy2025", "fy2026", "2025", "2026", "earnings", "call", "transcript"})
    return [tok for tok in query_tokens if tok not in remove]


def build_keyword_index(processed_dir: Path, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    manifest_processed_lookup = {}
    for raw_name, info in manifest.items():
        pf = info.get("processed_file")
        if pf:
            manifest_processed_lookup[pf] = raw_name

    for txt_path in sorted(processed_dir.glob("*.txt")):
        try:
            text = txt_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logging.warning("讀取失敗：%s | %s", txt_path.name, exc)
            continue

        source_file = manifest_processed_lookup.get(txt_path.name, txt_path.name.replace(".txt", ".pdf"))
        base_meta = infer_metadata_from_filename(source_file)
        chunks = split_text_into_chunks(text)
        for idx, chunk in enumerate(chunks):
            metadata = dict(base_meta)
            metadata["processed_file"] = txt_path.name
            metadata["chunk_index"] = idx
            tokens = tokenize(chunk)
            token_counts = Counter(tokens)
            filename_text = f"{metadata['source_file']} {metadata['company']} {metadata['doc_family']} {metadata['period']} {metadata['vendor']}"
            entries.append({
                "id": f"{Path(source_file).stem}::chunk_{idx:04d}",
                "text": chunk,
                "metadata": metadata,
                "tokens": tokens,
                "token_counts": token_counts,
                "length": max(len(tokens), 1),
                "filename_text": filename_text.lower(),
            })
    return entries


def filter_entries(entries: List[Dict[str, Any]], company: str = "", doc_family: str = "") -> List[Dict[str, Any]]:
    company = company.strip().lower()
    doc_family = doc_family.strip().lower()
    filtered = []
    for e in entries:
        meta = e["metadata"]
        if company and meta.get("company", "").lower() != company:
            continue
        if doc_family and meta.get("doc_family", "").lower() != doc_family:
            continue
        filtered.append(e)
    return filtered


def query_intents(query: str) -> Dict[str, bool]:
    q = query.lower()
    return {
        "cost_pressure": any(k in q for k in ["cost pressure", "成本壓力", "成本压力", "inflation pressure", "成本"]),
        "ai": any(k in q for k in ["ai", "artificial intelligence", "agentic", "openai", "sparky", "人工智慧", "代理式"]),
        "guidance": any(k in q for k in ["guidance", "outlook", "展望", "指引", "預期", "预期"]),
    }


def split_sentences_loose(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[\.\!\?。！？])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def best_local_window(query: str, text: str, window_size: int = 2) -> Tuple[str, float]:
    sentences = split_sentences_loose(text)
    if not sentences:
        return shorten(text, 260), 0.0

    toks = strip_entity_and_time_tokens(normalize_query_tokens(query), query)
    intents = query_intents(query)
    positive_terms = []
    negative_terms = []

    if intents.get("cost_pressure"):
        positive_terms = ["inflation", "cost", "costs", "tariff", "commodity", "raw material", "input cost", "meat", "coffee", "原物料", "通膨", "關稅", "成本", "咖啡", "肉"]
        negative_terms = ["split", "separation", "restructuring", "one-time", "spin", "分拆", "拆分"]
    elif intents.get("ai"):
        positive_terms = ["ai", "agentic", "openai", "automation", "digital", "sparky", "人工智慧", "自動化"]
    elif intents.get("guidance"):
        positive_terms = ["guidance", "outlook", "2026", "volume", "price", "mix", "pricing", "展望", "指引", "量", "價格", "定價"]

    best_score = -1e9
    best = sentences[0]

    for i in range(len(sentences)):
        window = " ".join(sentences[i:i + window_size]).strip()
        wl = window.lower()
        score = 0.0
        for tok in toks:
            if tok in wl:
                score += 1.2
        for term in positive_terms:
            if term in wl:
                score += 2.6
        for term in negative_terms:
            if term in wl:
                score -= 2.0
        if score > best_score:
            best_score = score
            best = window

    return best, best_score


def build_df(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    df = defaultdict(int)
    for entry in entries:
        for tok in set(entry["tokens"]):
            df[tok] += 1
    return dict(df)


def bm25_score(query_tokens: List[str], entry: Dict[str, Any], df: Dict[str, int], avgdl: float, N: int) -> float:
    k1 = 1.5
    b = 0.75
    score = 0.0
    token_counts = entry["token_counts"]
    dl = entry["length"]

    for tok in query_tokens:
        tf = token_counts.get(tok, 0)
        if tf <= 0:
            continue
        n_qi = df.get(tok, 0)
        idf = math.log(1 + (N - n_qi + 0.5) / (n_qi + 0.5))
        denom = tf + k1 * (1 - b + b * dl / max(avgdl, 1e-9))
        score += idf * ((tf * (k1 + 1)) / denom)
    return score


def phrase_bonus(query: str, text: str) -> float:
    q = query.lower().strip()
    t = text.lower()
    bonus = 0.0
    if q and q in t:
        bonus += 8.0

    phrases = [
        "market share", "free cash flow", "gross margin", "operating margin", "volume growth",
        "consumer sentiment", "price/mix", "openai", "agentic commerce", "earnings call",
        "guidance", "tariff", "promotional activity", "digital", "automation",
        "市占", "市佔", "自由現金流", "毛利率", "營業利益率", "指引", "展望", "促銷", "關稅", "創新"
    ]
    for ph in phrases:
        if ph in q and ph in t:
            bonus += 2.5
    return bonus


def metadata_bonus(query: str, entry: Dict[str, Any]) -> float:
    q = query.lower()
    meta = entry["metadata"]
    bonus = 0.0

    company_hits = expand_company_mentions(query)
    if company_hits and meta.get("company") in company_hits:
        bonus += 7.0
    elif company_hits:
        bonus -= 6.0

    fname = entry.get("filename_text", "")
    for tok in normalize_query_tokens(query):
        if tok in fname:
            bonus += 0.7

    vendor = str(meta.get("vendor", "unknown")).lower()
    bonus += VENDOR_QUALITY.get(vendor, 0.0)

    wants_call = any(k in q for k in ["earnings call", "法說", "法说", "transcript"])
    wants_10k = any(k in q for k in ["10-k", "年報", "年报", "annual report"])

    if wants_call and meta.get("doc_family") == "earnings_call":
        bonus += 10.0
    if wants_10k and meta.get("doc_type") == "10-K":
        bonus += 8.0
    if wants_call and meta.get("doc_family") != "earnings_call":
        bonus -= 5.0
    if wants_10k and meta.get("doc_type") != "10-K":
        bonus -= 3.0

    period = str(meta.get("period", "")).upper()
    if any(k in q for k in ["q4", "第四季", "第四季度"]):
        bonus += 3.5 if "Q4" in period else -2.5
    if any(k in q for k in ["q3", "第三季", "第三季度"]):
        bonus += 3.5 if "Q3" in period else -2.5
    if "2026" in q:
        bonus += 2.0 if "2026" in period else -1.5
    if "2025" in q:
        bonus += 1.5 if "2025" in period else -1.0

    return bonus


def concept_match_bonus(query: str, text: str) -> float:
    q = query.lower()
    t = text.lower()
    bonus = 0.0
    for aliases in CONCEPT_ALIASES.values():
        if any(alias in q for alias in aliases):
            hits = sum(1 for alias in aliases if alias in t)
            if hits:
                bonus += min(hits * 1.6, 7.0)
    return bonus


def entity_presence_adjustment(query: str, entry: Dict[str, Any]) -> float:
    companies = expand_company_mentions(query)
    if not companies:
        return 0.0
    text = entry["text"].lower()
    score = 0.0
    for comp in companies:
        aliases = COMPANY_ALIASES.get(comp, [])
        if any(alias in text for alias in aliases):
            score += 1.5
        elif entry["metadata"].get("doc_family") == "earnings_call":
            score -= 2.5
    return score


def junk_penalty(text: str, metadata: Dict[str, Any]) -> float:
    t = text.lower()
    penalty = 0.0
    for pat in JUNK_PATTERNS:
        if re.search(pat, t):
            penalty += 10.0
    if metadata.get("doc_family") == "earnings_call":
        if t.count("operator") + t.count("participants") + t.count("analyst") >= 8:
            penalty += 6.0
        if "earnings summary" in t and "eps" in t and "revenue" in t:
            penalty += 8.0
    return penalty


def coverage_bonus(query_tokens: List[str], entry: Dict[str, Any]) -> float:
    token_set = set(entry["tokens"])
    if not query_tokens:
        return 0.0
    hit = sum(1 for tok in set(query_tokens) if tok in token_set)
    coverage = hit / max(len(set(query_tokens)), 1)
    return coverage * 5.0


def score_chunk(query: str, query_tokens: List[str], entry: Dict[str, Any], df: Dict[str, int], avgdl: float, N: int) -> float:
    base = bm25_score(query_tokens, entry, df, avgdl, N)
    _, window_score = best_local_window(query, entry["text"])
    return (
        base
        + phrase_bonus(query, entry["text"])
        + metadata_bonus(query, entry)
        + coverage_bonus(query_tokens, entry)
        + concept_match_bonus(query, entry["text"])
        + entity_presence_adjustment(query, entry)
        + max(window_score, 0.0) * 1.8
        - junk_penalty(entry["text"], entry["metadata"])
    )


def dedupe_results(results: List[Dict[str, Any]], max_sources: int, top_k: int) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = defaultdict(int)
    seen_text = set()

    for item in results:
        text_key = re.sub(r"\s+", " ", item["text"]).strip()[:220]
        if text_key in seen_text:
            continue

        src = item["metadata"].get("source_file", "unknown")
        if source_counts[src] >= 2:
            continue

        existing_sources = {k["metadata"].get("source_file", "") for k in kept}
        if len(existing_sources) >= max_sources and src not in existing_sources:
            continue

        kept.append(item)
        seen_text.add(text_key)
        source_counts[src] += 1
        if len(kept) >= top_k:
            break

    return kept


def keyword_search(query: str, entries: List[Dict[str, Any]], top_k: int, max_sources: int) -> List[Dict[str, Any]]:
    query_tokens = strip_entity_and_time_tokens(normalize_query_tokens(query), query)
    if not query_tokens:
        return []

    df = build_df(entries)
    avgdl = statistics.mean([e["length"] for e in entries]) if entries else 1.0
    N = len(entries)

    scored: List[Dict[str, Any]] = []
    for entry in entries:
        s = score_chunk(query, query_tokens, entry, df, avgdl, N)
        if s > 0:
            item = dict(entry)
            item["score"] = round(s, 4)
            scored.append(item)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return dedupe_results(scored, max_sources=max_sources, top_k=top_k)


def lazy_import_vector_stack():
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        raise RuntimeError(
            "向量檢索依賴載入失敗，請檢查 chromadb / sentence-transformers / transformers / torch。"
        ) from exc
    return chromadb, SentenceTransformer


def vector_search(query: str, chroma_dir: str, collection_name: str, embedding_model_name: str, top_k: int) -> List[Dict[str, Any]]:
    chromadb, SentenceTransformer = lazy_import_vector_stack()
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_collection(name=collection_name)

    if collection.count() == 0:
        return []

    model = SentenceTransformer(embedding_model_name)
    q_emb = model.encode(
        [query],
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0].tolist()

    result = collection.query(query_embeddings=[q_emb], n_results=top_k)

    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    ids = result.get("ids", [[]])[0]
    dists = result.get("distances", [[]])[0] if result.get("distances") else [None] * len(docs)

    entries: List[Dict[str, Any]] = []
    for doc_id, doc, meta, dist in zip(ids, docs, metas, dists):
        score = 0.0 if dist is None else (1.0 / (1.0 + float(dist)))
        entries.append({
            "id": doc_id,
            "text": doc,
            "metadata": meta or {},
            "score": round(score, 4),
        })
    return entries


def format_citation(meta: Dict[str, Any]) -> str:
    company = meta.get("company", "?")
    family = meta.get("doc_family", "?")
    period = meta.get("period", "unknown")
    chunk = meta.get("chunk_index", "?")
    src = meta.get("source_file", "unknown")
    return f"[{company} | {family} | {period} | chunk {chunk} | {src}]"


def shorten(text: str, limit: int = 300) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " ..."


def best_snippet(query: str, text: str, limit: int = 280) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= limit:
        return clean
    window, _ = best_local_window(query, clean)
    window = re.sub(r"\s+", " ", window).strip()
    if len(window) <= limit:
        return window
    return shorten(window, limit)


def group_results_by_source(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[item["metadata"].get("source_file", "unknown")].append(item)
    return dict(grouped)


def build_context(results: List[Dict[str, Any]]) -> str:
    blocks = []
    for i, item in enumerate(results, start=1):
        blocks.append(f"[{i}] {format_citation(item['metadata'])}\n{item['text']}")
    return "\n\n".join(blocks)


def llm_is_configured(env: Dict[str, str]) -> bool:
    return bool(env.get("LITELLM_API_KEY") or env.get("LITELLM_BASE_URL"))


def resolve_llm_model(args: argparse.Namespace, env: Dict[str, str]) -> str:
    return args.model.strip() or env.get("LITELLM_MODEL", "gemini-2.5-flash")


def clamp_history_turns(history_turns: int) -> int:
    return max(1, int(history_turns))


def build_effective_query(
    query: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    history_turns: int = DEFAULT_HISTORY_TURNS,
) -> str:
    query = query.strip()
    if not conversation_history:
        return query

    keep_turns = clamp_history_turns(history_turns)
    recent_user_turns = [
        item.get("content", "").strip()
        for item in conversation_history
        if item.get("role") == "user" and item.get("content", "").strip()
    ][-keep_turns:]

    if not recent_user_turns:
        return query

    history_text = " | ".join(recent_user_turns)
    return f"對話背景：{history_text}\n目前問題：{query}"


def history_to_messages(
    conversation_history: Optional[List[Dict[str, str]]] = None,
    history_turns: int = DEFAULT_HISTORY_TURNS,
) -> List[Dict[str, str]]:
    if not conversation_history:
        return []

    keep_turns = clamp_history_turns(history_turns)
    max_messages = keep_turns * 2
    trimmed = conversation_history[-max_messages:]
    messages: List[Dict[str, str]] = []

    for item in trimmed:
        role = item.get("role", "")
        content = item.get("content", "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    return messages


def try_llm_answer(
    query: str,
    results: List[Dict[str, Any]],
    env: Dict[str, str],
    model_name: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    history_turns: int = DEFAULT_HISTORY_TURNS,
) -> Optional[str]:
    try:
        from litellm import completion
    except Exception:
        return None

    if not llm_is_configured(env):
        return None

    prompt = (
        "你是一個財報與法說會研究助理。請只根據提供的檢索內容回答，不要自行補造。"
        "若資訊不足，要明確說明。請使用繁體中文作答，並用 [1]、[2] 形式標示來源。"
        "若這是一個延續前文的追問，請結合先前對話一起理解當前問題。\n\n"
        f"問題：{query}\n\n檢索內容：\n{build_context(results)}"
    )

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "請根據上下文精準回答，不要自行編造。"},
    ]
    messages.extend(history_to_messages(conversation_history, history_turns=history_turns))
    messages.append({"role": "user", "content": prompt})

    kwargs: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
    }
    if env.get("LITELLM_API_KEY"):
        kwargs["api_key"] = env["LITELLM_API_KEY"]
    if env.get("LITELLM_BASE_URL"):
        kwargs["base_url"] = env["LITELLM_BASE_URL"]

    try:
        response = completion(**kwargs)
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logging.warning("LiteLLM 生成失敗，改用 extractive fallback：%s", exc)
        return None


def build_extractive_answer(query: str, results: List[Dict[str, Any]]) -> str:
    if not results:
        return (
            "找不到足夠相關的內容。\n\n"
            "建議你改寫問題、放寬公司或文件類型條件，或先確認 data/processed、manifest.json、chroma_db 是否存在。"
        )

    lines: List[str] = []
    lines.append(f"問題：{query}")
    lines.append("")
    lines.append("回答摘要：")
    for i, item in enumerate(results[:3], start=1):
        snippet = best_snippet(query, item["text"], 240)
        lines.append(f"- 重點 {i}：{snippet}")
    lines.append("")

    lines.append("關鍵證據：")
    for i, item in enumerate(results[:4], start=1):
        lines.append(f"{i}. {best_snippet(query, item['text'], 300)}")
        lines.append(f"   來源：{format_citation(item['metadata'])}")
        if "score" in item:
            lines.append(f"   分數：{item['score']}")
        lines.append("")

    grouped = group_results_by_source(results)
    lines.append("來源總覽：")
    for src, items in grouped.items():
        meta = items[0]["metadata"]
        lines.append(
            f"- {src}（公司={meta.get('company')}, 類型={meta.get('doc_family')}, 期間={meta.get('period')}, 命中 chunks={len(items)}）"
        )

    return "\n".join(lines).strip()


def run_single_query(
    args: argparse.Namespace,
    env: Dict[str, str],
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Tuple[int, str]:
    processed_dir = Path(args.processed_dir)
    manifest_path = Path(args.manifest_path)
    chroma_dir = args.chroma_dir.strip() or env["CHROMA_PERSIST_DIR"]
    query = args.query.strip()

    if not query:
        print("請提供問題；若不帶 --query，程式會自動進入互動模式。")
        return 1, ""

    effective_query = build_effective_query(
        query,
        conversation_history=conversation_history,
        history_turns=args.history_turns,
    )

    results: List[Dict[str, Any]] = []
    mode_used = args.mode

    if args.mode in {"auto", "vector"}:
        try:
            results = vector_search(
                query=effective_query,
                chroma_dir=chroma_dir,
                collection_name=args.collection_name,
                embedding_model_name=env["EMBEDDING_MODEL"],
                top_k=args.top_k,
            )
            if results:
                mode_used = "vector"
        except Exception as exc:
            if args.mode == "vector":
                logging.error("向量檢索失敗：%s", exc)
                return 1, ""
            logging.info("向量檢索不可用，退回 keyword 模式：%s", exc)

    if not results:
        manifest = load_manifest(manifest_path)
        entries = build_keyword_index(processed_dir, manifest)
        entries = filter_entries(entries, company=args.company, doc_family=args.doc_family)
        results = keyword_search(effective_query, entries, args.top_k, args.max_sources)
        mode_used = "keyword"

    print(f"檢索模式：{mode_used}")
    print(f"Top K：{args.top_k}")
    if args.company:
        print(f"公司過濾：{args.company}")
    if args.doc_family:
        print(f"文件族群過濾：{args.doc_family}")
    print("")

    model_name = resolve_llm_model(args, env)
    should_try_llm = args.use_llm or llm_is_configured(env)
    answer = (
        try_llm_answer(
            query=query,
            results=results,
            env=env,
            model_name=model_name,
            conversation_history=conversation_history,
            history_turns=args.history_turns,
        )
        if should_try_llm
        else None
    )
    final_answer = answer if answer else build_extractive_answer(query, results)
    print(final_answer)

    if args.show_context and results:
        print("\n===== Retrieved Context =====")
        for item in results:
            print(format_citation(item["metadata"]))
            if args.show_scores and "score" in item:
                print(f"score={item['score']}")
            print(best_snippet(query, item["text"], 520))
            print("")

    return 0, final_answer


def interactive_loop(args: argparse.Namespace, env: Dict[str, str]) -> int:
    print("進入互動模式。輸入 exit / quit 可離開。")
    print(f"目前會保留最近 {clamp_history_turns(args.history_turns)} 輪對話歷史。")

    conversation_history: List[Dict[str, str]] = []
    keep_turns = clamp_history_turns(args.history_turns)

    while True:
        try:
            q = input("\n請輸入問題> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已離開。")
            return 0

        if q.lower() in {"exit", "quit"}:
            print("已離開。")
            return 0
        if not q:
            continue

        args.query = q
        status, answer = run_single_query(args, env, conversation_history=conversation_history)
        if status != 0:
            continue

        conversation_history.append({"role": "user", "content": q})
        conversation_history.append({"role": "assistant", "content": answer})
        conversation_history = conversation_history[-(keep_turns * 2):]


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)
    env = load_env()

    if env.get("EMBEDDING_PROVIDER", "sentence-transformers") != "sentence-transformers":
        logging.error("目前正式提交版僅支援 EMBEDDING_PROVIDER=sentence-transformers")
        return 1

    if args.interactive or not args.query.strip():
        return interactive_loop(args, env)

    status, _ = run_single_query(args, env)
    return status


if __name__ == "__main__":
    raise SystemExit(main())