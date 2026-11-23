#!/usr/bin/env python3
"""
wiki_lint.py — LLM Wiki 的「檢查節點」（確定性檢查，不靠 LLM 自評）

用途
  AI 每次寫完 / 改完 Wiki 頁面後都要跑這支程式；沒有 error 才算通過。
  檢查的是「AI 寫的東西」跟「原始文件」之間有沒有對得上，而不是文筆好不好。

Wiki 頁面的寫法（詳見 wiki/SCHEMA.md）
  * 一條主張 = 一行（list item 或段落）。
  * 主張後面用  {{來源id: "原文逐字引文"}}  附上證據；多段原文用 ... 串接。
  * 引文必須能在 data/processed/<file>.txt（HW3 data_update.py 的輸出）中逐字找到。
  * 主張裡的數字必須出現在同一行的引文裡；若是推算值，要寫 <!--calc: 4-3=1-->，
    本程式會驗算，並確認運算元真的出現在引文中。
  * 標題含「虛構」或「通則」的小節（教學用假想數字、名詞定義）不檢查數字；簡報引用時必須標示。

錯誤代碼
  E-FM       frontmatter 缺欄位 / 格式錯
  E-SRC      來源登錄錯誤（檔案不存在、sha256 與 manifest 不符）
  E-QUOTE    引文在原文中找不到
  E-QSHORT   引文太短（< 20 字元，容易誤中）
  E-NUM      主張中的數字沒有被引文支持
  E-NOEVID   含數字的主張沒有附證據
  E-CALC     <!--calc--> 算式錯誤或運算元不在引文中
  E-LINK     [[連結]] 指向不存在的頁面
  E-INDEX    頁面沒有被列在 index.md
  E-LOG      來源沒有 log.md 的 ingest 紀錄
  E-SECTION  證據行放錯小節（例如放在「容易誤會」底下）
  W-ORPHAN   沒有任何頁面連到它
  W-SINGLE   概念頁只被一份來源支持
  W-LONGQ    引文過長（> 400 字元）

用法
  python wiki_lint.py                       # 檢查整個 wiki/
  python wiki_lint.py --record logs/runs.jsonl --label "batch1-round1"
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent
WIKI = ROOT / "wiki"
PROCESSED = ROOT / "data" / "processed"
MANIFEST = ROOT / "data" / "manifest.json"

EVID_RE = re.compile(r'\{\{\s*([a-z0-9][a-z0-9\-]*)\s*:\s*"(.+?)"\s*\}\}')
LINK_RE = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]")
CALC_RE = re.compile(r"<!--\s*calc:\s*(.+?)\s*-->")
COMMENT_RE = re.compile(r"<!--.*?-->")
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    # 序數（eighth consecutive quarter → 8）
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}


# --------------------------------------------------------------------------- helpers
def norm(text: str) -> str:
    """把 PDF 抽字與引文都壓成同一種寫法再比對（引號、破折號、空白、連字號）。"""
    t = (
        text.replace("’", "'").replace("‘", "'")
        .replace("“", '"').replace("”", '"')
        .replace("–", "-").replace("—", "-").replace("­", "")
    )
    t = re.sub(r"\s+", " ", t).lower()
    t = re.sub(r"\s*-\s*", "-", t)
    return t


def to_float(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def numbers_in_quote(q: str) -> Set[float]:
    """引文中出現過的數字（含 one/two... 與 'a point' 這種英文寫法）。"""
    out: Set[float] = set()
    for m in NUM_RE.finditer(q):
        v = to_float(m.group(0))
        if v is not None:
            out.add(v)
    ql = q.lower()
    for w, v in WORD_NUM.items():
        if re.search(rf"\b{w}\b", ql):
            out.add(float(v))
    if re.search(r"\ba (?:percentage )?point\b", ql):
        out.add(1.0)
    return out


def numbers_in_claim(line: str) -> List[Tuple[str, float]]:
    """主張文字中的數字（先剝掉證據、連結、年份、Q4/FY2026 這類標籤）。"""
    t = EVID_RE.sub(" ", line)
    t = LINK_RE.sub(" ", t)
    t = COMMENT_RE.sub(" ", t)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", t)
    t = re.sub(r"\b(?:Q|H)\d\b", " ", t)
    t = re.sub(r"\b10-[KQ]\b|批次\s*\d+|\bD\d{2}\b|Q&A", " ", t)
    t = re.sub(r"\bFY\s?\d{2,4}\b", " ", t)
    t = re.sub(r"\b(?:19|20)\d{2}\b", " ", t)
    res = []
    for m in NUM_RE.finditer(t):
        v = to_float(m.group(0))
        if v is not None:
            res.append((m.group(0), v))
    return res


def safe_eval(expr: str) -> float:
    node = ast.parse(expr, mode="eval")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
               ast.Mult, ast.Div, ast.USub, ast.UAdd)
    for n in ast.walk(node):
        if not isinstance(n, allowed):
            raise ValueError("只允許數字與 + - * /")
    return float(eval(compile(node, "<calc>", "eval"), {"__builtins__": {}}, {}))


def parse_frontmatter(text: str) -> Tuple[Dict[str, str], int]:
    """回傳 (frontmatter dict, body 起始行號 0-based)。只支援 key: value。"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, 0
    fm: Dict[str, str] = {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return fm, i + 1
        if ":" in lines[i]:
            k, v = lines[i].split(":", 1)
            fm[k.strip()] = v.strip()
    return {}, 0


# --------------------------------------------------------------------------- issues
class Issues:
    def __init__(self) -> None:
        self.items: List[Dict] = []

    def add(self, code: str, path: Path, line: int, msg: str) -> None:
        self.items.append({
            "code": code,
            "severity": "error" if code.startswith("E-") else "warn",
            "file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "line": line,
            "msg": msg,
        })

    @property
    def errors(self) -> List[Dict]:
        return [i for i in self.items if i["severity"] == "error"]

    @property
    def warnings(self) -> List[Dict]:
        return [i for i in self.items if i["severity"] == "warn"]


# --------------------------------------------------------------------------- main checks
def load_sources(issues: Issues) -> Dict[str, Dict]:
    """讀 wiki/sources/*.md 的 frontmatter，登錄來源，並驗證檔案與 sha256。"""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    registry: Dict[str, Dict] = {}
    for p in sorted((WIKI / "sources").glob("*.md")):
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        need = ["id", "title", "file", "raw", "sha256", "company", "period", "kind", "batch"]
        miss = [k for k in need if not fm.get(k)]
        if miss:
            issues.add("E-FM", p, 1, f"source frontmatter 缺欄位：{', '.join(miss)}")
            continue
        sid = fm["id"]
        if sid != p.stem:
            issues.add("E-FM", p, 1, f"id ({sid}) 必須等於檔名 ({p.stem})")
        txt = PROCESSED / f"{fm['file']}.txt"
        if not txt.exists():
            issues.add("E-SRC", p, 1, f"找不到 processed 檔：data/processed/{fm['file']}.txt")
            continue
        m = manifest.get(fm["raw"])
        if not m:
            issues.add("E-SRC", p, 1, f"manifest.json 沒有 {fm['raw']}")
        elif not m.get("sha256", "").startswith(fm["sha256"]):
            issues.add("E-SRC", p, 1,
                       f"sha256 不符：頁面 {fm['sha256']} / manifest {m.get('sha256','')[:12]}（原始檔已變更？Wiki 可能過期）")
        registry[sid] = {"path": p, "fm": fm, "text": norm(txt.read_text(encoding="utf-8"))}
    return registry


def iter_claim_lines(body_lines: List[str], start: int):
    """產生 (行號 1-based, 文字, 是否在『虛構』小節)。略過 code fence、標題、表格分隔線。"""
    in_code = False
    fictional = False
    heading = ""
    for off, raw in enumerate(body_lines):
        ln = start + off + 1
        s = raw.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not s:
            continue
        if s.startswith("#"):
            fictional = ("虛構" in s) or ("通則" in s)
            heading = s
            continue
        if re.fullmatch(r"[|\-:\s]+", s):
            continue
        yield ln, raw, fictional, heading


def check_page(p: Path, registry: Dict[str, Dict], issues: Issues, stats: Counter,
               used_sources: Dict[str, Set[str]]) -> None:
    text = p.read_text(encoding="utf-8")
    fm, body_start = parse_frontmatter(text)
    ptype = fm.get("type", "")
    if not fm or not ptype or not fm.get("title"):
        issues.add("E-FM", p, 1, "缺 frontmatter（需要 type 與 title）")
        return
    lines = text.split("\n")[body_start:]
    evid_count = 0
    for ln, raw, fictional, heading in iter_claim_lines(lines, body_start):
        evs = EVID_RE.findall(raw)
        if evs and "容易誤會" in heading:
            issues.add("E-SECTION", p, ln, "證據行被放在「容易誤會」小節；證據應放在「各家怎麼說／證據」類小節")
        quote_nums: Set[float] = set()
        for sid, quote in evs:
            evid_count += 1
            stats["evidence_total"] += 1
            used_sources[str(p)].add(sid)
            src = registry.get(sid)
            if not src:
                issues.add("E-QUOTE", p, ln, f"來源 id『{sid}』沒有登錄在 wiki/sources/")
                continue
            if len(norm(quote)) < 20:
                issues.add("E-QSHORT", p, ln, f"引文太短：「{quote}」")
            if len(quote) > 400:
                issues.add("W-LONGQ", p, ln, f"引文過長（{len(quote)} 字元）")
            parts = [x.strip() for x in re.split(r"\.\.\.|…", quote) if x.strip()]
            pos = 0
            ok = True
            for part in parts:
                idx = src["text"].find(norm(part), pos)
                if idx < 0:
                    ok = False
                    issues.add("E-QUOTE", p, ln,
                               f"在 {sid} 原文找不到引文片段：「{part[:70]}{'…' if len(part) > 70 else ''}」")
                    break
                pos = idx + len(norm(part))
            if ok:
                stats["evidence_verified"] += 1
            quote_nums |= numbers_in_quote(quote)

        # calc
        allowed_calc: Set[float] = set()
        for expr in CALC_RE.findall(raw):
            try:
                lhs, rhs = expr.split("=")
                val = safe_eval(lhs)
                if abs(val - float(rhs)) > 1e-6:
                    issues.add("E-CALC", p, ln, f"算式不成立：{expr}（實際 {val:g}）")
                    continue
                for m in NUM_RE.finditer(lhs):
                    v = to_float(m.group(0))
                    is_unit = v is not None and v > 0 and abs(__import__("math").log10(v) - round(__import__("math").log10(v))) < 1e-9
                    if v is not None and v not in quote_nums and not is_unit:  # 10 的次方視為單位換算
                        issues.add("E-CALC", p, ln, f"算式運算元 {m.group(0)} 沒有出現在該行引文中")
                allowed_calc.add(abs(float(rhs)))
                stats["calc_verified"] += 1
            except Exception as exc:  # noqa: BLE001
                issues.add("E-CALC", p, ln, f"無法解析 calc：{expr}（{exc}）")

        if fictional:
            continue
        nums = numbers_in_claim(raw)
        if not nums:
            continue
        if not evs:
            issues.add("E-NOEVID", p, ln,
                       f"含數字（{', '.join(n for n, _ in nums)}）但沒有附 {{{{來源: \"引文\"}}}}：{raw.strip()[:60]}")
            continue
        stats["numbers_checked"] += len(nums)
        for tok, v in nums:
            if v in quote_nums or abs(v) in allowed_calc:
                continue
            issues.add("E-NUM", p, ln, f"數字 {tok} 沒有出現在該行的引文裡（可能是幻覺或誤植）")

    if ptype == "source" and evid_count < 3:
        issues.add("E-FM", p, 1, f"來源頁至少要有 3 條證據，現在只有 {evid_count}")


def check_links_and_index(pages: List[Path], issues: Issues) -> None:
    rels = {str(p.relative_to(WIKI))[:-3]: p for p in pages}
    inbound: Dict[str, Set[str]] = defaultdict(set)
    index_text = (WIKI / "index.md").read_text(encoding="utf-8") if (WIKI / "index.md").exists() else ""
    index_links = set(LINK_RE.findall(index_text))
    for p in pages:
        text = p.read_text(encoding="utf-8")
        me = str(p.relative_to(WIKI))[:-3]
        for ln, line in enumerate(text.split("\n"), 1):
            for target in LINK_RE.findall(re.sub(r"`[^`]*`", " ", line)):
                target = target.strip()
                if target not in rels:
                    issues.add("E-LINK", p, ln, f"[[{target}]] 指向不存在的頁面")
                elif target != me:
                    inbound[target].add(me)
    for rel, p in rels.items():
        if rel in ("index", "log", "SCHEMA") or rel.startswith("discussions/"):
            continue
        if rel not in index_links:
            issues.add("E-INDEX", p, 1, "沒有被列在 wiki/index.md")
        if not (inbound[rel] - {"index"}):
            issues.add("W-ORPHAN", p, 1, "沒有任何頁面（除了 index）連到它")


def check_log(registry: Dict[str, Dict], issues: Issues) -> None:
    log = WIKI / "log.md"
    txt = log.read_text(encoding="utf-8") if log.exists() else ""
    for sid, src in registry.items():
        if not re.search(rf"ingest\s*\|\s*{re.escape(sid)}\b", txt):
            issues.add("E-LOG", src["path"], 1, f"log.md 沒有『ingest | {sid}』紀錄")


def run(label: str = "", record: Optional[str] = None, quiet: bool = False) -> Dict:
    issues = Issues()
    stats: Counter = Counter()
    used: Dict[str, Set[str]] = defaultdict(set)
    registry = load_sources(issues)
    pages = sorted(p for p in WIKI.rglob("*.md"))
    content_pages = [p for p in pages if p.relative_to(WIKI).parts[0] in ("sources", "concepts", "entities")]
    for p in content_pages:
        check_page(p, registry, issues, stats, used)
    check_links_and_index(pages, issues)
    check_log(registry, issues)
    for p in content_pages:
        if p.relative_to(WIKI).parts[0] == "concepts" and len(used[str(p)]) == 1:
            issues.add("W-SINGLE", p, 1, f"概念頁只有 1 份來源支持（{next(iter(used[str(p)]))}）")

    kinds = Counter(p.relative_to(WIKI).parts[0] for p in content_pages)
    summary = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stage": "wiki-lint",
        "label": label,
        "sources": len(registry),
        "pages": dict(kinds),
        "evidence_total": stats["evidence_total"],
        "evidence_verified": stats["evidence_verified"],
        "numbers_checked": stats["numbers_checked"],
        "calc_verified": stats["calc_verified"],
        "errors": len(issues.errors),
        "warnings": len(issues.warnings),
        "error_codes": dict(Counter(i["code"] for i in issues.errors)),
        "warn_codes": dict(Counter(i["code"] for i in issues.warnings)),
        "passed": not issues.errors,
    }
    if not quiet:
        by_file: Dict[str, List[Dict]] = defaultdict(list)
        for i in issues.items:
            by_file[i["file"]].append(i)
        for f in sorted(by_file):
            print(f"\n{f}")
            for i in sorted(by_file[f], key=lambda x: x["line"]):
                print(f"  L{i['line']:<4} {i['code']:<9} {i['msg']}")
        print("\n" + "=" * 70)
        print(f"sources={summary['sources']}  pages={summary['pages']}")
        print(f"evidence verified: {summary['evidence_verified']}/{summary['evidence_total']}   "
              f"numbers checked: {summary['numbers_checked']}   calc verified: {summary['calc_verified']}")
        print(f"errors={summary['errors']} {summary['error_codes']}   warnings={summary['warnings']} {summary['warn_codes']}")
        print("RESULT:", "PASS ✅" if summary["passed"] else "FAIL ❌")
    if record:
        rp = ROOT / record
        rp.parent.mkdir(parents=True, exist_ok=True)
        with rp.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**summary, "issues": issues.items}, ensure_ascii=False) + "\n")
    return {"summary": summary, "issues": issues.items}


def main() -> int:
    ap = argparse.ArgumentParser(description="LLM Wiki 檢查器")
    ap.add_argument("--record", default="", help="把本次結果附加到 jsonl（例如 logs/runs.jsonl）")
    ap.add_argument("--label", default="", help="本次執行的標籤，例如 batch1-round1")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    res = run(args.label, args.record or None, args.quiet)
    return 0 if res["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
