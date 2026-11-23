---
type: log
title: Wiki 操作紀錄
---
# Wiki 操作紀錄（append-only）

格式：`## [時間] 動作 | 對象`。動作有 `scope`（討論範圍）、`discuss`（先討論）、`ingest`（讀入來源並寫頁面）、`lint`（檢查）、`fix`（依檢查結果修正）、`query`（用 Wiki 回答問題）。
時間戳記由 `wiki_pipeline.py log` 自動產生。

## [2026-11-23 21:08] scope | topic
學生提出：想用 HW3 附件專案來改做這次作業。決議：沿用 HW3 的 20 份文件與 data_update.py；主題定為「看懂消費品公司的成長：Volume / Price / Mix」。

## [2026-11-23 21:08] discuss | D01-batch1
先討論（尚未生成任何頁面）：預讀 5 份法說會，列出重點、擬建頁面、6 個疑點與決議，見 [[discussions/D01-batch1]]。

## [2026-11-23 21:12] ingest | ko-q4-2025
batch 1：新增 sources/ko-q4-2025；建立或更新 concepts（volume/price/mix/…）與對應 entity；依 D01 決議。尚未跑 lint。

## [2026-11-23 21:12] ingest | pg-q2-fy2026
batch 1：新增 sources/pg-q2-fy2026；建立或更新 concepts（volume/price/mix/…）與對應 entity；依 D01 決議。尚未跑 lint。

## [2026-11-23 21:12] ingest | kmb-q4-2025
batch 1：新增 sources/kmb-q4-2025；建立或更新 concepts（volume/price/mix/…）與對應 entity；依 D01 決議。尚未跑 lint。

## [2026-11-23 21:12] ingest | khc-q4-2025
batch 1：新增 sources/khc-q4-2025；建立或更新 concepts（volume/price/mix/…）與對應 entity；依 D01 決議。尚未跑 lint。

## [2026-11-23 21:12] ingest | wmt-q4-fy2026
batch 1：新增 sources/wmt-q4-fy2026；建立或更新 concepts（volume/price/mix/…）與對應 entity；依 D01 決議。尚未跑 lint。

## [2026-11-23 21:13] lint | batch1-round1
第 1 輪：引文 145/145 逐字通過；10 個 error。其中 3 個是檢查器誤判（SCHEMA 範例連結、「10-K」「批次 2」被當成數字）→ 修檢查器；其餘是真的內容問題：mix 頁某行的數字 3 只在別行的引文裡（數字漂移）、AI 解釋句夾帶沒有證據的數字。

## [2026-11-23 21:14] fix | D01-batch1
預讀時把 KMB 的 volume/mix +1.7% 寫成「北美」；對照逐字稿原話（as you saw from our results）後，source 頁改為公司整體。這是『預讀摘要 ≠ 原文』造成的錯誤，因此後續一律以引文為準。

## [2026-11-23 21:14] discuss | D02-batch2
先討論（尚未生成批次 2 頁面）：針對批次 1 檢查發現的 3 個缺口，預讀 5 份 10-K，列出要更新的頁面與 6 個疑點，見 [[discussions/D02-batch2]]。

## [2026-11-23 21:15] ingest | ko-10k-fy2025
batch 2：新增 sources/ko-10k-fy2025；更新 organic-growth / volume / price / mix / reporting-conventions / cost / retail-business-mix 與對應 entity；依 D02 決議。

## [2026-11-23 21:15] ingest | khc-10k-fy2025
batch 2：新增 sources/khc-10k-fy2025；更新 organic-growth / volume / price / mix / reporting-conventions / cost / retail-business-mix 與對應 entity；依 D02 決議。

## [2026-11-23 21:15] ingest | kmb-10k-fy2025
batch 2：新增 sources/kmb-10k-fy2025；更新 organic-growth / volume / price / mix / reporting-conventions / cost / retail-business-mix 與對應 entity；依 D02 決議。

## [2026-11-23 21:15] ingest | pg-10k-fy2025
batch 2：新增 sources/pg-10k-fy2025；更新 organic-growth / volume / price / mix / reporting-conventions / cost / retail-business-mix 與對應 entity；依 D02 決議。

## [2026-11-23 21:15] ingest | wmt-10k-fy2026
batch 2：新增 sources/wmt-10k-fy2026；更新 organic-growth / volume / price / mix / reporting-conventions / cost / retail-business-mix 與對應 entity；依 D02 決議。

## [2026-11-23 21:16] fix | cost-and-productivity
人工複查發現 KHC 的 10-K 證據被插到「容易誤會」小節（我用腳本插入段落時，把插入點設成「名詞小教室」之前，結果落在「容易誤會」底下）。lint 當時抓不到 → 新增 E-SECTION 規則；內容搬回證據小節。SCHEMA 補上規則 8–10（把檢查前移到生成前）。

## [2026-11-23 21:18] query | gap-fill
設計簡報第 8 頁（KO 案例）時用 wiki_query 查「KO CEO 底層價格 4% + 銷量 1% = 5%」：Wiki 只有零散的 4%、1%、5%，沒有 CEO 把它們相加的那句話。以 --raw 退回原始 chunk 找到 KO_Transcript_Q4_2025 chunk 20，回頭補進 sources/ko-q4-2025、concepts/timing-and-base-effects、entities/ko（Wiki 缺口 → 回到 ingest）。

## [2026-11-23 21:18] query | gap
問題：Kraft Heinz Q3 2025 organic sales
- Wiki 命中頁面：entities/khc, concepts/mix, concepts/reporting-conventions
- **Wiki 缺口**：Wiki 沒有 ingest KHC 的 Q3 2025 文件；raw 命中：KHC_10K_FY2025_SEC.pdf chunk 58；KHC_10K_FY2025_SEC.pdf chunk 217；PG_10K_FY2025_SEC.pdf chunk 121

## [2026-11-23 21:18] query | hit
問題：KO Q4 的 price/mix 為什麼只有 1%
- Wiki 命中頁面：sources/ko-q4-2025, sources/kmb-q4-2025, concepts/price

## [2026-11-23 21:28] slides | deck-round1
依 Wiki 產生 22 頁簡報。簡報檢查 0 錯誤（72 個數字、9 段引文）；渲染檢查 3 頁溢出（R-OVERFLOW：s02、s18 編號清單的粗體被拆成 grid 欄位而變成直排；s21 對照表來源 id 太長）。

## [2026-11-23 21:28] fix | deck-round2
修正編號清單結構（內文包進單一 span）與附錄 B 版面（改三欄、只列公司代號）。渲染檢查通過，但肉眼看總覽圖發現 9 頁下半部大片留白、流程圖『Wiki 缺口』標籤被虛線劃過。

## [2026-11-23 21:28] fix | deck-round3
加入依可用高度自動放大內容（上限 1.35 倍，測驗頁與附錄不放大）、SVG 標籤加底色描邊；並新增 W-SPARSE 警告，讓『版面太空』以後由程式檢查。簡報檢查與渲染檢查皆通過。

## [2026-11-23 21:30] fix | deck-round5
模擬發佈環境的外殼測試發現：手機寬度（400px）下簡報沒切到閱讀模式，舞台被縮成 0.29 倍。原因是腳本執行當下版面寬度還沒確定、之後也沒重新計算。改成 load / 下一個畫面 / ResizeObserver 都重算，手機、平板、橫放手機都進入閱讀模式。這個問題在直接開 index.html 的渲染檢查裡沒有出現，只有包上發佈外殼才重現。
