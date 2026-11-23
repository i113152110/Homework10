---
type: schema
title: Wiki 規則書（給維護這個 Wiki 的 LLM 看的）
---
# SCHEMA — 這個 Wiki 怎麼運作

**主題**：看懂消費品公司的成長 —— Volume（銷量）/ Price（價格）/ Mix（組合）。
**讀者**：完全沒學過財報的人（教學簡報的目標讀者）。
**資料邊界**：HW3 的 20 份美國消費必需品財報 / 法說會中，被明確 ingest 的那幾份（見 `index.md`）。**沒有 ingest 的，就不能寫進 Wiki。**

## 三層結構（參考 Karpathy 的 LLM Wiki 模式）
1. `data/raw/` + `data/processed/`：原始資料，唯讀。processed 是 HW3 `data_update.py` 抽出來的文字。
2. `wiki/`：LLM 擁有並維護的 markdown 頁面（sources / concepts / entities），頁面之間用 `[[路徑]]` 互連。
3. 這份 `SCHEMA.md`：規則。

## 頁面類型
| 資料夾 | 內容 | 必備 |
|---|---|---|
| `sources/<id>.md` | 一份來源一頁：這份文件在講什麼、可引用的重點 | frontmatter（id,file,raw,sha256…）、≥3 條證據 |
| `concepts/<slug>.md` | 一個概念一頁：白話定義＋各家怎麼說（跨來源綜合） | 盡量 ≥2 份來源支持 |
| `entities/<ticker>.md` | 一家公司一頁：它怎麼描述自己的成長 | ≥1 條證據 |
| `discussions/` | 「先討論」的紀錄：每次 ingest 前的討論稿與決議 | — |
| `index.md` / `log.md` | 目錄 / 操作紀錄 | 每頁都要在 index；每份來源都要在 log |

## 寫作規則（lint 會強制檢查）
1. **一條主張 = 一行**。主張用繁體中文寫。
2. 主張後面接證據：`{{來源id: "英文原文逐字引文"}}`。長段落用 `...` 把前後兩段接起來。引文至少 20 字元。
3. 主張裡出現的數字，必須出現在**同一行**的引文裡（`one`、`a point` 這類英文寫法會被換算）。
4. 推算出來的數字要寫 `<!--calc: 4-3=1-->`，lint 會驗算，並確認運算元在引文中。
5. 教學用的假想數字只能放在標題含「虛構」的小節，簡報上也必須標成「虛構範例」。
6. 來源之間有出入（例如各公司對 mix 的定義不同）要明講，不要硬合併。
7. 不確定就寫「來源沒有說」，不要補。
8. **解釋句不要夾帶數字**：白話解釋、容易誤會這類 AI 自己寫的句子盡量不出現阿拉伯數字；要舉例就放進標題含「虛構」的小節，要講名詞定義就放進標題含「通則」的小節。（第 1 輪檢查有 4 條是這類錯誤，所以把規則提前到寫之前。）
9. **證據行放在「各家怎麼說／證據」小節**，不要放進「容易誤會」。
10. 每寫完一份來源，先跑 `python wiki_pipeline.py check`，再寫下一份（不要全部寫完才檢查）。

## 三個動作
- **ingest**：讀一份來源 →（先討論：寫 `discussions/` 討論稿，列重點、擬建/更新的頁面、疑點、決議）→ 才生成頁面 → 更新 index、log → 跑 lint。
- **query**：先查 Wiki（`wiki_query.py`）；Wiki 查不到才回頭查 raw chunk（HW3 `rag_query.py` 的 keyword 模式），並在 log 記一筆「Wiki 缺口」。
- **lint**：`python wiki_lint.py`。沒有 error 才算完成。
