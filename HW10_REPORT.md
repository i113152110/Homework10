# 第十週作業｜用 LLM Wiki 做一份教學 HTML 簡報

**繳交標題**：`［學校］ 113152110 ［系級］ ［姓名］ 看懂消費品公司的成長：Volume / Price / Mix`
（學校、系級、姓名請自行補上；學號依 GitHub 帳號 i113152110 推得，請確認。）

> 本作業沿用 HW3（build your personal RAG）的專案：同一份 20 個 PDF、同一支 `data_update.py` 與 `rag_query.py`，改成 LLM Wiki 流程。HW3 的檔案都還在，新增的是 `wiki/`、`wiki_lint.py`、`wiki_query.py`、`wiki_pipeline.py`、`build_slides.py`、`check_render.py`、`slides/`。

---

## 1. LLM Wiki 主題與簡短介紹

**主題：看懂消費品公司的成長 —— Volume（銷量）/ Price（價格）/ Mix（組合）。**

財報常說「營收成長 5%」，但新手分不出這 5% 是「賣得更多」、「賣得更貴」，還是「賣的東西變了」。這個 Wiki 用可口可樂（KO）、寶僑（PG）、金百利克拉克（KMB）、卡夫亨氏（KHC）、沃爾瑪（WMT）五家公司的真實法說會與年報，整理出初學者需要的概念、各家的說法與容易誤會的地方。

- **資料來源**：HW3 的 20 份文件中，ingest 了 10 份（5 份 2025 年 Q4 / FY2026 法說會逐字稿 + 5 份年報 10-K）。其餘 10 份**沒有 ingest，Wiki 與簡報都不引用**。
- **內容**：10 個概念頁、5 個公司頁、10 個來源頁，另有規則書 `SCHEMA.md`、目錄 `index.md`、操作紀錄 `log.md`、兩份討論稿。
- **每一條主張都附英文原文**，格式 `{{來源id: "逐字引文"}}`；數字必須出現在同一行的引文裡，推算的數字要寫 `<!--calc: 4-3=1-->` 讓程式驗算。
- **先討論、後生成**：每批來源在生成頁面前，先寫討論稿（預讀重點、擬建頁面、疑點與決議）：`wiki/discussions/D01-batch1.md`、`D02-batch2.md`。

## 2. LLM Wiki 連結或成果

- **可瀏覽的 Wiki**：https://claude.ai/artifact/9DjFfwmP3DwcUS8kuc8PoN
  （左側目錄可看每一頁；每個證據句下方直接顯示英文原文；首頁有最近一次檢查結果）
- **原始檔**：壓縮檔內的 `wiki/`（markdown，可直接用編輯器或 Obsidian 開啟）

節錄一條 Wiki 裡的證據句（`wiki/sources/ko-q4-2025.md`）：

```
- Q4 的 price/mix 只有 1%：約 4 點來自漲價，被 3 點不利的組合抵銷。
  {{ko-q4-2025: "Our price/mix growth of 1% was primarily driven by approximately 4 points of pricing actions, offset by 3 points of unfavorable mix"}} <!--calc: 4-3=1-->
```

## 3. 教學 HTML 簡報連結

- **簡報**：https://claude.ai/artifact/VZgkB7AqmRLU6QbdiqER3E
  （22 頁；鍵盤 ← → 換頁；手機寬度自動變成由上往下的閱讀模式）

**教學結構**：先問一個問題（KO 營收 +5%、銷量只有 +1%）→ 三個詞 → 公式（先用虛構數字，再用真實數字驗證）→ 案例（KO、PG、KHC）→ 三個陷阱（各家報法不同、單季雜訊與基期、零售商的 mix 是事業組合）→ 公司怎麼回應（價值導向、成本、指引）→ 四個問題的讀法 → 小測驗 → 附錄（流程圖、簡報↔Wiki 對照、來源清單）。

**簡報 ↔ Wiki 對應表**（由 `slides/slides_spec.py` 產生；簡報每一頁底部也標出引用的 Wiki 頁面，附錄 B 有簡化版）

| 頁 | 簡報標題 | 對應的 Wiki 概念頁 | 對應的來源頁 |
|---|---|---|---|
| 2 | 學完這份簡報，你可以… | （概念整理） | — |
| 3 | 營收成長 5%，是好消息嗎？ | —（直接引用來源） | ko-q4-2025 |
| 4 | 三個詞，拆開看成長 | volume, price, mix | — |
| 5 | 成長可以加起來：銷量 + 價格 + 組合 | organic-growth | — |
| 6 | 真實數字也能加起來 | organic-growth | ko-10k-fy2025, khc-10k-fy2025, pg-q2-fy2026 |
| 7 | 「有機成長」就是只看本業 | organic-growth | pg-10k-fy2025 |
| 8 | 價格 4、組合 −3，price/mix 只剩 1 | mix, timing-and-base-effects | ko-q4-2025 |
| 9 | mix 變負，不一定是壞事 | mix, price | ko-10k-fy2025, kmb-q4-2025 |
| 10 | price/mix 不是量出來的，是倒推出來的 | mix | ko-10k-fy2025 |
| 11 | 銷量 −3，但有 2 點是「去年太好」 | timing-and-base-effects | pg-q2-fy2026 |
| 12 | 各家報法不同：mix 跟誰綁在一起？ | reporting-conventions | ko-10k-fy2025, khc-10k-fy2025, pg-10k-fy2025, kmb-10k-fy2025 |
| 13 | 漲價救不了銷量 | price, value-and-affordability | khc-10k-fy2025, khc-q4-2025 |
| 14 | 消費者更會比價，公司怎麼回應？ | value-and-affordability | kmb-q4-2025, ko-q4-2025, khc-q4-2025, wmt-q4-fy2026 |
| 15 | 零售商的 mix 是「事業組合」 | retail-business-mix | wmt-q4-fy2026 |
| 16 | 成本壓力：關稅、原物料，以及生產力 | cost-and-productivity | pg-q2-fy2026, khc-10k-fy2025, ko-q4-2025 |
| 17 | 管理層指引：對下一年的預測區間 | guidance | ko-q4-2025, pg-q2-fy2026, wmt-q4-fy2026, kmb-q4-2025 |
| 18 | 三分鐘讀法：四個問題 | （概念整理） | — |
| 19 | 換你判斷 | mix, reporting-conventions, timing-and-base-effects | ko-q4-2025 |

第 1 頁為封面；第 20–22 頁為附錄（流程圖、對照表、來源清單）。

## 4. loop / graph 設計

```
主線：① 取得資料 → ② 先討論 → ③ 後生成 → ④ 檢查 Wiki → ⑤ 查詢 Wiki → ⑥ 整理成簡報 → ⑦ 檢查簡報 → ⑧ 發佈

回流：④ 檢查 Wiki   ──不通過──────────────→ ③ 後生成    （修正後重跑 lint，直到 0 error）
      ⑤ 查詢 Wiki   ──Wiki 缺口（查不到）──→ ② / ③      （退回 raw 查，補 ingest 後才能用）
      ⑦ 檢查簡報   ──不通過──────────────→ ⑥ 整理成簡報 （修正後重新產生，再檢查）

節點性質：①⑤⑧ 由程式執行；②③⑥ 由 AI 撰寫；④⑦ 由程式檢查（沒有 LLM）
```
圖形版見簡報附錄 A（第 20 頁），用顏色區分「程式執行 / AI 撰寫 / 程式檢查」，紅線是三條回流。

**重複的部分**
1. **③ ↔ ④（生成 ↔ 檢查 Wiki）**：寫完一批頁面就跑 `wiki_lint.py`，有 error 就修、再跑，直到 0 error 才往下。
2. **⑥ ↔ ⑦（整理簡報 ↔ 檢查簡報）**：簡報檢查（數字溯源、引文逐字比對、概念頁是否都被用到）與渲染檢查（每頁溢出、手機寬度、版面太空）不過，就回頭改簡報規格，再產生一次。
3. **⑤ → ② / ③（Wiki 缺口回流）**：設計簡報時用 `wiki_query.py` 查 Wiki；查不到（或問題指定的公司季度沒被 ingest）就退回 raw chunk 查，並在 `log.md` 記一筆「Wiki 缺口」，補進 Wiki 後才能被簡報使用。

**檢查與重新生成發生在哪裡、為什麼**
- **簡報不直接讀 PDF，只能讀 Wiki**；`build_slides.py` 一開始就先跑 Wiki 檢查，沒通過就不產生簡報（閘門）。這樣簡報裡的每個數字都只需要追到 Wiki 的證據句，而證據句已被程式比對過原文。
- **「AI 負責寫、程式負責檢查」**：AI 擅長整理與改寫，但容易數字漂移、把話說過頭；所以檢查用沒有 LLM 的 Python 腳本（逐字比對、數字溯源、算式驗算），不是讓 AI 自己檢查自己。
- **來源在檢查前就鎖版本**：來源頁記錄 PDF 文字的 sha256，原始資料若變了，lint 會報 stale。

## 5. 一次實際執行的結果與檢查紀錄

完整紀錄：`logs/runs.jsonl`（每次檢查一筆）、`wiki/log.md`（操作時間線）、`logs/final_run.txt`（最後一次完整執行）。

**最後一次完整執行**（`logs/final_run.txt`）：

```
$ python wiki_pipeline.py check
sources=10  pages={concepts: 10, entities: 5, sources: 10}
evidence verified: 201/201   numbers checked: 174   calc verified: 12
errors=0   warnings=0                          RESULT: PASS

$ python wiki_pipeline.py slides
slides=22  numbers traced=72/72  quotes verified=9/9  retrieval ok=16/16
errors=0   warnings=0                          RESULT: PASS → slides/index.html

$ python check_render.py
slides=22  errors=0  cjk_font=True            RESULT: PASS
```

**這次執行是怎麼走到 PASS 的**（同樣來自紀錄檔，不是事後整理的理想版本）

| 階段 | 檢查 | 結果 | 發現什麼、怎麼處理 |
|---|---|---|---|
| Wiki 批次 1 第 1 輪 | `wiki_lint` | 引文 145/145 通過，**10 error** | 3 個是檢查器誤判（把「10-K」「批次 2」當成數字）→ 修檢查器；7 個是真的內容問題：mix 頁一個數字 3 只出現在別行的引文裡（**數字漂移**）、AI 的解釋句夾帶沒有證據的數字 → 改寫或搬進「通則」小節 |
| 批次 1 第 2、3 輪 | 同上 | 1 error（`E-CALC`）→ **PASS** | 基點換算 `270/100=2.7` 的 100 不在引文裡被擋下 → 規定 10 的次方可當單位常數（調整檢查器規則）。另做一次**負向測試**：故意植入錯誤，檢查器報出 7 個 error（E-NUM×3、E-QUOTE、E-NOEVID、E-LINK、E-INDEX），證明它真的會報錯 |
| 預讀更正 | 人工對照原文 | — | 討論稿 D01 把 KMB 的 +1.7% 寫成「北美」，對照逐字稿後改為公司整體（`fix` 記在 log） |
| Wiki 批次 2（5 份 10-K） | `wiki_lint` | 第 1 輪 **0 error**（197/197） | 套用批次 1 學到的規則 8–9 之後，第一次檢查就沒有 error |
| 批次 2 人工複查 | 人工 + 新規則 | `E-SECTION` 1 筆 → PASS | 一條 KHC 證據被我的腳本插錯小節（跑到「容易誤會」底下），lint 當時抓不到 → **新增 `E-SECTION` 規則**，內容搬回 |
| Wiki 缺口 | `wiki_query` | 查「KO CEO 底層價格 4% + 銷量 1% = 5%」，**Wiki 缺口** | Wiki 沒有 CEO 把兩者相加的那句；用 `--raw` 找到原始 chunk，補進 3 個頁面，lint 重跑 200/200 通過 |
| 簡報第 1 輪 | 簡報檢查 + 渲染檢查 | 簡報檢查 0 error；**渲染 3 error**（`R-OVERFLOW`） | 編號清單的粗體被拆成 grid 欄位變成直排（s02、s18）；附錄對照表太長（s21）→ 修版面 |
| 簡報第 2–3 輪 | 渲染 + 肉眼看總覽圖 | 渲染 PASS，但看圖發現 9 頁下半部大片留白、流程圖標籤被線劃過 | 程式量不到「好不好看」→ 加上依高度自動放大內容，並**新增 `W-SPARSE` 警告**讓程式以後能檢查 |
| 簡報負向測試 | `build_slides` | 5 種竄改（改錯數字、引用不存在的頁、改引文、有數字沒引用 Wiki、概念頁漏用）**全部被擋下** | `logs/negative_test.jsonl` |
| 發佈外殼測試 | 模擬發佈環境 | 手機寬度沒切到閱讀模式 | 直接開 `index.html` 時沒問題，包上外殼才重現（版面寬度尚未確定就計算）→ 改成載入後、尺寸變化時都重算 |

Wiki 檢查的累計軌跡：批次 1 第 1 輪 10 error → 第 2 輪 1 → 第 3 輪 0；批次 2 第 1 輪 0 → 新規則後 1 → 0；缺口補完 0；簡報前 0（201 條引文、174 個數字、12 個算式）。

**重跑方式**：
```
python wiki_pipeline.py extract      # ① 取得資料（需要 HW3 的 data/raw PDF）
python wiki_pipeline.py check        # ④ 檢查 Wiki
python wiki_query.py "KO Q4 的 price/mix 為什麼只有 1%"   # ⑤ 查詢；加 --raw 退回原始資料
python wiki_pipeline.py slides       # ⑥⑦ 檢查通過才產生 slides/index.html
python check_render.py               # ⑦ 渲染檢查（Playwright）
python wiki_site.py                  # 產生 Wiki 瀏覽網站
```

## 6. 反思

**最容易出錯的節點：③「後生成」（AI 寫 Wiki 頁面）。** 第一輪檢查 10 個 error 裡，真正的內容問題都出在這裡，而且有固定模式：
1. **數字漂移**：某一行的數字，只存在於另一行的引文裡（mix 頁的 3）。
2. **AI 自己寫的解釋句夾帶沒有證據的數字**（基點、區間、年份）。
3. **預讀摘要不等於原文**：D01 把 KMB 的 +1.7% 寫成「北美」，只有回頭對原話才發現。結論是：討論稿只能決定「要寫什麼」，不能當成「事實的來源」，事實一律以引文為準。
4. **放錯位置**：證據被插進「容易誤會」小節，語意變了，但數字與引文都對，原本的 lint 抓不到。

第二個容易出錯的是 ⑥⑦ 簡報的**版面**：內容檢查全過，渲染才發現直排、溢出、留白。這類問題程式檢查器看不到「好不好看」，我是看總覽圖才發現的。

**把檢查提前了哪些地方**
- 第 1 輪錯誤之後，在 `SCHEMA.md` 加規則 8–9（解釋句不放數字、證據放在證據小節），讓 AI **在寫之前**就知道會被檢查；結果批次 2 第一次 lint 就是 0 error。
- 規則 10 要求每份來源寫完就檢查，不要全部寫完才檢查（這次批次 2 仍是五份寫完才跑第一次，之後的 ingest 應照規則 10 做）。
- 把 `wiki_lint` 變成 `build_slides` 的閘門：Wiki 沒過，簡報根本不會產生。
- 簡報設計階段就用 `wiki_query` 查資料，缺口在寫簡報之前就被發現（CEO 4%+1% 那句），不是等簡報做完才發現數字沒依據。
- 把「版面太空」「手機寬度」這類原本靠肉眼的問題，改成 `W-SPARSE`、模擬發佈外殼的測試，下次不用靠運氣。

**流程 / graph 有沒有修改？為什麼？**
- 新增 `E-SECTION` 檢查（來自人工複查發現的放錯位置）。
- 新增「Wiki 缺口 → 回去 ingest」這條回流邊（原本只有「查詢 → 回答」）。
- 在「檢查簡報」裡拆出第二層**渲染檢查**：第一版只檢查內容（數字、引文），結果內容全過、版面卻壞了。
- 把檢查器本身也當成會出錯的節點：第 1 輪有 3 個是檢查器誤判，因此做了負向測試，證明它確實會報錯，而不只是「沒報錯」。

**限制與老實說明**
- 程式檢查的是「引文真的在原文裡」「數字有出現在引文裡」「算式正確」，**不能判斷詮釋是否正確**（例如把 A 公司的定義套到 B 公司）。這類問題要靠討論稿的疑點清單與人工複查。
- 只 ingest 20 份中的 10 份；沒 ingest 的內容不會出現在簡報，這是刻意的邊界，不是遺漏。
- 簡報裡的「虛構範例」是教學用的假想數字，已標示且只能來自 Wiki 的「虛構」小節。
- **AI 使用揭露**：Wiki 頁面、討論稿與簡報由 Claude 在本次對話中撰寫；檢查由上述 Python 腳本執行。討論稿的「決議」欄是 AI 提案後採用，**不是**與同學或老師的討論紀錄，學生應自行閱讀並可修改。
