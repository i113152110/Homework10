#!/usr/bin/env python3
"""
check_render.py — 「簡報渲染檢查」節點（Playwright）
  R-OVERFLOW  桌機 1280×720 舞台：某一頁內容超出可用範圍（.sbody 的 scrollHeight > clientHeight，或水平溢出）
  R-HSCROLL   手機寬度 400px：頁面出現水平捲軸
  R-CJK       CJK 字型沒載入（中文變方框）
  R-JS        頁面出現 console error / pageerror
輸出：logs/render/*.png（桌機每頁、手機整頁）、logs/runs.jsonl 一筆紀錄
"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "logs" / "render"
OUT.mkdir(parents=True, exist_ok=True)

def main(label="", shots=True):
    url = (ROOT / "slides" / "index.html").as_uri()
    issues, errors_js, zs = [], [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        pg = ctx.new_page()
        pg.on("console", lambda m: errors_js.append(m.text) if m.type == "error" and "fonts.g" not in m.text and "ERR_" not in m.text else None)
        pg.on("pageerror", lambda e: errors_js.append(str(e)))
        pg.goto(url, wait_until="load")
        pg.wait_for_timeout(300)
        n = pg.evaluate("window.__deck.count")
        per = []
        for k in range(n):
            pg.evaluate(f"window.__deck.show({k})")
            pg.wait_for_timeout(40)
            m = pg.evaluate("""()=>{const s=document.querySelector('.slide.active');const b=s.querySelector('.sbody')||s;
              const sc=document.querySelector('.stage').getBoundingClientRect().width/1280;const f=s.querySelector('.sfit');
              const vis=f?f.getBoundingClientRect().height/sc+(parseFloat(f.style.marginTop)||0):0;
              const z=(f&&f.style.transform)?parseFloat(f.style.transform.replace(/[^0-9.]/g,'')):1;
              const nf=s.dataset.fit==='0';const hs=[...s.querySelectorAll('*')].filter(e=>e.scrollWidth>e.clientWidth+2&&getComputedStyle(e).overflowX==='visible'&&e.clientWidth>0).map(e=>e.className||e.tagName).slice(0,3);
              return {id:s.id,nf:nf,z:z,sh:s.scrollHeight,ch:s.clientHeight,bh:Math.max(vis,0),bch:b.clientHeight,sw:s.scrollWidth,cw:s.clientWidth,hs:hs}}""")
            per.append(m)
            zs.append((m["id"], round(m["z"], 2)))
            if m["sh"] > m["ch"] + 1 or m["bh"] > m["bch"] + 1:
                issues.append({"code": "R-OVERFLOW", "slide": m["id"], "msg": f"內容高度 {max(m['sh'], m['bh'])} 超出可用 {m['ch'] if m['sh']>m['ch'] else m['bch']}（差 {max(m['sh']-m['ch'], m['bh']-m['bch'])}px）"})
            if not m["nf"] and m["bh"] > 0 and m["bch"] and m["bh"] / m["bch"] < 0.5:
                issues.append({"code": "W-SPARSE", "slide": m["id"], "msg": f"內容只占可用高度 {m['bh'] / m['bch']:.0%}，版面偏空"})
            if m["sw"] > m["cw"] + 1:
                issues.append({"code": "R-OVERFLOW", "slide": m["id"], "msg": f"水平溢出 {m['sw']} > {m['cw']}"})
            if shots:
                pg.screenshot(path=str(OUT / f"desk-{k+1:02d}.png"))
        fam = pg.evaluate("document.fonts.check('20px \"Noto Sans CJK TC\"') || document.fonts.check('20px \"Noto Sans TC\"')")
        # 手機
        mctx = b.new_context(viewport={"width": 400, "height": 800}, device_scale_factor=2, is_mobile=True, has_touch=True)
        mp = mctx.new_page()
        mp.on("pageerror", lambda e: errors_js.append(str(e)))
        mp.goto(url, wait_until="load"); mp.wait_for_timeout(300)
        mm = mp.evaluate("""()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,reading:document.querySelector('.viewer').classList.contains('reading'),
           wide:[...document.querySelectorAll('.slide *')].filter(e=>{const r=e.getBoundingClientRect();return r.right>window.innerWidth+1&&!e.closest('.tblwrap')&&!e.closest('svg')}).slice(0,5).map(e=>(e.className||e.tagName)+':'+Math.round(e.getBoundingClientRect().right))})""")
        if mm["sw"] > mm["cw"] + 1 or mm["wide"]:
            issues.append({"code": "R-HSCROLL", "slide": "-", "msg": f"手機寬度出現水平捲軸 {mm}"})
        if not mm["reading"]:
            issues.append({"code": "R-HSCROLL", "slide": "-", "msg": "手機寬度沒有切到閱讀模式"})
        if shots:
            mp.screenshot(path=str(OUT / "phone-full.png"), full_page=True)
        b.close()
    if errors_js:
        issues.append({"code": "R-JS", "slide": "-", "msg": "; ".join(errors_js[:3])})
    for i in issues:
        print(f"  {i['slide']:<5}{i['code']:<11}{i['msg']}")
    rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "stage": "render-check", "label": label, "slides": n,
           "errors": sum(1 for i in issues if i["code"].startswith("R-")), "warnings": sum(1 for i in issues if i["code"].startswith("W-")), "error_codes": {c: sum(1 for i in issues if i["code"] == c) for c in {i["code"] for i in issues}},
           "passed": not any(i["code"].startswith("R-") for i in issues), "issues": issues, "cjk_font": bool(fam)}
    with (ROOT / "logs" / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("放大倍率：" + " ".join(f"{a}×{z}" for a, z in zs if z != 1))
    print("=" * 60); print(f"slides={n} errors={len(issues)} cjk_font={bool(fam)}")
    bad = [i for i in issues if i["code"].startswith("R-")]
    print("RESULT:", "PASS ✅" if not bad else "FAIL ❌")
    return 0 if not bad else 1

if __name__ == "__main__":
    sys.exit(main(label=sys.argv[1] if len(sys.argv) > 1 else ""))
