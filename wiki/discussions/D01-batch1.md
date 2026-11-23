---
type: discussion
title: D01 批次 1 討論稿（先討論、後生成）— 5 份法說會逐字稿
---
# D01 批次 1 討論稿

**狀態**：AI 提案 → 採用（學生可在下方「決議」欄改掉任何一項，改完重跑 lint 即可）
**目的**：在寫任何 Wiki 頁面之前，先決定「這 5 份來源各自能教什麼、要新增或更新哪些頁面、哪裡有疑點」。

## 0. 範圍決議（來自學生的需求）
- 作業要求「用附件的 HW3 檔案改」→ 沿用 HW3 的 20 份財報資料，不另找新主題。
- 主題收斂為：**看懂消費品公司的成長（Volume / Price / Mix）**。理由：HW3 的資料全是「公司怎麼解釋成長」，而這是最適合初學者的切入點，且不需要財務背景。
- 讀者：完全沒學過財報的人。

## 1. 本批來源與預讀重點

| id | 文件 | 預讀到的重點（尚未寫進 Wiki，待證據化） | 對主題的價值 |
|---|---|---|---|
| ko-q4-2025 | KO Q4 2025 法說會（FactSet） | 有機營收成長 5%、銷量 1%、price/mix 1%（價格約 4 點、組合 −3 點）；CEO 要大家看「四季平均」；2026 指引 organic revenue 4–5%，期望價與量回到約 50/50 | **最佳範例**：能示範 price/mix 如何被單季組合拖累 |
| pg-q2-fy2026 | PG FY2026 Q2 法說會（Motley Fool） | 有機銷售持平：銷量 −1、價格 +1、組合 0；北美銷量 −3 其中約 2 點來自去年同期（港口罷工）囤貨的基期；全年指引 in line 到 +4%；關稅成本約 5 億美元 | 示範「基期效應」與價 / 量 / 組合分開報 |
| kmb-q4-2025 | KMB Q4 2025 法說會（Motley Fool） | volume+mix +1.7%（預讀時誤寫成「北美」，已於 log 更正）；分析師問「price/mix 在減速」→ 管理層用三件事解釋（促銷、club 通路組合、價格包裝投資）；good-better-best 階梯；Costco 鋪貨損失約 60 bp | 示範「mix 下降不一定是壞事」 |
| khc-q4-2025 | KHC Q4 2025 法說會（Motley Fool） | 只有 Q&A（沒有 prepared remarks）；暫停分拆、增加約 6 億美元品牌投資，其中約一半用在價格、產品、包裝；目標「volume-led profitable growth」 | 示範「價值導向 / 開口價 / 再投資」，**不拿來抓數字** |
| wmt-q4-fy2026 | WMT Q4 FY2026 法說會（FactSet） | 營收 +4.9%（固定匯率）、eCommerce +24%；營業利益 +10.5%；廣告 +37%、會員收入 +15% 以上，兩者合計近三分之一營業利益；庫存增速約為銷售的一半 | 示範**零售商的「mix」是事業組合**，和品牌商的產品組合不同 |

## 2. 擬建立的頁面
- **concepts（先建 9 個）**：organic-growth、volume、price、mix、reporting-conventions（各家報法不同）、timing-and-base-effects（單季雜訊與基期）、value-and-affordability、cost-and-productivity、retail-business-mix、guidance（共 10）。
- **entities**：ko、pg、kmb、khc、wmt。
- **sources**：上表 5 頁。
- 批次 2 再用 10-K 補「正式定義」，屆時會**更新** volume / price / mix / organic-growth / reporting-conventions 這幾頁（練習「新資料改舊頁」）。

## 3. 疑點與決議

| # | 疑點 | 決議 |
|---|---|---|
| 1 | 各家期間不一致：KO / KMB / KHC 是日曆年 Q4 2025；PG 的 FY2026 Q2 其實是 2025 年 10–12 月；WMT 的 Q4 FY2026 是 2025 年 11 月–2026 年 1 月 | 每條數字都標「公司＋期間」，不做跨公司同期比較 |
| 2 | KHC、KMB 的逐字稿來源（Motley Fool）開頭可能缺 prepared remarks（KHC 確定只有 Q&A） | KHC 只拿來支撐概念（再投資、價格帶），**數字改由批次 2 的 10-K 提供** |
| 3 | 「四季平均看價/量」是 KO 管理層的**個人建議**，不是通用規則 | 寫進 timing-and-base-effects 時標明是 KO CEO 的說法 |
| 4 | WMT 講的 mix 是 business mix / category mix，品牌商講的是產品、包裝、通路、地區 mix | 在 mix 頁分兩節；另建 retail-business-mix 頁，不硬合併 |
| 5 | 引文是英文、頁面是中文 | 主張中文、證據英文逐字；lint 以英文原文比對 |
| 6 | 要不要把 20 份都 ingest？ | 不要。品質重於數量；先 5 份寫好、再補 10-K 定義，其餘列為「未 ingest」 |

## 4. 學生決議欄
- [x] 採用上述 AI 提案（如要修改，直接改本檔並在 log 記一筆 `discuss`）
