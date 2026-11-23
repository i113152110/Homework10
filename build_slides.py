#!/usr/bin/env python3
"""
build_slides.py — 「用 Wiki 產生簡報」節點 + 「簡報檢查」節點

流程
  0. 閘門：先跑 wiki_lint；Wiki 沒通過就不產生簡報。
  1. 讀 slides/slides_spec.py（每頁引用哪些 Wiki 頁面、要回答什麼問題）。
  2. 簡報檢查（任何一項 error 都會讓 build 失敗，不產生 HTML）：
       S-WIKI   引用的 Wiki 頁面不存在
       S-NOWIKI 頁面有數字，卻沒有引用任何 Wiki 頁面
       S-NUM    頁面上的數字，不在所引用 Wiki 頁面「有證據的句子」裡
       S-FICT   標為虛構的區塊用了 Wiki『虛構』小節以外的數字
       S-QUOTE  引文區塊在原始文件中找不到
       S-COVER  有 concept 頁面沒有被任何一頁引用
       W-RETR   用該頁的 question 查 Wiki，排名前 5 的頁面都不包含該頁引用的頁面
       W-LEN    單頁文字太多，可能放不下
  3. 通過後才輸出：
       slides/index.html            單一檔案、離線可開
       slides/index.artifact.html   發佈用片段（沒有 doctype/head/body）
"""
from __future__ import annotations

import html
import importlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "slides"))

import wiki_lint as WL  # noqa: E402
import wiki_query as WQ  # noqa: E402

WIKI = ROOT / "wiki"
TITLE = "Volume Price Mix 教學簡報"


# ----------------------------------------------------------------------------- Wiki 解析
def read_page(rel: str):
    p = WIKI / f"{rel}.md"
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    fm, start = WL.parse_frontmatter(text)
    return text, fm, start


def page_facts(rel: str) -> Dict:
    """某頁『有證據的句子』的數字、虛構小節的數字、引用到的來源 id。"""
    r = read_page(rel)
    res = {"nums": set(), "fict": set(), "src": set(), "exists": bool(r)}
    if not r:
        return res
    text, fm, start = r
    for ln, raw, fictional, heading in WL.iter_claim_lines(text.split("\n")[start:], start):
        evs = WL.EVID_RE.findall(raw)
        if fictional and "虛構" in heading:
            res["fict"] |= {abs(v) for _, v in WL.numbers_in_claim(raw)}
            continue
        if fictional or not evs:
            continue
        res["nums"] |= {abs(v) for _, v in WL.numbers_in_claim(raw)}
        for sid, q in evs:
            res["src"].add(sid)
            res["nums"] |= WL.numbers_in_quote(q)
        for expr in WL.CALC_RE.findall(raw):
            try:
                res["nums"].add(abs(float(expr.split("=")[1])))
            except Exception:  # noqa: BLE001
                pass
    return res


# ----------------------------------------------------------------------------- 文字處理
def esc(s: str) -> str:
    return html.escape(s, quote=False)


def md(s: str) -> str:
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s.replace("\n", "<br>")


def fmt(v: float, signed: bool = True) -> str:
    sign = "+" if v > 0 and signed else ("−" if v < 0 else "")
    a = abs(v)
    txt = f"{a:g}"
    return f"{sign}{txt}"


def block_texts(b: Dict) -> List[str]:
    """這個區塊『看得到的文字』，用來做數字檢查。quote 另外逐字驗證，不在此列。"""
    t = b["t"]
    out: List[str] = []
    if t in ("text", "callout"):
        out.append(b["md"])
    elif t == "bullets" or t == "olist" or t == "flow":
        out += b["items"]
    elif t == "cards":
        for c in b["items"]:
            out += [c["h"], c["p"]]
    elif t == "stats":
        for c in b["items"]:
            out += [c["v"], c["l"]]
    elif t in ("equation", "eqrow"):
        out.append(b.get("label", ""))
        for p in b["parts"]:
            out += [p.get("t", ""), p.get("v", "")]
    elif t == "table":
        out += b["head"]
        for r in b["rows"]:
            out += r
    elif t == "waterfall":
        out.append(b["title"])
        for s in b["steps"]:
            out += [s["label"], fmt(s["v"])]
    elif t == "stackbar":
        out += [b["title"], b["total"]["label"], fmt(-b["total"]["v"])]
        for p in b["parts"]:
            out.append(p["label"])
            if p.get("v") is not None:
                out.append(fmt(p["v"]))
    elif t == "quiz":
        for q in b["items"]:
            out += [q["q"], q["why"]] + q["opts"]
    elif t == "split":
        for side in ("left", "right"):
            for sb in b[side]:
                out += block_texts(sb)
    return out


def all_blocks(blocks: List[Dict]):
    for b in blocks:
        if b["t"] == "split":
            yield from all_blocks(b["left"])
            yield from all_blocks(b["right"])
        else:
            yield b


# ----------------------------------------------------------------------------- 簡報檢查
def lint_slides(slides: List[Dict], registry: Dict[str, Dict]) -> Dict:
    issues: List[Dict] = []
    stats = Counter()

    def add(code, sid, msg):
        issues.append({"code": code, "severity": "error" if code.startswith("S-") else "warn", "slide": sid, "msg": msg})

    cited_concepts: Set[str] = set()
    for s in slides:
        sid = s["id"]
        wiki = s.get("wiki", [])
        facts = [page_facts(w) for w in wiki]
        for w, f in zip(wiki, facts):
            if not f["exists"]:
                add("S-WIKI", sid, f"找不到 Wiki 頁面 {w}")
            if w.startswith("concepts/"):
                cited_concepts.add(w)
        if s["kind"] != "content":
            continue
        allowed: Set[float] = set().union(*[f["nums"] for f in facts]) if facts else set()
        fict_allowed: Set[float] = set().union(*[f["fict"] for f in facts]) if facts else set()
        title_nums = [(tok, abs(v)) for tok, v in WL.numbers_in_claim(s["title"])]
        slide_chars = len(s["title"])
        for tok, v in title_nums:
            stats["numbers_checked"] += 1
            if v not in allowed:
                add("S-NUM", sid, f"標題的數字 {tok} 不在所引用 Wiki 頁面的證據句裡")
            else:
                stats["numbers_traced"] += 1
        for b in all_blocks(s.get("blocks", [])):
            if b["t"] == "quote":
                src = registry.get(b["src"])
                stats["quotes"] += 1
                if not src:
                    add("S-QUOTE", sid, f"引文的來源 id『{b['src']}』未登錄")
                elif WL.norm(b["text"]) not in src["text"]:
                    add("S-QUOTE", sid, f"引文在 {b['src']} 原文找不到：{b['text'][:60]}…")
                else:
                    stats["quotes_verified"] += 1
                if b["src"] not in set().union(*[f["src"] for f in facts]) and facts:
                    add("S-QUOTE", sid, f"引文來源 {b['src']} 不在這頁引用的 Wiki 頁面證據裡（簡報不可引用 Wiki 沒有的來源）")
                continue
            if b["t"] in ("method", "auto_mapping", "auto_sources"):
                continue
            texts = block_texts(b)
            slide_chars += sum(len(x) for x in texts)
            is_fict = b["t"] == "fiction"
            for tx in texts:
                for tok, v in WL.numbers_in_claim(tx):
                    stats["numbers_checked"] += 1
                    pool = fict_allowed if is_fict else allowed
                    if abs(v) not in pool:
                        add("S-FICT" if is_fict else "S-NUM", sid,
                            f"數字 {tok} 不在{'Wiki 虛構小節' if is_fict else '所引用 Wiki 頁面的證據句'}裡：「{tx[:40]}」")
                    else:
                        stats["numbers_traced"] += 1
        has_digits = stats["numbers_checked"] > 0
        if slide_chars > 560:
            add("W-LEN", sid, f"文字約 {slide_chars} 字，可能放不下（建議 < 560）")
        q = s.get("question")
        if q and wiki:
            top = WQ.rank_pages(q, 5)
            stats["retr_total"] += 1
            if set(top) & set(wiki):
                stats["retr_ok"] += 1
            else:
                add("W-RETR", sid, f"問『{q}』時，Wiki 排名前 5（{', '.join(top)}）不含這頁引用的頁面")
    all_concepts = {f"concepts/{p.stem}" for p in (WIKI / "concepts").glob("*.md")}
    for c in sorted(all_concepts - cited_concepts):
        add("S-COVER", "-", f"概念頁 {c} 沒有被任何一頁簡報引用")
    # S-NOWIKI：有數字卻沒引用 Wiki
    for s in slides:
        if s["kind"] == "content" and not s.get("wiki"):
            nums = []
            for b in all_blocks(s.get("blocks", [])):
                for tx in block_texts(b):
                    nums += WL.numbers_in_claim(tx)
            if nums:
                add("S-NOWIKI", s["id"], "有數字但沒有引用任何 Wiki 頁面")
    return {"issues": issues, "stats": dict(stats)}


# ----------------------------------------------------------------------------- 區塊渲染
COLOR = {"vol": "vol", "price": "price", "mix": "mix", "total": "total", "neutral": "neutral", None: "neutral"}


def r_block(b: Dict, ctx: Dict) -> str:
    t = b["t"]
    if t == "text":
        return f'<p class="txt">{md(b["md"])}</p>'
    if t == "callout":
        return f'<div class="callout">{md(b["md"])}</div>'
    if t == "fiction":
        return f'<div class="fiction"><span class="badge">虛構範例，非來源</span><p>{md(b["md"])}</p></div>'
    if t == "bullets":
        return "<ul class=\"bl\">" + "".join(f"<li>{md(i)}</li>" for i in b["items"]) + "</ul>"
    if t == "olist":
        return "<ol class=\"ol\">" + "".join(f'<li><span class="ot">{md(i)}</span></li>' for i in b["items"]) + "</ol>"
    if t == "flow":
        parts = []
        for k, it in enumerate(b["items"]):
            parts.append(f'<div class="fnode">{md(it)}</div>')
            if k < len(b["items"]) - 1:
                parts.append('<div class="farrow" aria-hidden="true">↓</div>')
        return '<div class="flow">' + "".join(parts) + "</div>"
    if t == "cards":
        n = len(b["items"])
        cs = "".join(f'<div class="card c-{COLOR[c.get("c")]}"><h3>{esc(c["h"])}</h3><p>{md(c["p"])}</p></div>' for c in b["items"])
        return f'<div class="cards n{n}">{cs}</div>'
    if t == "stats":
        cs = "".join(f'<div class="stat c-{COLOR[c.get("c")]}"><div class="v">{esc(c["v"])}</div><div class="l">{esc(c["l"])}</div></div>' for c in b["items"])
        return f'<div class="stats n{len(b["items"])}">{cs}</div>'
    if t == "quote":
        return (f'<figure class="quote"><blockquote lang="en">{esc(b["text"])}</blockquote>'
                f'<figcaption>{esc(b["who"])} · <code>{esc(b["src"])}</code> <span class="ok">已逐字比對原文</span></figcaption></figure>')
    if t in ("equation", "eqrow"):
        items = []
        for p in b["parts"]:
            if "op" in p:
                items.append(f'<span class="op">{esc(p["op"])}</span>')
            else:
                v = f'<span class="ev">{esc(p["v"])}</span>' if p.get("v") else ""
                items.append(f'<span class="chip c-{COLOR[p.get("c")]}"><span class="et">{esc(p["t"])}</span>{v}</span>')
        lab = f'<div class="eqlabel">{esc(b["label"])}</div>' if b.get("label") else ""
        return f'<div class="eqwrap">{lab}<div class="eq">{"".join(items)}</div></div>'
    if t == "table":
        head = "".join(f"<th>{esc(h)}</th>" for h in b["head"])
        rows = "".join("<tr>" + "".join(f"<td>{md(c)}</td>" for c in r) + "</tr>" for r in b["rows"])
        return f'<div class="tblwrap"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
    if t == "split":
        l = "".join(r_block(x, ctx) for x in b["left"])
        r = "".join(r_block(x, ctx) for x in b["right"])
        return f'<div class="split"><div class="col">{l}</div><div class="col">{r}</div></div>'
    if t == "waterfall":
        return r_waterfall(b)
    if t == "stackbar":
        tot = b["total"]["v"]
        segs = ""
        for p in b["parts"]:
            v = p.get("v")
            w = (v if v is not None else tot - sum(x.get("v") or 0 for x in b["parts"])) / tot * 100
            cls = "seg hatch" if p.get("hatch") else "seg rest"
            lab = esc(p["label"]) + (f" 約 {v:g} 點" if v is not None else "")
            segs += f'<div class="{cls}" style="width:{w:.1f}%"><span>{lab}</span></div>'
        return (f'<div class="stackbar"><div class="sbt">{esc(b["title"])}</div>'
                f'<div class="sbl">{esc(b["total"]["label"])} −{tot:g} 點</div><div class="sbbar">{segs}</div></div>')
    if t == "quiz":
        out = []
        for qi, q in enumerate(b["items"]):
            opts = "".join(f'<button type="button" class="opt" data-q="{qi}" data-i="{oi}" data-ans="{1 if oi == q["ans"] else 0}">{esc(o)}</button>'
                           for oi, o in enumerate(q["opts"]))
            out.append(f'<div class="quizq" id="qq{qi}"><div class="qt">{esc(q["q"])}</div><div class="opts">{opts}</div>'
                       f'<div class="why" hidden>{esc(q["why"])}</div></div>')
        return '<div class="quiz">' + "".join(out) + "</div>"
    if t == "method":
        return METHOD_SVG
    if t == "auto_mapping":
        return ctx["mapping_html"]
    if t == "auto_sources":
        return ctx["sources_html"]
    raise ValueError(f"unknown block {t}")


def r_waterfall(b: Dict) -> str:
    steps = b["steps"]
    W, H, top, bot, left = 560, 330, 56, 70, 24
    run = 0.0
    bars = []
    for s in steps:
        if s.get("total"):
            a, z = 0.0, s["v"]
            run = s["v"]
        else:
            a, z = run, run + s["v"]
            run = z
        bars.append((a, z, s))
    lo = min(0.0, *[min(a, z) for a, z, _ in bars])
    hi = max(0.0, *[max(a, z) for a, z, _ in bars])
    pad = (hi - lo) * 0.12 or 1
    lo -= pad if lo < 0 else 0
    hi += pad
    plot_h = H - top - bot

    def y(v: float) -> float:
        return top + (hi - v) / (hi - lo) * plot_h

    n = len(bars)
    gap = (W - 2 * left) / n
    bw = gap * 0.58
    svg = [f'<svg class="wf" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(b["title"])}">']
    svg.append(f'<line x1="{left}" x2="{W - left}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="axis"/>')
    prev_end = None
    for k, (a, z, s) in enumerate(bars):
        x = left + gap * k + (gap - bw) / 2
        y1, y2 = y(max(a, z)), y(min(a, z))
        col = {"vol": "var(--vol)", "price": "var(--price)", "mix": "var(--mix)", "total": "var(--accent)"}.get(s.get("c"), "var(--muted)")
        svg.append(f'<rect x="{x:.1f}" y="{y1:.1f}" width="{bw:.1f}" height="{max(y2 - y1, 2):.1f}" rx="3" style="fill:{col}"/>')
        up = s["v"] >= 0 or s.get("total")
        ly = y1 - 10 if (s["v"] >= 0) else y2 + 22
        svg.append(f'<text x="{x + bw / 2:.1f}" y="{ly:.1f}" class="wv" text-anchor="middle">{fmt(s["v"])}</text>')
        svg.append(f'<text x="{x + bw / 2:.1f}" y="{H - bot + 30:.1f}" class="wl" text-anchor="middle">{esc(s["label"])}</text>')
        if prev_end is not None:
            svg.append(f'<line x1="{x - (gap - bw):.1f}" x2="{x:.1f}" y1="{y(prev_end):.1f}" y2="{y(prev_end):.1f}" class="conn"/>')
        prev_end = z
    svg.append("</svg>")
    return f'<div class="wfwrap"><div class="wft">{esc(b["title"])}</div>{"".join(svg)}</div>'


METHOD_SVG = """
<div class="method">
<svg viewBox="0 0 1120 430" role="img" aria-label="從取得資料到發佈簡報的流程圖，含兩個檢查迴圈與一條 Wiki 缺口回流線">
<defs><marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" style="fill:var(--ink)"/></marker>
<marker id="ar2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" style="fill:var(--neg)"/></marker></defs>
<g class="nd w"><rect x="0" y="80" width="250" height="84" rx="10"/><text x="125" y="112" class="nt">1 取得資料</text><text x="125" y="142" class="ns">data_update.py（HW3 重用）</text></g>
<g class="nd a"><rect x="290" y="80" width="250" height="84" rx="10"/><text x="415" y="112" class="nt">2 先討論</text><text x="415" y="142" class="ns">討論稿 D01、D02</text></g>
<g class="nd a"><rect x="580" y="80" width="250" height="84" rx="10"/><text x="705" y="112" class="nt">3 後生成</text><text x="705" y="142" class="ns">Wiki 頁面＋英文原文引文</text></g>
<g class="nd c"><rect x="870" y="80" width="250" height="84" rx="10"/><text x="995" y="112" class="nt">4 檢查 Wiki</text><text x="995" y="142" class="ns">wiki_lint.py</text></g>
<g class="nd w"><rect x="870" y="270" width="250" height="84" rx="10"/><text x="995" y="302" class="nt">5 查詢 Wiki</text><text x="995" y="332" class="ns">wiki_query.py</text></g>
<g class="nd a"><rect x="580" y="270" width="250" height="84" rx="10"/><text x="705" y="302" class="nt">6 整理成簡報</text><text x="705" y="332" class="ns">slides_spec → HTML</text></g>
<g class="nd c"><rect x="290" y="270" width="250" height="84" rx="10"/><text x="415" y="302" class="nt">7 檢查簡報</text><text x="415" y="332" class="ns">數字溯源・引文・渲染</text></g>
<g class="nd w"><rect x="0" y="270" width="250" height="84" rx="10"/><text x="125" y="302" class="nt">8 發佈</text><text x="125" y="332" class="ns">HTML 簡報＋Wiki</text></g>
<g class="ln"><path d="M250 122H288" marker-end="url(#ar)"/><path d="M540 122H578" marker-end="url(#ar)"/><path d="M830 122H868" marker-end="url(#ar)"/>
<path d="M995 164V268" marker-end="url(#ar)"/><path d="M868 312H832" marker-end="url(#ar)"/><path d="M578 312H542" marker-end="url(#ar)"/><path d="M288 312H252" marker-end="url(#ar)"/></g>
<g class="ln bad"><path d="M995 78C995 24 705 24 705 78" marker-end="url(#ar2)"/><text x="850" y="22" class="lb" text-anchor="middle">不通過：修正後重跑</text>
<path d="M415 356C415 410 705 410 705 358" marker-end="url(#ar2)" transform="translate(0 0)"/><text x="560" y="424" class="lb" text-anchor="middle">不通過：修正後重跑</text>
<path d="M930 268C930 210 415 220 415 166" stroke-dasharray="6 5" marker-end="url(#ar2)"/><text x="700" y="224" class="lb" text-anchor="middle">Wiki 缺口：回去補 ingest</text></g>
<g class="lg"><rect x="0" y="388" width="16" height="16" rx="3" class="lw"/><text x="24" y="401" class="ls">程式執行</text><rect x="110" y="388" width="16" height="16" rx="3" class="la"/><text x="134" y="401" class="ls">AI 撰寫</text><rect x="214" y="388" width="16" height="16" rx="3" class="lc"/><text x="238" y="401" class="ls">程式檢查</text></g>
</svg></div>
"""


# ----------------------------------------------------------------------------- 附錄表格
def build_mapping(slides: List[Dict], registry: Dict[str, Dict]) -> str:
    rows = []
    for n, s in enumerate(slides, 1):
        if s["kind"] != "content":
            continue
        pages = s.get("wiki", [])
        srcs: Set[str] = set()
        for w in pages:
            srcs |= page_facts(w)["src"]
        cos = sorted({registry[x]["fm"]["company"] for x in srcs if x in registry})
        chips = " ".join(f"<code>{esc(p.split('/')[1])}</code>" for p in pages if p.startswith("concepts/")) or '<span class="dim">概念整理</span>'
        co = f' <span class="co">· {"／".join(cos)}</span>' if cos else ""
        short = re.sub(r"%%.*?%%", "", s["title"])
        rows.append(f'<div class="mrow"><span class="mn">{n}</span><span class="mt">{esc(short)}</span><span class="mp">{chips}{co}</span></div>')
    k = (len(rows) + 2) // 3
    cols = "".join(f'<div class="mcol">{"".join(rows[i:i + k])}</div>' for i in range(0, len(rows), k))
    return f'<div class="mapping">{cols}</div><p class="note">灰色公司代號 = 該頁引用的 Wiki 頁面，其證據來自哪幾家公司的來源；完整來源清單見下一頁。</p>'


def build_sources(registry: Dict[str, Dict]) -> str:
    cnt: Counter = Counter()
    for p in WIKI.rglob("*.md"):
        for sid, _ in WL.EVID_RE.findall(p.read_text(encoding="utf-8")):
            cnt[sid] += 1
    rows = ""
    for sid, r in sorted(registry.items(), key=lambda kv: (kv[1]["fm"]["batch"], kv[0])):
        fm = r["fm"]
        kind = "法說會" if fm["kind"] == "earnings_call" else "年報 10-K"
        rows += (f'<tr><td><code>{esc(sid)}</code></td><td>{esc(fm["company"])}</td><td>{esc(fm["period"])}</td>'
                 f'<td>{kind}</td><td>批次 {esc(fm["batch"])}</td><td class="num">{cnt[sid]}</td><td class="fn">{esc(fm["raw"])}</td></tr>')
    return ('<div class="tblwrap"><table class="src"><thead><tr><th>來源 id</th><th>公司</th><th>期間</th><th>類型</th><th>ingest</th>'
            f'<th>引文數</th><th>HW3 原始檔</th></tr></thead><tbody>{rows}</tbody></table></div>'
            '<p class="note">HW3 的 20 份文件中，這個 Wiki 只 ingest 上面這幾份；沒有 ingest 的內容，簡報不講。</p>')


# ----------------------------------------------------------------------------- 頁面與樣式
CSS = r"""
:root{
  --bg:#EDF1EF; --paper:#FFFFFF; --ink:#14201D; --muted:#566763; --line:#D3DCD9; --soft:#E4EEEB;
  --accent:#0A6B5C; --accent-ink:#FFFFFF;
  --vol:#2563C9; --vol-bg:#E3EBFA; --price:#B06E08; --price-bg:#F7E9CF; --mix:#9B3A8A; --mix-bg:#F2DFEE;
  --neu-bg:#EEF2F1; --tot-bg:#D8EEE8; --neg:#B3402F; --fic:#5B3FA6; --fic-bg:#EEE8FA;
  --shadow:0 1px 2px rgba(20,32,29,.08),0 10px 30px rgba(20,32,29,.10);
  --display:"Space Grotesk","Noto Sans TC","PingFang TC","Microsoft JhengHei",system-ui,sans-serif;
  --body:"Noto Sans TC","PingFang TC","Microsoft JhengHei","Noto Sans CJK TC",system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0B1210; --paper:#141D1A; --ink:#E7EFEC; --muted:#9FB2AC; --line:#26342F; --soft:#1B2A25;
  --accent:#4FD1B8; --accent-ink:#06201A;
  --vol:#7BA9FF; --vol-bg:#16253F; --price:#E8B04A; --price-bg:#3A2D12; --mix:#E293D3; --mix-bg:#3A1E35;
  --neu-bg:#1A2623; --tot-bg:#143A33; --neg:#FF9684; --fic:#B9A4F5; --fic-bg:#2A2144;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.45); color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0B1210; --paper:#141D1A; --ink:#E7EFEC; --muted:#9FB2AC; --line:#26342F; --soft:#1B2A25;
  --accent:#4FD1B8; --accent-ink:#06201A;
  --vol:#7BA9FF; --vol-bg:#16253F; --price:#E8B04A; --price-bg:#3A2D12; --mix:#E293D3; --mix-bg:#3A1E35;
  --neu-bg:#1A2623; --tot-bg:#143A33; --neg:#FF9684; --fic:#B9A4F5; --fic-bg:#2A2144;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.45); color-scheme:dark}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);-webkit-font-smoothing:antialiased;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));overflow-x:hidden}
code{font-family:var(--mono);font-size:.82em;background:var(--soft);padding:.08em .4em;border-radius:4px}
.viewer{height:100%;display:flex;flex-direction:column;gap:10px;padding-block:12px}
.stagewrap{flex:1;min-height:0;display:flex;align-items:center;justify-content:center}
.sizer{position:relative}
.stage{width:1280px;height:720px;position:absolute;left:0;top:0;transform-origin:0 0}
.slide{position:absolute;inset:0;background:var(--paper);border-radius:14px;box-shadow:var(--shadow);display:none;flex-direction:column;
  padding:44px 64px 26px;overflow:hidden;border:1px solid var(--line)}
.slide.active{display:flex}
.slide header{margin-bottom:22px}
.kicker{font:600 15px/1 var(--display);letter-spacing:.08em;color:var(--accent);text-transform:uppercase}
.slide h2{margin:10px 0 0;font:700 38px/1.22 var(--body);letter-spacing:-.005em;text-wrap:balance}
.sbody{flex:1;min-height:0;font-size:23px;line-height:1.55}
.sfit{display:flex;flex-direction:column;gap:18px}
.slide footer{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:12px;padding-top:10px;border-top:1px solid var(--line);
  font-size:13px;color:var(--muted)}
.slide footer .src{display:flex;flex-wrap:wrap;gap:6px;align-items:center;min-width:0}
.slide footer .pg{font:600 14px var(--display);white-space:nowrap}
.txt{margin:0}
.callout{background:var(--soft);border-left:5px solid var(--accent);padding:14px 20px;border-radius:0 10px 10px 0;font-size:21px}
.fiction{background:var(--fic-bg);border:2px dashed var(--fic);border-radius:12px;padding:14px 20px;position:relative}
.fiction p{margin:0;font-size:22px}
.badge{display:inline-block;font:700 13px/1 var(--body);color:var(--fic);border:1.5px solid var(--fic);border-radius:999px;padding:4px 10px;margin-bottom:8px;letter-spacing:.04em}
.bl,.ol{margin:0;padding-left:1.3em;display:flex;flex-direction:column;gap:8px}
.ol{counter-reset:s;list-style:none;padding-left:0;gap:16px}
.ol li{counter-increment:s;display:grid;grid-template-columns:44px 1fr;align-items:start;gap:14px;font-size:25px;line-height:1.45}
.ol .ot{min-width:0}
.ol li::before{content:counter(s);font:700 22px/44px var(--display);background:var(--accent);color:var(--accent-ink);width:44px;height:44px;border-radius:50%;text-align:center}
.flow{display:flex;flex-direction:column;gap:6px;align-items:stretch}
.fnode{background:var(--neu-bg);border:1px solid var(--line);border-radius:10px;padding:10px 16px;font-size:20px}
.farrow{text-align:center;color:var(--muted);line-height:1;font-size:20px}
.cards{display:grid;gap:18px}
.cards.n2{grid-template-columns:repeat(2,1fr)}.cards.n3{grid-template-columns:repeat(3,1fr)}.cards.n4{grid-template-columns:repeat(2,1fr)}
.card{border-radius:14px;padding:18px 22px;border:1px solid var(--line);background:var(--neu-bg);min-width:0}
.card h3{margin:0 0 8px;font:700 24px/1.2 var(--body)}
.card p{margin:0;font-size:21px;line-height:1.5}
.card.c-vol{background:var(--vol-bg);border-color:transparent}.card.c-vol h3{color:var(--vol)}
.card.c-price{background:var(--price-bg);border-color:transparent}.card.c-price h3{color:var(--price)}
.card.c-mix{background:var(--mix-bg);border-color:transparent}.card.c-mix h3{color:var(--mix)}
.stats{display:grid;gap:18px}.stats.n2{grid-template-columns:repeat(2,1fr)}.stats.n3{grid-template-columns:repeat(3,1fr)}
.stat{border-radius:14px;padding:16px 22px;background:var(--neu-bg)}
.stat .v{font:700 54px/1.05 var(--display);letter-spacing:-.02em}
.stat .l{font-size:19px;color:var(--muted);margin-top:4px}
.stat.c-vol{background:var(--vol-bg)}.stat.c-vol .v{color:var(--vol)}
.stat.c-price{background:var(--price-bg)}.stat.c-price .v{color:var(--price)}
.stat.c-mix{background:var(--mix-bg)}.stat.c-mix .v{color:var(--mix)}
.stat.c-total{background:var(--tot-bg)}.stat.c-total .v{color:var(--accent)}
.quote{margin:0;border:1px solid var(--line);border-radius:12px;padding:14px 20px;background:var(--paper)}
.quote blockquote{margin:0;font:italic 400 18px/1.5 Georgia,"Times New Roman",serif;color:var(--ink)}
.quote figcaption{margin-top:8px;font-size:13px;color:var(--muted);display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.quote .ok{color:var(--accent);font-weight:600}
.eqwrap{display:flex;flex-direction:column;gap:6px}
.eqlabel{font:600 15px var(--body);color:var(--muted);letter-spacing:.02em}
.eq{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.op{font:600 30px var(--display);color:var(--muted)}
.chip{display:inline-flex;flex-direction:column;align-items:center;min-width:92px;padding:8px 16px;border-radius:12px;background:var(--neu-bg);border:1px solid var(--line)}
.chip .et{font-size:18px;font-weight:600}
.chip .ev{font:700 28px/1.15 var(--display)}
.chip.c-vol{background:var(--vol-bg);border-color:transparent;color:var(--vol)}
.chip.c-price{background:var(--price-bg);border-color:transparent;color:var(--price)}
.chip.c-mix{background:var(--mix-bg);border-color:transparent;color:var(--mix)}
.chip.c-total{background:var(--tot-bg);border-color:transparent;color:var(--accent)}
.chip.c-neutral{color:var(--ink)}
.split{display:grid;grid-template-columns:1fr 1fr;gap:34px;align-items:start}
.col{display:flex;flex-direction:column;gap:16px;min-width:0}
.tblwrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:21px}
th{text-align:left;font:600 16px var(--body);color:var(--muted);letter-spacing:.04em;padding:8px 14px;border-bottom:2px solid var(--line)}
td{padding:11px 14px;border-bottom:1px solid var(--line);vertical-align:top}
td.num{font-family:var(--display);font-weight:700;text-align:right}
table.src{font-size:16px}table.src td{padding:7px 12px}td.fn{font-family:var(--mono);font-size:12px;color:var(--muted)}
.wfwrap{display:flex;flex-direction:column;gap:2px}
.wft{font:600 16px var(--body);color:var(--muted)}
.wf{width:100%;height:auto;max-height:330px}
.wf .axis{stroke:var(--muted);stroke-width:1.2}.wf .conn{stroke:var(--muted);stroke-width:1;stroke-dasharray:4 4}
.wf .wv{font:700 22px var(--display);fill:var(--ink)}.wf .wl{font:600 16px var(--body);fill:var(--muted)}
.stackbar{display:flex;flex-direction:column;gap:6px}
.sbt{font:600 16px var(--body);color:var(--muted)}.sbl{font:700 26px var(--display)}
.sbbar{display:flex;height:54px;border-radius:10px;overflow:hidden;border:1px solid var(--line)}
.seg{display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:600;padding:0 6px;text-align:center}
.seg.hatch{background:repeating-linear-gradient(45deg,var(--vol-bg),var(--vol-bg) 8px,var(--paper) 8px,var(--paper) 14px);color:var(--vol)}
.seg.rest{background:var(--neu-bg);color:var(--muted)}
.quiz{display:flex;flex-direction:column;gap:14px}
.quizq{border:1px solid var(--line);border-radius:12px;padding:12px 18px}
.qt{font-weight:700;font-size:21px;margin-bottom:8px}
.opts{display:flex;flex-wrap:wrap;gap:10px}
.opt{font:500 18px var(--body);padding:8px 16px;border-radius:999px;border:1.5px solid var(--line);background:var(--paper);color:var(--ink);cursor:pointer}
.opt:hover{border-color:var(--accent)}
.opt.right{background:var(--tot-bg);border-color:var(--accent);color:var(--accent);font-weight:700}
.opt.wrong{border-color:var(--neg);color:var(--neg)}
.why{margin-top:8px;font-size:17px;color:var(--muted)}
.method svg{width:100%;height:auto;max-height:440px}
.method .nd rect{stroke-width:2}
.method .nd.w rect{fill:var(--neu-bg);stroke:var(--line)}.method .nd.a rect{fill:var(--vol-bg);stroke:var(--vol)}.method .nd.c rect{fill:var(--tot-bg);stroke:var(--accent)}
.method .nt{font:700 22px var(--body);fill:var(--ink);text-anchor:middle}.method .ns{font:500 16px var(--body);fill:var(--muted);text-anchor:middle}
.method .ln path{fill:none;stroke:var(--ink);stroke-width:2}.method .ln.bad path{stroke:var(--neg)}
.method .lb{font:600 15px var(--body);fill:var(--neg);paint-order:stroke;stroke:var(--paper);stroke-width:7px;stroke-linejoin:round}.method .ls{font:500 14px var(--body);fill:var(--muted)}
.method .lw{fill:var(--neu-bg);stroke:var(--line)}.method .la{fill:var(--vol-bg);stroke:var(--vol)}.method .lc{fill:var(--tot-bg);stroke:var(--accent)}
.mapping{display:grid;grid-template-columns:repeat(3,1fr);gap:6px 26px}
.mcol{display:flex;flex-direction:column;gap:6px}
.mrow{display:grid;grid-template-columns:26px 1fr;grid-template-areas:"n t" "n p";gap:0 8px;padding:5px 0;border-bottom:1px solid var(--line);font-size:13px;line-height:1.35}
.mn{grid-area:n;font:700 14px var(--display);color:var(--accent)}.mt{grid-area:t;font-weight:700;font-size:14px}
.mp{grid-area:p;font-size:12px}.co{color:var(--muted)}.dim{color:var(--muted)}
.note{margin:6px 0 0;font-size:15px;color:var(--muted)}
.title{justify-content:center;gap:22px;background:linear-gradient(135deg,var(--tot-bg),var(--paper) 62%)}
.title .big{font:700 84px/1.08 var(--body);letter-spacing:-.02em;margin:0}
.title .sub{font:700 40px var(--display);display:flex;gap:16px;align-items:center;margin:0}
.title .sub span:nth-child(1){color:var(--vol)}.title .sub span:nth-child(3){color:var(--price)}.title .sub span:nth-child(5){color:var(--mix)}
.title .sub i{color:var(--muted);font-style:normal}
.title .lead{font-size:28px;margin:0;max-width:820px;line-height:1.5}
.title .meta{font-size:16px;color:var(--muted);margin:0}
.controls{display:flex;align-items:center;gap:12px;justify-content:center;color:var(--muted);font-size:14px}
.controls button{font:600 15px var(--body);padding:8px 18px;border-radius:999px;border:1.5px solid var(--line);background:var(--paper);color:var(--ink);cursor:pointer}
.controls button:hover{border-color:var(--accent)}
.controls button:focus-visible,.opt:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.bar{flex:1;max-width:360px;height:6px;border-radius:99px;background:var(--line);overflow:hidden}
.bar i{display:block;height:100%;background:var(--accent);width:0;transition:width .25s}
.hint{font-size:13px}
/* 閱讀模式：窄螢幕改成由上往下捲動 */
.viewer.reading{height:auto;padding-block:16px}
.reading .stagewrap{display:block}
.reading .sizer{width:auto!important;height:auto!important}
.reading .stage{position:static;width:auto;height:auto;transform:none!important;display:flex;flex-direction:column;gap:16px}
.reading .slide{position:static;display:flex;padding:22px 18px 14px;border-radius:12px;overflow:visible}
.reading .slide h2{font-size:24px}.reading .sbody{font-size:16px}.reading .callout{font-size:15px}
.reading .ol li{font-size:17px;grid-template-columns:34px 1fr}.reading .ol li::before{width:34px;height:34px;line-height:34px;font-size:17px}
.reading .cards.n2,.reading .cards.n3,.reading .cards.n4,.reading .stats.n2,.reading .stats.n3,.reading .split,.reading .mapping{grid-template-columns:1fr}
.reading .card p,.reading .fiction p,.reading table{font-size:15px}.reading .card h3{font-size:18px}
.reading .stat .v{font-size:34px}.reading .stat .l{font-size:14px}
.reading .quote blockquote{font-size:14px}.reading .chip{min-width:70px;padding:6px 10px}.reading .chip .ev{font-size:20px}.reading .chip .et{font-size:14px}
.reading .title .big{font-size:42px}.reading .title .sub{font-size:24px;flex-wrap:wrap}.reading .title .lead{font-size:18px}
.reading .controls{display:none}.reading .opt{font-size:15px}.reading .qt{font-size:16px}
.reading .slide footer{font-size:11px;flex-wrap:wrap}
@media (prefers-reduced-motion:reduce){.bar i{transition:none}}
@media print{.controls{display:none}.slide{display:flex!important;position:static;page-break-after:always;box-shadow:none}.stage{position:static;transform:none!important;width:auto;height:auto}.sizer{width:auto!important;height:auto!important}}
"""

JS = r"""
(function(){
  var slides=[].slice.call(document.querySelectorAll('.slide')),n=slides.length,i=0;
  var viewer=document.querySelector('.viewer'),wrap=document.querySelector('.stagewrap'),sizer=document.querySelector('.sizer'),stage=document.querySelector('.stage');
  var bar=document.querySelector('.bar i'),cnt=document.querySelector('.cnt');
  function reading(){return (document.documentElement.clientWidth||window.innerWidth)<820;}
  function resetFit(f){f.style.transform='';f.style.width='';f.style.marginTop='';}
  function fitSlide(s){
    var body=s.querySelector('.sbody'),f=s.querySelector('.sfit');
    if(!f)return;resetFit(f);
    if(reading()||s.dataset.fit==='0')return;
    var avail=body.clientHeight,nat=f.offsetHeight;
    if(!avail||!nat)return;
    var z=Math.min(1.35,avail*0.96/nat);
    if(z<1.04)return;
    for(var k=0;k<12;k++){
      f.style.width=(100/z)+'%';
      if(f.offsetHeight*z<=avail*0.97)break;
      z-=0.03;
      if(z<1.02){resetFit(f);return;}
    }
    f.style.transformOrigin='0 0';f.style.transform='scale('+z+')';
    f.style.marginTop=Math.max(0,(avail-f.offsetHeight*z)*0.28)+'px';
  }
  function fit(){
    var r=reading();viewer.classList.toggle('reading',r);
    if(r){sizer.style.width='';sizer.style.height='';stage.style.transform='';slides.forEach(function(s){var f=s.querySelector('.sfit');if(f)resetFit(f);});return;}
    var w=wrap.clientWidth,h=wrap.clientHeight,s=Math.min(w/1280,h/720);
    sizer.style.width=(1280*s)+'px';sizer.style.height=(720*s)+'px';stage.style.transform='scale('+s+')';
    fitSlide(slides[i]);
  }
  function show(k,fromHash){
    i=Math.max(0,Math.min(n-1,k));
    slides.forEach(function(s,j){s.classList.toggle('active',j===i);});
    if(!reading())fitSlide(slides[i]);
    bar.style.width=((i+1)/n*100)+'%';cnt.textContent=(i+1)+' / '+n;
    if(!fromHash){try{history.replaceState(null,'','#s'+(i+1));}catch(e){}}
  }
  function go(d){show(i+d);}
  document.getElementById('prev').addEventListener('click',function(){go(-1);});
  document.getElementById('next').addEventListener('click',function(){go(1);});
  document.addEventListener('keydown',function(e){
    if(reading()||e.target.tagName==='BUTTON'&&(e.key===' '||e.key==='Enter'))return;
    if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '){e.preventDefault();go(1);}
    else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();go(-1);}
    else if(e.key==='Home'){show(0);}else if(e.key==='End'){show(n-1);}
  });
  var tx=null;
  stage.addEventListener('touchstart',function(e){tx=e.touches[0].clientX;},{passive:true});
  stage.addEventListener('touchend',function(e){if(tx===null||reading())return;var d=e.changedTouches[0].clientX-tx;if(Math.abs(d)>50)go(d<0?1:-1);tx=null;});
  [].forEach.call(document.querySelectorAll('.opt'),function(b){
    b.addEventListener('click',function(){
      var q=b.closest('.quizq');[].forEach.call(q.querySelectorAll('.opt'),function(o){o.classList.remove('right','wrong');});
      b.classList.add(b.dataset.ans==='1'?'right':'wrong');
      if(b.dataset.ans!=='1'){var c=q.querySelector('.opt[data-ans="1"]');if(c)c.classList.add('right');}
      q.querySelector('.why').hidden=false;
    });
  });
  window.addEventListener('resize',fit);window.addEventListener('load',fit);window.addEventListener('orientationchange',fit);
  if(window.ResizeObserver){try{new ResizeObserver(function(){fit();}).observe(wrap);}catch(e){}}
  if(window.requestAnimationFrame)requestAnimationFrame(function(){fit();});
  window.__deck={go:go,show:show,count:n,fit:fit};
  if(document.fonts&&document.fonts.ready)document.fonts.ready.then(function(){if(!reading())fitSlide(slides[i]);});
  var m=/^#s(\d+)$/.exec(location.hash);fit();show(m?parseInt(m[1],10)-1:0,true);
  window.addEventListener('hashchange',function(){var m=/^#s(\d+)$/.exec(location.hash);if(m)show(parseInt(m[1],10)-1,true);});
})();
"""


def render_slide(s: Dict, idx: int, total: int, ctx: Dict) -> str:
    sid = s["id"]
    if s["kind"] == "title":
        meta = s["meta"]
        for k, v in ctx["vars"].items():
            meta = meta.replace(f"%%{k}%%", str(v))
        return (f'<section class="slide title" id="{sid}" data-n="{idx}"><h1 class="big">{esc(s["title"])}</h1>'
                f'<p class="sub"><span>Volume</span><i>·</i><span>Price</span><i>·</i><span>Mix</span></p>'
                f'<p class="lead">{esc(s["lead"])}</p><p class="meta">{esc(meta)}</p></section>')
    title = s["title"]
    for k, v in ctx["vars"].items():
        title = title.replace(f"%%{k}%%", str(v))
    body = "".join(r_block(b, ctx) for b in s.get("blocks", []))
    nofit = s["kind"] == "appendix" or any(b["t"] == "quiz" for b in all_blocks(s.get("blocks", [])))
    if s.get("wiki"):
        chips = " ".join(f"<code>{esc(w)}</code>" for w in s["wiki"])
        foot = f'<span class="src">Wiki 資料：{chips}</span>'
    elif s["kind"] == "appendix":
        foot = '<span class="src">由程式依 Wiki 自動產生</span>'
    else:
        foot = '<span class="src">本頁是概念整理，沒有引用數字</span>'
    return (f'<section class="slide" id="{sid}" data-n="{idx}"{" data-fit=\"0\"" if nofit else ""}><header><div class="kicker">{esc(s.get("kicker", ""))}</div><h2>{esc(title)}</h2></header>'
            f'<div class="sbody"><div class="sfit">{body}</div></div><footer>{foot}<span class="pg">{idx} / {total}</span></footer></section>')


def render_html(slides: List[Dict], ctx: Dict, standalone: bool) -> str:
    total = len(slides)
    secs = "\n".join(render_slide(s, k + 1, total, ctx) for k, s in enumerate(slides))
    fonts = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Space+Grotesk:wght@500;700&display=swap">')
    app = (f'<div class="viewer"><div class="stagewrap"><div class="sizer"><div class="stage">\n{secs}\n</div></div></div>'
           f'<div class="controls"><button id="prev" type="button" aria-label="上一頁">← 上一頁</button><div class="bar"><i></i></div>'
           f'<span class="cnt">1 / {total}</span><button id="next" type="button" aria-label="下一頁">下一頁 →</button>'
           f'<span class="hint">鍵盤 ← → 換頁</span></div></div>')
    head = f'<title>{TITLE}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n{fonts}\n<style>{CSS}</style>'
    if standalone:
        return ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
                f'{head}\n</head>\n<body>\n{app}\n<script>{JS}</script>\n</body>\n</html>\n')
    return f'{head}\n{app}\n<script>{JS}</script>\n'


# ----------------------------------------------------------------------------- 主流程
def main_with(label: str = "", record: str | None = None) -> int:
    t0 = time.time()
    gate = WL.run(label=f"{label}-gate", quiet=True)
    if not gate["summary"]["passed"]:
        print("✗ Wiki 檢查未通過，不產生簡報。請先 python wiki_pipeline.py check")
        return 2
    registry = WL.load_sources(WL.Issues())
    spec = importlib.import_module("slides_spec")
    importlib.reload(spec)
    slides = spec.SLIDES
    res = lint_slides(slides, registry)
    errs = [i for i in res["issues"] if i["severity"] == "error"]
    warns = [i for i in res["issues"] if i["severity"] == "warn"]
    for i in res["issues"]:
        print(f"  {i['slide']:<4} {i['code']:<9} {i['msg']}")
    st = res["stats"]
    print("=" * 70)
    print(f"slides={len(slides)}  numbers traced={st.get('numbers_traced', 0)}/{st.get('numbers_checked', 0)}  "
          f"quotes verified={st.get('quotes_verified', 0)}/{st.get('quotes', 0)}  retrieval ok={st.get('retr_ok', 0)}/{st.get('retr_total', 0)}")
    print(f"errors={len(errs)} warnings={len(warns)}")
    summary = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "stage": "slides-lint", "label": label, "slides": len(slides),
               **st, "errors": len(errs), "warnings": len(warns),
               "error_codes": dict(Counter(i["code"] for i in errs)), "warn_codes": dict(Counter(i["code"] for i in warns)),
               "passed": not errs, "issues": res["issues"]}
    if record:
        rp = ROOT / record
        rp.parent.mkdir(parents=True, exist_ok=True)
        with rp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    if errs:
        print("RESULT: FAIL ❌（未產生 HTML）")
        return 1
    ctx = {"vars": {"n_sources": gate["summary"]["sources"], "n_evidence": gate["summary"]["evidence_verified"]},
           "mapping_html": build_mapping(slides, registry), "sources_html": build_sources(registry)}
    out = ROOT / "slides"
    (out / "index.html").write_text(render_html(slides, ctx, True), encoding="utf-8")
    (out / "index.artifact.html").write_text(render_html(slides, ctx, False), encoding="utf-8")
    print(f"RESULT: PASS ✅  → slides/index.html（{(out / 'index.html').stat().st_size // 1024} KB），耗時 {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main_with(label=sys.argv[1] if len(sys.argv) > 1 else "", record="logs/runs.jsonl"))
