---
type: discussion
title: D02 批次 2 討論稿（先討論、後生成）— 5 份 10-K 的定義與全年數字
---
# D02 批次 2 討論稿

**狀態**：AI 提案 → 採用（學生可修改決議欄後重跑 lint）
**為什麼要有批次 2**：批次 1 的檢查發現三個缺口——(a) concepts 裡「有機成長」「mix」的定義只能靠 AI 白話整理，沒有來源；(b) KHC 的逐字稿沒有數字；(c) `retail-business-mix` 只有 1 份來源支持（lint 警告 W-SINGLE）。批次 2 用 10-K 補這三個缺口。

## 1. 預讀重點

| id | 文件 | 預讀到的重點 | 要補的頁面 |
|---|---|---|---|
| ko-10k-fy2025 | KO 10-K | **price/mix 的正式定義**；價格/組合是用「總變動 − 銷量 − 匯率 − 併購出售」**倒推出來的剩餘值**；全年表格：銷量 1%、price/mix 4%、匯率 −2%、併購出售 −1%，合計 2% | price、mix、reporting-conventions、organic-growth |
| khc-10k-fy2025 | KHC 10-K | 報法是 **Price** 與 **Volume/Mix**（mix 跟銷量綁一起）；全年有機淨銷售 −3.4%，價格 +0.7 pp、volume/mix −4.1 pp；北美漲價是為了抵銷咖啡等投入成本 | reporting-conventions、volume、price、cost-and-productivity、khc |
| kmb-10k-fy2025 | KMB 10-K | 全年有機銷售 +1.7%，主要是銷量 +2.5%，被較低的價格部分抵銷 | volume、price、kmb |
| pg-10k-fy2025 | PG 10-K | **有機銷售的定義**（排除併購出售與匯率）；有機銷量的定義；報表欄位是 volume、FX、price、mix、other | organic-growth、reporting-conventions、pg |
| wmt-10k-fy2026 | WMT 10-K | 策略之一是用「productivity 與 category/business mix」改善利潤率 | retail-business-mix（第 2 份來源）、wmt |

## 2. 擬做的更新（練習「新資料改舊頁」）
- **更新**：organic-growth、volume、price、mix、reporting-conventions、cost-and-productivity、retail-business-mix 與 5 個 entity。
- **新增**：5 個 source 頁。
- organic-growth 新增「**教學範例（虛構數字）**」：示範 營收成長 ≈ 銷量 + 價格 + 組合；並用 3 家真實數字驗證「這個加總在真實資料也成立」。

## 3. 疑點與決議

| # | 疑點 | 決議 |
|---|---|---|
| 1 | 10-K 是全年數字，法說會是單季數字，口徑與期間不同 | 簡報與頁面都標「全年」或「Q4」，不混在同一張比較表 |
| 2 | KO 的 price/mix 是「倒推的剩餘值」，這和批次 1 說的「價格 4 點、組合 −3 點」是否衝突？ | 不衝突：10-K 說明 price/mix 的算法，法說會是管理層再拆出價格與組合。兩者並列，並在 mix 頁註明 |
| 3 | 各家 mix 綁的對象不同（KO：price/mix；KHC：volume/mix；PG：獨立） | 這是本 Wiki 最重要的發現，獨立成 reporting-conventions 頁的主軸，簡報也要用一整頁講 |
| 4 | PG 10-K 的表格抽字後有許多「—」與括號負號，數字難以逐格引用 | 只引用句子（定義與文字敘述），不引用表格格子 |
| 5 | 10-K 全文很長（每份數百個 chunk），要不要全部 ingest？ | 不要。只 ingest 與主題相關的 MD&A 段落，其餘寫入「尚未 ingest」 |
| 6 | 前一批 KMB 的 +1.7% 在 D01 預讀時我誤寫成「北美」 | 已在寫 source 頁時更正為公司整體（原話 "as you saw from our results"），並在 log 記一筆 fix（見下） |

## 4. 學生決議欄
- [x] 採用上述 AI 提案
