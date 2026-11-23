#!/usr/bin/env python3
"""
wiki_site.py — 把 wiki/*.md 轉成一個可瀏覽的單頁網站（作業第 2 項「Wiki 連結或成果」）

  • 左側目錄：首頁 / 規則書 / 討論稿 / 概念 / 實體 / 來源 / 操作紀錄
  • 每個證據句 {{id: "原文"}} 會把英文原文直接顯示在句子下方
  • [[concepts/price]] 變成站內連結（hash 路由 #concepts-price）
  • 首頁附「最近一次 Wiki 檢查」的實際數字（來自 logs/runs.jsonl）
輸出：wiki_site/index.html（單檔）、wiki_site/index.artifact.html（發佈用片段）
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIKI = ROOT / "wiki"
OUT = ROOT / "wiki_site"
TITLE = "Volume Price Mix Wiki"

EVID = re.compile(r'\{\{\s*([a-z0-9][a-z0-9\-]*)\s*:\s*"(.+?)"\s*\}\}')
CALC = re.compile(r"<!--\s*calc:\s*(.+?)\s*-->")
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")

GROUPS = [("", "首頁與規則"), ("discussions", "先討論：討論稿"), ("concepts", "概念（10）"), ("entities", "公司（5）"),
          ("sources", "來源（10）"), ("log", "操作紀錄")]


def pid(rel: str) -> str:
    return rel.replace("/", "-")


def inline(s: str) -> str:
    # 先抽出證據與 calc，避免被其他規則破壞
    evs, calcs = [], []

    def take_ev(m):
        evs.append((m.group(1), m.group(2)))
        return f"\x00E{len(evs) - 1}\x00"

    def take_calc(m):
        calcs.append(m.group(1))
        return f"\x00C{len(calcs) - 1}\x00"

    s = EVID.sub(take_ev, s)
    s = CALC.sub(take_calc, s)
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)

    def link(m):
        tgt, alias = m.group(1).strip(), m.group(2)
        label = alias or tgt.split("/")[-1]
        return f'<a href="#{pid(tgt)}" data-go="{pid(tgt)}">{label}</a>'

    s = LINK.sub(link, s)
    for i, (sid, q) in enumerate(evs):
        s = s.replace(f"\x00E{i}\x00", f'<span class="ev" lang="en"><a href="#sources-{sid}" data-go="sources-{sid}">{sid}</a>“{html.escape(q, quote=False)}”</span>')
    for i, c in enumerate(calcs):
        s = s.replace(f"\x00C{i}\x00", f'<span class="calc" title="程式驗算">驗算 {html.escape(c, quote=False)}</span>')
    return s


def render_md(text: str) -> tuple[str, dict]:
    fm: dict = {}
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for k in range(1, len(lines)):
            if lines[k].strip() == "---":
                for ln in lines[1:k]:
                    if ":" in ln:
                        a, b = ln.split(":", 1)
                        fm[a.strip()] = b.strip()
                lines = lines[k + 1:]
                break
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf), quote=False) + "</code></pre>")
            continue
        if re.match(r"^#{1,4}\s", ln):
            n = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{n + 1}>{inline(ln[n:].strip())}</h{n + 1}>")
            i += 1
            continue
        if ln.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:\-|]+\|\s*$", lines[i + 1]):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = "<div class='tw'><table><thead><tr>" + "".join(f"<th>{inline(h)}</th>" for h in head) + "</tr></thead><tbody>"
            t += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>"
            out.append(t)
            continue
        if re.match(r"^\s*[-*]\s", ln) or re.match(r"^\s*\d+\.\s", ln):
            ordered = bool(re.match(r"^\s*\d+\.\s", ln))
            items = []
            while i < len(lines) and (re.match(r"^\s*[-*]\s", lines[i]) or re.match(r"^\s*\d+\.\s", lines[i])):
                items.append(re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        if ln.strip().startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + inline(" ".join(buf)) + "</blockquote>")
            continue
        if not ln.strip():
            i += 1
            continue
        buf = [ln]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|\s*[-*]\s|\s*\d+\.\s|\s*\||```|>)", lines[i]):
            buf.append(lines[i])
            i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
    return "\n".join(out), fm


def latest_lint() -> dict:
    last = {}
    for l in (ROOT / "logs" / "runs.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(l)
        if (d.get("stage") or "wiki-lint") == "wiki-lint" and d.get("evidence_total") is not None:
            last = d
    return last


def main() -> None:
    pages = []
    order = {g: n for n, (g, _) in enumerate(GROUPS)}
    files = sorted(WIKI.rglob("*.md"))
    for p in files:
        rel = str(p.relative_to(WIKI))[:-3]
        top = rel.split("/")[0] if "/" in rel else ("log" if rel == "log" else "")
        body, fm = render_md(p.read_text(encoding="utf-8"))
        title = fm.get("title") or ({"index": "首頁（index）", "SCHEMA": "規則書（SCHEMA）", "log": "操作紀錄（log）"}.get(rel, rel))
        chips = ""
        if fm.get("type"):
            keys = ["type", "company", "period", "kind", "batch", "sha256", "updated"]
            chips = "".join(f'<span class="chip"><i>{k}</i>{html.escape(fm[k], quote=False)}</span>' for k in keys if fm.get(k))
            chips = f'<div class="chips">{chips}</div>'
        full = body.replace("</h2>", "</h2>" + chips, 1) if "</h2>" in body else chips + body
        pages.append({"id": pid(rel), "rel": rel, "group": top, "title": title, "html": full})
    pages.sort(key=lambda x: (order.get(x["group"], 9), 0 if x["rel"] == "index" else 1 if x["rel"] == "SCHEMA" else 2, x["rel"]))
    s = latest_lint()
    stat = (f'<div class="statbox"><div><b>{s.get("sources", "?")}</b><span>份來源</span></div><div><b>{s.get("evidence_verified", "?")}/{s.get("evidence_total", s.get("evidence_verified", "?"))}</b><span>條證據逐字比對成功</span></div>'
            f'<div><b>{s.get("numbers_checked", "?")}</b><span>個數字溯源</span></div><div><b>{s.get("calc_verified", "?")}</b><span>個計算驗算</span></div>'
            f'<div><b>{s.get("errors", "?")}</b><span>個錯誤</span></div></div>'
            f'<p class="note">以上是 <code>python wiki_lint.py</code> 最近一次的結果；Wiki 沒通過檢查，就不會產生簡報。</p>')
    for p in pages:
        if p["rel"] == "index":
            p["html"] = p["html"] + "<h2>最近一次 Wiki 檢查</h2>" + stat
    nav = ""
    for g, label in GROUPS:
        items = [p for p in pages if p["group"] == g]
        if not items:
            continue
        nav += f'<div class="ng">{label}</div>' + "".join(f'<a class="ni" href="#{p["id"]}" data-go="{p["id"]}">{html.escape(p["title"], quote=False)}</a>' for p in items)
    data = json.dumps({p["id"]: {"t": p["title"], "h": p["html"]} for p in pages}, ensure_ascii=False).replace("</", "<\\/")
    css = CSS
    app = (f'<div class="app"><header class="top"><div class="brand">LLM Wiki<span>Volume · Price · Mix</span></div></header>'
           f'<details class="navwrap" id="navwrap" open><summary>目錄</summary><nav>{nav}</nav></details>'
           f'<main id="main" tabindex="-1"></main></div>')
    js = JS.replace("__DATA__", data)
    head = f'<title>{TITLE}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Space+Grotesk:wght@500;700&display=swap">\n<style>{css}</style>'
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text('<!doctype html>\n<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
                                    + head + f'</head><body>{app}<script>{js}</script></body></html>', encoding="utf-8")
    (OUT / "index.artifact.html").write_text(f"{head}\n{app}\n<script>{js}</script>\n", encoding="utf-8")
    print(f"wiki_site: {len(pages)} pages → wiki_site/index.html ({(OUT / 'index.html').stat().st_size // 1024} KB)")


CSS = r"""
:root{--bg:#EDF1EF;--paper:#fff;--ink:#14201D;--muted:#566763;--line:#D3DCD9;--soft:#E4EEEB;--accent:#0A6B5C;--accent-ink:#fff;
--ev-bg:#EEF2FA;--ev-ink:#2A3B63;--calc:#7A4E00;--calc-bg:#F7E9CF;
--display:"Space Grotesk","Noto Sans TC","PingFang TC","Microsoft JhengHei",system-ui,sans-serif;--body:"Noto Sans TC","PingFang TC","Microsoft JhengHei","Noto Sans CJK TC",system-ui,sans-serif;--mono:ui-monospace,Menlo,Consolas,monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0B1210;--paper:#141D1A;--ink:#E7EFEC;--muted:#9FB2AC;--line:#26342F;--soft:#1B2A25;--accent:#4FD1B8;--accent-ink:#06201A;--ev-bg:#18223A;--ev-ink:#B8C8F2;--calc:#E8B04A;--calc-bg:#3A2D12;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0B1210;--paper:#141D1A;--ink:#E7EFEC;--muted:#9FB2AC;--line:#26342F;--soft:#1B2A25;--accent:#4FD1B8;--accent-ink:#06201A;--ev-bg:#18223A;--ev-ink:#B8C8F2;--calc:#E8B04A;--calc-bg:#3A2D12;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 var(--body);padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));overflow-x:hidden}
.app{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:260px minmax(0,1fr);grid-template-areas:"top top" "nav main";gap:0 28px;padding-block:14px 40px}
.top{grid-area:top;padding:6px 0 14px}.brand{font:700 22px var(--display)}.brand span{font:600 13px var(--display);color:var(--accent);margin-left:12px;letter-spacing:.08em;text-transform:uppercase}
.navwrap{grid-area:nav;align-self:start;position:sticky;top:12px;max-height:calc(100vh - 24px);overflow:auto;background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:6px 10px 12px}
.navwrap summary{cursor:pointer;font-weight:700;padding:8px 4px;list-style:none}
.ng{font:700 12px var(--display);letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin:12px 4px 4px}
.ni{display:block;padding:5px 8px;border-radius:7px;color:var(--ink);text-decoration:none;font-size:14px;line-height:1.4}
.ni:hover{background:var(--soft)}.ni.on{background:var(--accent);color:var(--accent-ink);font-weight:700}
main{grid-area:main;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:26px 30px 34px;min-width:0;outline:none}
h2{font:700 28px/1.3 var(--body);margin:0 0 6px}h3{font:700 20px/1.4 var(--body);margin:26px 0 6px;padding-top:10px;border-top:1px solid var(--line)}h4,h5{margin:18px 0 4px}
p{margin:8px 0}ul,ol{margin:6px 0 10px;padding-left:1.3em}li{margin:5px 0}
code{font-family:var(--mono);font-size:.84em;background:var(--soft);padding:.08em .4em;border-radius:4px;overflow-wrap:anywhere}
pre{background:var(--soft);border-radius:10px;padding:12px 14px;overflow-x:auto;font-size:13px;line-height:1.5}pre code{background:none;padding:0}
a{color:var(--accent)}blockquote{margin:8px 0;padding:8px 14px;border-left:4px solid var(--accent);background:var(--soft);border-radius:0 8px 8px 0}
.ev{display:block;margin:4px 0 2px 0;padding:5px 10px;background:var(--ev-bg);color:var(--ev-ink);border-radius:8px;font:italic 400 14px/1.5 Georgia,"Times New Roman",serif}
.ev a{font:600 12px var(--mono);font-style:normal;margin-right:8px;color:var(--accent)}
.calc{display:inline-block;font:600 12px var(--mono);background:var(--calc-bg);color:var(--calc);border-radius:6px;padding:1px 8px;margin-left:6px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px}.chip{font:500 12px var(--mono);background:var(--soft);border-radius:999px;padding:2px 10px}.chip i{font-style:normal;color:var(--muted);margin-right:6px}
.tw{overflow-x:auto}table{border-collapse:collapse;font-size:14px;min-width:420px}th,td{text-align:left;padding:7px 12px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}
.statbox{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:10px 0}.statbox div{background:var(--soft);border-radius:12px;padding:12px 14px}
.statbox b{display:block;font:700 28px/1.1 var(--display);color:var(--accent)}.statbox span{font-size:13px;color:var(--muted)}.note{font-size:13px;color:var(--muted)}
@media (max-width:820px){.app{grid-template-columns:minmax(0,1fr);grid-template-areas:"top" "nav" "main"}.navwrap{position:static;max-height:60vh}main{padding:18px 16px 26px}h2{font-size:23px}}
"""

JS = r"""
(function(){
  var D=__DATA__, main=document.getElementById('main'), wrap=document.getElementById('navwrap');
  function show(id,push){
    if(!D[id]) id='index';
    main.innerHTML=D[id].h;
    [].forEach.call(document.querySelectorAll('.ni'),function(a){a.classList.toggle('on',a.dataset.go===id);});
    main.scrollTop=0; window.scrollTo(0,0);
    if(push){try{history.replaceState(null,'','#'+id);}catch(e){}}
    if(window.innerWidth<=820)wrap.open=false;
  }
  document.addEventListener('click',function(e){
    var a=e.target.closest&&e.target.closest('a[data-go]'); if(!a)return;
    e.preventDefault(); show(a.dataset.go,true);
  });
  window.addEventListener('hashchange',function(){show(location.hash.slice(1),false);});
  if(window.innerWidth<=820)wrap.open=false;
  show(location.hash.slice(1)||'index',false);
})();
"""

if __name__ == "__main__":
    main()
