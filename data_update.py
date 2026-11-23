#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

try:
    from pypdf import PdfReader
except ImportError as exc:
    raise ImportError("請先安裝 pypdf：pip install pypdf") from exc


DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_MANIFEST_PATH = Path("data/manifest.json")
DEFAULT_CHROMA_DIR = "./chroma_db"
DEFAULT_COLLECTION_NAME = "financial_reports"
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


@dataclass
class ChunkRecord:
    chunk_id: str
    text: str
    metadata: Dict[str, Any]


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def ensure_directories(raw_dir: Path, processed_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)


def load_env() -> Tuple[str, str, str]:
    load_dotenv()
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
    embedding_model_name = os.getenv(
        "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
    )
    chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIR", DEFAULT_CHROMA_DIR)
    return embedding_provider, embedding_model_name, chroma_persist_dir


def compute_file_hash(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            hasher.update(block)
    return hasher.hexdigest()


def load_manifest(manifest_path: Path) -> Dict[str, Any]:
    if not manifest_path.exists():
        return {}
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest_path: Path, manifest: Dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def sanitize_filename_stem(file_path: Path) -> str:
    return file_path.stem


def infer_company_name(file_path: Path) -> str:
    parts = file_path.stem.split("_")
    return parts[0] if parts else file_path.stem


def infer_doc_type(file_path: Path) -> str:
    name_upper = file_path.stem.upper()
    if "TRANSCRIPT" in name_upper:
        return "Transcript"
    if "10-K" in name_upper or "10K" in name_upper:
        return "10-K"
    if "10-Q" in name_upper or "10Q" in name_upper:
        return "10-Q"
    return file_path.suffix.lower().lstrip(".")


def infer_doc_family(file_path: Path) -> str:
    name_upper = file_path.stem.upper()
    if "TRANSCRIPT" in name_upper:
        return "earnings_call"
    if "10-K" in name_upper or "10K" in name_upper:
        return "annual_report"
    if "10-Q" in name_upper or "10Q" in name_upper:
        return "quarterly_report"
    return "note"


def infer_period(file_path: Path) -> str:
    stem = file_path.stem
    patterns = [
        r"(Q[1-4]_FY\d{4})",
        r"(Q[1-4]_\d{4})",
        r"(FY\d{4})",
        r"(Q[1-4]FY\d{4})",
        r"(Q[1-4]\d{4})",
    ]
    for pattern in patterns:
        m = re.search(pattern, stem, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return "unknown"


def infer_source_vendor(file_path: Path) -> str:
    stem = file_path.stem.lower()
    vendors = [
        "seekingalpha",
        "investing",
        "motleyfool",
        "factset",
        "stockinsights",
        "insidermonkey",
        "sec",
    ]
    for vendor in vendors:
        if vendor in stem:
            return vendor
    return "unknown"


def read_pdf_text(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    pages_text: List[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logging.warning("PDF 第 %d 頁抽取失敗：%s", i + 1, exc)
            text = ""
        if text.strip():
            pages_text.append(f"\n\n[PAGE {i + 1}]\n{text}")
    return "\n".join(pages_text)


def read_text_file(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="ignore")


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_common_page_artifacts(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines: List[str] = []
    generic_noise_patterns = [
        r"^\s*\[PAGE\s+\d+\]\s*$",
        r"^\s*\d+\s*$",
        r"^\s*\d{4}/\d+/\d+.*$",
        r"^\s*https?://\S+\s*$",
        r"^\s*Copyright ©.*$",
        r"^\s*Total Pages:\s*\d+\s*$",
        r"^\s*1-877-FACTSET.*$",
        r"^\s*www\.callstreet\.com.*$",
        r"^\s*Image source:.*$",
        r"^\s*FREE ARTICLE.*$",
        r"^\s*Follow us.*$",
        r"^\s*Accessibility Menu.*$",
        r"^\s*View all comments.*$",
        r"^\s*Summarize with AI.*$",
        r"^\s*Need a quote from.*$",
        r"^\s*#1 AI Stock to Buy.*$",
    ]
    compiled = [re.compile(p, re.IGNORECASE) for p in generic_noise_patterns]

    for line in lines:
        stripped = line.strip()
        if stripped in {"TRUE", "FALSE", "True", "False"}:
            continue
        if any(p.match(stripped) for p in compiled):
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
    cleaned = re.sub(r"[ ]{2,}", " ", cleaned)
    return cleaned.strip()


def clean_10k_text(text: str) -> str:
    text = remove_common_page_artifacts(text)
    lines = text.splitlines()
    cleaned_lines: List[str] = []
    noise_patterns = [
        r"^\s*UNITED STATES\s*$",
        r"^\s*SECURITIES AND EXCHANGE COMMISSION\s*$",
        r"^\s*WASHINGTON,\s*D\.?C\.?\s*20549\s*$",
        r"^\s*FORM\s+10-K\s*$",
        r"^\s*FORM\s+10-Q\s*$",
        r"^\s*FORM 10-K TABLE OF CONTENTS\s*$",
        r"^\s*TABLE OF CONTENTS\s*$",
        r"^\s*DOCUMENTS INCORPORATED BY REFERENCE\s*$",
        r"^\s*Yes\s*[☒☐xXoOýþ¨].*No\s*[☒☐xXoOýþ¨].*$",
    ]
    compiled = [re.compile(p, re.IGNORECASE) for p in noise_patterns]

    for line in lines:
        stripped = line.strip()
        if any(p.match(stripped) for p in compiled):
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ ]{2,}", " ", cleaned)
    return cleaned.strip()


def is_market_widget_line(stripped: str) -> bool:
    patterns = [
        r"^S&P 500$",
        r"^DJI$",
        r"^NASDA$",
        r"^[\d,]+(?:\.\d+)?$",
        r"^[+-]?\d+(?:\.\d+)?%$",
        r"^[+-]?\d+(?:\.\d+)?$",
        r"^\(/quote/.*\)$",
    ]
    return any(re.match(p, stripped) for p in patterns)


def is_junk_transcript_line(stripped: str) -> bool:
    if not stripped:
        return False

    phrases = [
        "Top 10 Stocks to Buy Now",
        "Explore Premium Services",
        "Receive real-time insider trading",
        "Enter Your Email",
        "Get Email Alerts",
        "Subscribe with Google",
        "Click here",
        "privacy policy",
        "Accessibility Menu",
        "View all comments",
        "Follow Walmart Inc.",
        "NEWS (HTTPS://",
        "TRANSCRIPTS (HTTPS://",
        "Follow\nSummary AI Assistant",
        "Summary AI Assistant",
        "FREE ARTICLE",
        "Image source:",
        "Published on",
        "Follow us",
    ]
    if any(phrase.lower() in stripped.lower() for phrase in phrases):
        return True

    if stripped.startswith("http://") or stripped.startswith("https://"):
        return True
    if "utm_source=" in stripped or "utm_medium=" in stripped:
        return True
    if stripped.startswith("(") and stripped.endswith(")") and "http" in stripped.lower():
        return True
    if is_market_widget_line(stripped):
        return True

    compact = stripped.replace(" ", "")
    if "privacypolicy" in compact.lower() or "getemailalerts" in compact.lower() or "subscribewithgoogle" in compact.lower():
        return True
    if re.match(r"^[\$\d\.,\-\+% ]{8,}$", stripped):
        return True
    if len(stripped) >= 20 and re.match(r"^(?:[A-Za-z]\s+){8,}[A-Za-z]$", stripped):
        return True

    return False


def trim_transcript_preamble(text: str, vendor: str) -> str:
    lines = text.splitlines()
    start_idx = 0

    anchor_patterns = [
        re.compile(r"^\s*Full Conference Call Transcript\s*$", re.IGNORECASE),
        re.compile(r"^\s*Full transcript.*$", re.IGNORECASE),
        re.compile(r"^\s*Operator\s*[:：]", re.IGNORECASE),
        re.compile(r"^\s*MANAGEMENT DISCUSSION SECTION\s*$", re.IGNORECASE),
        re.compile(r"^\s*Q&A Session\s*$", re.IGNORECASE),
        re.compile(r"^\s*QUESTION AND ANSWER SECTION\s*$", re.IGNORECASE),
    ]

    for i, line in enumerate(lines):
        if any(p.match(line.strip()) for p in anchor_patterns):
            start_idx = i
            break

    trimmed = lines[start_idx:]

    if vendor == "factset":
        for i, line in enumerate(trimmed):
            if re.match(r"^\s*Operator\s*[:：]", line.strip(), re.IGNORECASE):
                trimmed = trimmed[i:]
                break

    return "\n".join(trimmed).strip()


def clean_transcript_text(text: str, vendor: str) -> str:
    text = remove_common_page_artifacts(text)
    text = trim_transcript_preamble(text, vendor)

    patterns_to_remove = [
        r"^\s*Corrected Transcript\s*$",
        r"^\s*Transcripts\s*$",
        r"^\s*Presentation\s*$",
        r"^\s*Q&A Session\s*$",
        r"^\s*QUESTION AND ANSWER SECTION\s*$",
        r"^\s*MANAGEMENT DISCUSSION SECTION\s*$",
        r"^\s*OTHER PARTICIPANTS\s*$",
        r"^\s*CORPORATE PARTICIPANTS\s*$",
        r"^\s*Published on .*?$",
        r"^\s*Published .*?$",
        r"^\s*By .*?$",
        r"^\s*Follow\s*$",
        r"^\s*Summary AI Assistant\s*$",
        r"^\s*Takeaways\s*$",
        r"^\s*TAKEAWAYS\s*$",
        r"^\s*SUMMARY\s*$",
        r"^\s*Summary\s*$",
        r"^\s*Risks\s*$",
        r"^\s*Industry glossary\s*$",
        r"^\s*INDUSTRY GLOSSARY\s*$",
        r"^\s*Full Conference Call Transcript\s*$",
        r"^\s*Full transcript.*$",
        r"^\s*Operator Instructions.*$",
        r"^\s*\[Operator Instructions\].*$",
        r"^\s*Operator: \[Operator Instructions\].*$",
        r"^\s*Please limit yourself to one question.*$",
        r"^\s*Date\s*$",
        r"^\s*CALL PARTICIPANTS\s*$",
        r"^\s*Call participants\s*$",
        r"^\s*Company Participants\s*$",
        r"^\s*Conference Call Participants\s*$",
        r"^\s*Need a quote from .*?$",
        r"^\s*Follow .*?$",
        r"^\s*Title\s*$",
        r"^\s*Operator\s*$",
        r"^\s*Q[1-4]\s+\d{4}\s+Earnings Call\s*$",
        r"^\s*Q[1-4]\s+FY\d{4}\s+Earnings Call\s*$",
        r"^\s*\d{1,2}-[A-Za-z]{3}-\d{4}\s*$",
        r"^\s*The .*\([A-Z]{1,5}\)\s*$",
    ]
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns_to_remove]

    lines = text.splitlines()
    cleaned_lines: List[str] = []

    for line in lines:
        stripped = line.strip()

        if is_junk_transcript_line(stripped):
            continue
        if any(p.match(stripped) for p in compiled):
            continue

        if re.match(r"^\s*202\d/\d+/\d+.*$", stripped):
            continue
        if re.match(r"^\s*\(https?://.*\)\s*$", stripped, re.IGNORECASE):
            continue
        if re.match(r"^\s*\/author\/\d+.*$", stripped):
            continue
        if re.match(r"^\s*\(/\).*", stripped):
            continue
        if re.match(r"^\s*\▲\s*S&P 500.*$", stripped):
            continue
        if re.match(r"^\s*\$?\d+[\d,]*(?:\.\d+)?\s*[+-]\d.*$", stripped):
            continue
        if stripped.count("http") >= 1:
            continue

        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\.{8,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ ]{2,}", " ", cleaned)
    return cleaned.strip()


def clean_text(raw_text: str, file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    doc_family = infer_doc_family(file_path)
    vendor = infer_source_vendor(file_path)
    text = normalize_whitespace(raw_text)

    if suffix == ".pdf":
        if doc_family in {"annual_report", "quarterly_report"}:
            return normalize_whitespace(clean_10k_text(text))
        if doc_family == "earnings_call":
            return normalize_whitespace(clean_transcript_text(text, vendor))
        return normalize_whitespace(remove_common_page_artifacts(text))

    if doc_family == "earnings_call":
        return normalize_whitespace(clean_transcript_text(text, vendor))
    if doc_family in {"annual_report", "quarterly_report"}:
        return normalize_whitespace(clean_10k_text(text))

    return normalize_whitespace(text)


def extract_and_clean_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        raw_text = read_pdf_text(file_path)
    elif suffix in {".txt", ".md"}:
        raw_text = read_text_file(file_path)
    else:
        raise ValueError(f"不支援的檔案格式：{suffix}")
    return clean_text(raw_text, file_path)


def write_processed_text(processed_dir: Path, raw_file_path: Path, cleaned_text: str) -> Path:
    out_name = f"{sanitize_filename_stem(raw_file_path)}.txt"
    out_path = processed_dir / out_name
    out_path.write_text(cleaned_text, encoding="utf-8")
    return out_path


def split_text_into_chunks(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size 必須大於 0")
    if overlap < 0:
        raise ValueError("overlap 不可小於 0")
    if overlap >= chunk_size:
        raise ValueError("overlap 必須小於 chunk_size")

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


def build_chunk_records(source_file: Path, processed_file: Path, cleaned_text: str, chunk_size: int, overlap: int) -> List[ChunkRecord]:
    company = infer_company_name(source_file)
    doc_type = infer_doc_type(source_file)
    doc_family = infer_doc_family(source_file)
    period = infer_period(source_file)
    vendor = infer_source_vendor(source_file)
    chunks = split_text_into_chunks(cleaned_text, chunk_size=chunk_size, overlap=overlap)

    records: List[ChunkRecord] = []
    for idx, chunk_text in enumerate(chunks):
        chunk_id = f"{source_file.stem}::chunk_{idx:04d}"
        metadata = {
            "source_file": source_file.name,
            "processed_file": processed_file.name,
            "company": company,
            "doc_type": doc_type,
            "doc_family": doc_family,
            "period": period,
            "vendor": vendor,
            "chunk_index": idx,
        }
        records.append(ChunkRecord(chunk_id=chunk_id, text=chunk_text, metadata=metadata))
    return records


def lazy_import_chromadb():
    try:
        import chromadb
    except ImportError as exc:
        raise ImportError("缺少 chromadb。請先安裝：pip install chromadb") from exc
    return chromadb


def get_chroma_collection(persist_dir: str, collection_name: str):
    chromadb = lazy_import_chromadb()
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(name=collection_name)
    return client, collection


def reset_chroma(persist_dir: str) -> None:
    chroma_path = Path(persist_dir)
    if chroma_path.exists():
        shutil.rmtree(chroma_path)
        logging.info("已刪除 ChromaDB 資料夾：%s", chroma_path)


def delete_file_chunks_from_chroma(collection, source_file_name: str) -> None:
    try:
        collection.delete(where={"source_file": source_file_name})
        logging.info("已刪除舊 chunks：%s", source_file_name)
    except Exception as exc:
        logging.warning("刪除舊 chunks 時出現警告（可忽略）：%s", exc)


def lazy_load_sentence_transformer(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "缺少 sentence-transformers。請先安裝：pip install sentence-transformers"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            "載入 sentence-transformers 失敗。請檢查 transformers / torch 版本。"
        ) from exc

    try:
        model = SentenceTransformer(model_name)
    except Exception as exc:
        raise RuntimeError(f"初始化 embedding 模型失敗：{model_name}") from exc
    return model


def embed_texts(model, texts: List[str]) -> List[List[float]]:
    embeddings = model.encode(
        texts,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embeddings.tolist()


def upsert_chunks_to_chroma(collection, model, chunk_records: List[ChunkRecord], batch_size: int = 32) -> None:
    if not chunk_records:
        return
    for i in range(0, len(chunk_records), batch_size):
        batch = chunk_records[i:i + batch_size]
        ids = [r.chunk_id for r in batch]
        docs = [r.text for r in batch]
        metas = [r.metadata for r in batch]
        embs = embed_texts(model, docs)
        collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
    logging.info("已寫入 %d 個 chunks 到 ChromaDB", len(chunk_records))


def rebuild_all(processed_dir: Path, manifest_path: Path, chroma_dir: str, skip_embedding: bool) -> None:
    if processed_dir.exists():
        shutil.rmtree(processed_dir)
        logging.info("已刪除 processed 資料夾：%s", processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)

    if manifest_path.exists():
        manifest_path.unlink()
        logging.info("已刪除 manifest：%s", manifest_path)

    if not skip_embedding:
        reset_chroma(chroma_dir)


def collect_supported_files(raw_dir: Path) -> List[Path]:
    if not raw_dir.exists():
        return []
    files = [p for p in raw_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    files.sort()
    return files


def should_process_file(file_path: Path, manifest: Dict[str, Any], force_rebuild: bool) -> bool:
    if force_rebuild:
        return True
    current_hash = compute_file_hash(file_path)
    old_info = manifest.get(file_path.name)
    if old_info is None:
        return True
    return old_info.get("sha256") != current_hash


def delete_processed_file(processed_dir: Path, processed_file_name: str) -> None:
    processed_path = processed_dir / processed_file_name
    if processed_path.exists():
        processed_path.unlink()
        logging.info("已刪除 processed 檔：%s", processed_path)


def sync_removed_files(
    manifest: Dict[str, Any],
    raw_files: List[Path],
    processed_dir: Path,
    manifest_path: Path,
    collection,
    skip_embedding: bool,
) -> int:
    current_raw_names = {p.name for p in raw_files}
    removed_files = sorted(set(manifest.keys()) - current_raw_names)

    if not removed_files:
        return 0

    logging.info("偵測到 %d 個已從 raw 移除的檔案，開始同步刪除。", len(removed_files))

    for source_file_name in removed_files:
        old_info = manifest.get(source_file_name, {})
        processed_file_name = old_info.get("processed_file")
        if processed_file_name:
            delete_processed_file(processed_dir, processed_file_name)

        if not skip_embedding and collection is not None:
            delete_file_chunks_from_chroma(collection, source_file_name)
        elif old_info.get("embedding_indexed"):
            logging.warning(
                "檔案 %s 曾建立過向量，但本次使用 --skip-embedding，未同步刪除 Chroma 中舊資料。",
                source_file_name,
            )

        manifest.pop(source_file_name, None)
        logging.info("已從 manifest 移除：%s", source_file_name)

    save_manifest(manifest_path, manifest)
    return len(removed_files)


def append_chunk_preview(preview_path: Path, file_path: Path, chunk_records: List[ChunkRecord], max_chunks: int = 3, max_chars: int = 500) -> None:
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    with preview_path.open("a", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"FILE: {file_path.name}\n")
        f.write(f"TOTAL_CHUNKS: {len(chunk_records)}\n")
        f.write("=" * 80 + "\n\n")
        for record in chunk_records[:max_chunks]:
            snippet = record.text[:max_chars].strip()
            f.write(f"CHUNK_ID: {record.chunk_id}\n")
            f.write(f"METADATA: {json.dumps(record.metadata, ensure_ascii=False)}\n")
            f.write("TEXT:\n")
            f.write(snippet + "\n")
            f.write("\n" + "-" * 80 + "\n\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="更新 RAG 知識庫：抽取文字、清理、chunk、embedding、寫入 ChromaDB")
    parser.add_argument("--rebuild", action="store_true", help="清空 processed、manifest、ChromaDB 後全量重建")
    parser.add_argument("--skip-embedding", action="store_true", help="只做抽文字、清理、chunk 與 manifest，不做 embedding / ChromaDB")
    parser.add_argument("--chunk-size", type=int, default=1200, help="每個 chunk 的字元長度（預設：1200）")
    parser.add_argument("--overlap", type=int, default=200, help="相鄰 chunk 的重疊字元數（預設：200）")
    parser.add_argument("--collection-name", type=str, default=DEFAULT_COLLECTION_NAME, help="Chroma collection 名稱")
    parser.add_argument("--raw-dir", type=str, default=str(DEFAULT_RAW_DIR), help="原始資料夾路徑")
    parser.add_argument("--processed-dir", type=str, default=str(DEFAULT_PROCESSED_DIR), help="processed 資料夾路徑")
    parser.add_argument("--manifest-path", type=str, default=str(DEFAULT_MANIFEST_PATH), help="manifest 檔案路徑")
    parser.add_argument("--chroma-dir", type=str, default="", help="覆蓋 .env 中 CHROMA_PERSIST_DIR")
    parser.add_argument("--only-file", type=str, default="", help="只處理特定檔名，例如 KO_Transcript_Q3_2025_FactSet.pdf")
    parser.add_argument("--save-chunk-preview", type=str, default="", help="將 chunk 預覽輸出到指定檔案")
    parser.add_argument("--preview-chunks", type=int, default=3, help="chunk 預覽筆數（預設：3）")
    parser.add_argument("--preview-chars", type=int, default=500, help="每個 preview chunk 顯示的字數（預設：500）")
    parser.add_argument("--verbose", action="store_true", help="顯示詳細訊息")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(verbose=args.verbose)

    raw_dir = Path(args.raw_dir)
    processed_dir = Path(args.processed_dir)
    manifest_path = Path(args.manifest_path)
    ensure_directories(raw_dir, processed_dir)

    embedding_provider, embedding_model_name, env_chroma_dir = load_env()
    chroma_dir = args.chroma_dir.strip() or env_chroma_dir

    logging.info("Embedding provider: %s", embedding_provider)
    logging.info("Embedding model: %s", embedding_model_name)
    logging.info("Chroma persist dir: %s", chroma_dir)
    logging.info("Skip embedding: %s", args.skip_embedding)

    if embedding_provider != "sentence-transformers":
        logging.error("目前正式提交版僅支援 EMBEDDING_PROVIDER=sentence-transformers")
        sys.exit(1)

    if args.only_file:
        logging.info("Only file: %s", args.only_file)
    if args.save_chunk_preview:
        logging.info("Preview output: %s", args.save_chunk_preview)

    if args.rebuild:
        logging.info("執行全量重建模式 --rebuild")
        rebuild_all(processed_dir, manifest_path, chroma_dir, args.skip_embedding)

    ensure_directories(raw_dir, processed_dir)
    raw_files = collect_supported_files(raw_dir)
    manifest = load_manifest(manifest_path)

    collection = None
    if not args.skip_embedding and not args.only_file:
        _, collection = get_chroma_collection(
            persist_dir=chroma_dir,
            collection_name=args.collection_name,
        )

    removed_count = 0
    if not args.only_file:
        removed_count = sync_removed_files(
            manifest=manifest,
            raw_files=raw_files,
            processed_dir=processed_dir,
            manifest_path=manifest_path,
            collection=collection,
            skip_embedding=args.skip_embedding,
        )

    if not raw_files:
        if removed_count > 0:
            logging.info("raw 資料夾目前沒有檔案，已完成刪除同步。")
        else:
            logging.warning("找不到支援的檔案，請確認 %s 中有 pdf/txt/md", raw_dir)
        return

    if args.only_file:
        raw_files = [p for p in raw_files if p.name == args.only_file]
        if not raw_files:
            logging.error("找不到指定檔案：%s", args.only_file)
            sys.exit(1)

    files_to_process: List[Path] = []
    skipped_count = 0

    for file_path in raw_files:
        if should_process_file(file_path, manifest, args.rebuild):
            files_to_process.append(file_path)
        else:
            skipped_count += 1

    if not files_to_process:
        logging.info("沒有需要更新的檔案。")
        logging.info("跳過檔案數：%d", skipped_count)
        logging.info("已同步刪除檔案數：%d", removed_count)
        return

    preview_path: Optional[Path] = None
    if args.save_chunk_preview:
        preview_path = Path(args.save_chunk_preview)
        if preview_path.exists() and args.rebuild:
            preview_path.unlink()

    model = None
    if not args.skip_embedding:
        if collection is None:
            _, collection = get_chroma_collection(
                persist_dir=chroma_dir,
                collection_name=args.collection_name,
            )
        logging.info("載入 sentence-transformers embedding 模型中，請稍候...")
        model = lazy_load_sentence_transformer(embedding_model_name)

    processed_count = 0
    total_chunks = 0
    failed_files = 0

    for file_path in files_to_process:
        logging.info("開始處理：%s", file_path.name)
        try:
            cleaned_text = extract_and_clean_text(file_path)
            if not cleaned_text.strip():
                logging.warning("清理後為空，跳過：%s", file_path.name)
                continue

            processed_path = write_processed_text(processed_dir, file_path, cleaned_text)
            logging.info("已輸出 processed 檔：%s", processed_path)

            chunk_records = build_chunk_records(
                source_file=file_path,
                processed_file=processed_path,
                cleaned_text=cleaned_text,
                chunk_size=args.chunk_size,
                overlap=args.overlap,
            )
            if not chunk_records:
                logging.warning("未產生任何 chunks，跳過：%s", file_path.name)
                continue

            if preview_path is not None:
                append_chunk_preview(
                    preview_path=preview_path,
                    file_path=file_path,
                    chunk_records=chunk_records,
                    max_chunks=args.preview_chunks,
                    max_chars=args.preview_chars,
                )

            if not args.skip_embedding:
                delete_file_chunks_from_chroma(collection, file_path.name)
                upsert_chunks_to_chroma(collection, model, chunk_records)

            manifest[file_path.name] = {
                "sha256": compute_file_hash(file_path),
                "processed_file": processed_path.name,
                "num_chunks": len(chunk_records),
                "doc_type": infer_doc_type(file_path),
                "doc_family": infer_doc_family(file_path),
                "period": infer_period(file_path),
                "embedding_indexed": not args.skip_embedding,
            }
            save_manifest(manifest_path, manifest)

            processed_count += 1
            total_chunks += len(chunk_records)
            logging.info("完成：%s | chunks=%d", file_path.name, len(chunk_records))

        except Exception as exc:
            failed_files += 1
            logging.exception("處理檔案失敗：%s | %s", file_path.name, exc)

    logging.info("=== 更新完成 ===")
    logging.info("實際處理檔案數：%d", processed_count)
    logging.info("跳過檔案數：%d", skipped_count)
    logging.info("已同步刪除檔案數：%d", removed_count)
    logging.info("失敗檔案數：%d", failed_files)
    logging.info("新增 / 更新 chunks 總數：%d", total_chunks)

    if failed_files > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()