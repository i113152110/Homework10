# HW3 AI 評分回饋

> 本份回饋由 **Anthropic Claude Opus 4.7** 與 **OpenAI GPT-5.5** 兩個獨立模型，分別針對 Phase 1 與 Phase 2 程式碼與文件進行評分；最終加權分數為兩模型平均後，進行全班性的 Normalize，以及老師加分。

---

## 本次公布的兩個分數

本次 HW3 作業，每位同學會公布**兩個分數**，計算方式為下列三個候選值中**最高的兩個**：

| 候選 | 來源 | 計算 | 值 |
|---|---|---|---:|
| A | Max(Phase 1 兩模型評分) | max(Opus 88.0, GPT 91.0) | 91.00 |
| B | Max(Phase 2 兩模型評分) | max(Opus 85.0, GPT 86.1) | 86.12 |
| C | 最終加權分數 | 詳見下方加權計算 | 90.14 |

### 你的兩個分數

### **91.00**　／　**90.14**

_（A：Max(Phase 1 兩模型評分) = 91.00；C：最終加權分數 = 90.14）_

## 最終加權分數（候選 C）的計算

| 來源 | Phase 1 (40%) | Phase 2 (60%) | 加權平均 |
|---|---:|---:|---:|
| Anthropic Claude Opus 4.7 | 88.0 | 85.0 | 86.20 |
| OpenAI GPT-5.5 | 91.0 | 86.1 | 88.07 |
| **兩模型平均** | **89.5** | **85.6** | **87.14** |
| 老師加分 (professor_bonus) | | | +3 |
| **最終分數** | | | **90.14** |

## 計算公式

```
Phase 1 平均  = (Opus_P1 + GPT_P1) / 2
Phase 2 平均  = (Opus_P2 + GPT_P2) / 2
加權平均      = 0.4 × Phase 1 平均 + 0.6 × Phase 2 平均
Normalize 後  = 依全班分布做校準
最終分數      = min(100, Normalize 後 + 老師加分)
```

## 專案基本資料

- **github_id**：`i113152110`
- **領域**（Haiku 抽取）：`financial_reports_earnings_calls`
- **領域分類**（taxonomy）：`finance_investment`
- **Phase 1 CI**：✓ 通過
- **Phase 2 CI**：✓ 通過

## Phase 1 分項評語（40% 權重）

| 面向 | Opus 分數 | Opus 評語 | GPT 分數 | GPT 評語 |
|---|---:|---|---:|---|
| 資料收集 | 88 | data/raw 含 20 份 PDF（5 家公司 10-K + 15 份法說會 transcripts），超過高分門檻。README 詳列每份檔案、來源 vendor（SEC/FactSet/MotleyFool 等）與類型分類表，邊界明確（FY2025/FY2026）。扣分點：格式僅 PDF 單一類型，且授權欄位多為「公開頁面轉存」較模糊，缺乏明確 license 條款引用。 | 82 | data/raw 有 20 份 PDF，涵蓋 5 家公司 10-K 與 earnings call，數量達標且 README 清楚列檔案與來源；但格式僅 PDF，授權/轉存合規描述仍偏粗略。 |
| RAG 系統完整度 | 86 | data_update.py (848 行) 完整實作 PDF 抽取、metadata 推斷（company/period/vendor/doc_family）、固定 chunking、sentence-transformers embedding 與 ChromaDB 寫入。rag_query.py (921 行) 提供 auto/vector/keyword 三模式，含 BM25-like scoring、concept alias、vendor quality boost、transcript junk penalty、LiteLLM 整合與 fallback。retrieval 設計超越多數同儕，citation 機制具備。 | 93 | data_update.py 具 PDF 抽取、清理、chunk、metadata、embedding 寫入 Chroma；rag_query.py 支援 top-k、vector/keyword fallback、metadata boost、來源引用與 LiteLLM/抽取式回退，Phase 1 完整度高。 |
| 冪等性 | 92 | 明確支援 --rebuild（清 processed/manifest/chroma），預設增量更新以 SHA256 hash 比對未變動檔案跳過，並同步刪除已移除 raw 檔案對應的 processed txt、manifest 條目與 Chroma chunks，達到三方一致性。屬於本作業中冪等設計較完整者，僅缺 dry-run 等附加旗標。 | 96 | data_update.py 明確支援 --rebuild，並以 SHA256 manifest 跳過未變更檔案；README 亦說明 raw 刪除會同步 processed、manifest 與 Chroma chunks，冪等與增量更新完整。 |

## Phase 2 分項評語（60% 權重）

| 面向 | Opus 分數 | Opus 評語 | GPT 分數 | GPT 評語 |
|---|---:|---|---:|---|
| 資料收集深度 | 82 | data/raw 收錄 20 份 PDF，涵蓋 5 家公司的 10-K 與 15 份 earnings call transcripts，達到門檻並有跨 vendor（SEC/FactSet/MotleyFool/SeekingAlpha 等）多樣性。README §5 有來源表格與授權依據說明，但僅以「公開取得」帶過，缺乏明確 license 標註與每份文件 URL，略低於 high anchor 的一手來源 + 授權完整度。 | 78 | data/raw 有 20 份 PDF，剛好達 Phase 2 門檻；含 SEC 10-K 與多家 transcript vendor。README §5列清單，但授權多寫公開取得/自備，合規條款仍偏模糊。 |
| skill.md 品質 | 86 | skill.md（17377 字）九大章節齊全，Core Concepts 列 10 條且具體，Key Entities 含公司、品牌、策略、生態系對手分類詳實，Key Trends 有跨公司觀察與管理層敘事整合，Methodology 提出五軸比較框架。Example Q&A 附 source citations，知識邊界誠實標示 vendor 品質差異。整體已超越 finance_investment 的 high anchor，具備專家整理感。 | 87 | skill.md 章節齊全，§Core Concepts 有 10 項，§Key Entities 具體列公司、品牌、平台與交易對手，讀起來像財報分析指南；但缺少具體財務數字、估值方法與較完整時間軸。 |
| README 設計決策 | 88 | README §3 系統性回答 chunking（1200+200 理由）、embedding（多語 MiniLM 取捨）、vector DB（Chroma 免 docker）、retrieval（auto/vector/keyword fallback 含 BM25/metadata boost）、prompt、idempotency（SHA256 + 同步刪除 + --rebuild）、skill_builder 全域問題設計，每項皆有具體理由與取捨論述，且提供 A/B 兩條執行路徑，文件成熟度高。 | 93 | README §3完整回答 chunking、embedding、ChromaDB、retrieval、prompt、idempotency、skill_builder 全域問題，且有取捨理由；僅資料授權與部分限制可再更精確。 |
| skill_builder 品質 | 84 | skill_builder.py 定義 6 個全域問題，涵蓋 Overview/Trends/Entities/Methodology/Knowledge Gaps 多面向，並內建 FINANCIAL_THEMES、COMPANY_BRANDS、COMPANY_STRATEGIES 等領域結構化先驗，將多次查詢結果整合為 skill.md 各章節，非機械拼貼。對 transcript noise 有過濾設計，整體生成品質扎實，惟部分章節仍倚賴硬編字典補強，原創抽取深度可再加強。 | 86 | skill_builder.py 的 GLOBAL_QUESTIONS 覆蓋 Overview、Trends、Entities、Methodology、Gaps，並結合 metadata、主題詞與來源表；但部分公司品牌與策略為硬編碼，整合仍有模板化痕跡。 |

## 整體評語

### 亮點

- Comprehensive retrieval with vector + keyword fallback
- Detailed data cleaning for SEC filings and transcript vendors
- Idempotent design with file hash tracking
- Multi-language stopword support (EN + ZH)
- Clear Python 3.11.x environment documentation

### 改進建議

- Phase 2 (skill_builder.py, skill.md) not submitted
- No license/attribution metadata for source documents
- Dependency on external Hugging Face model download
- Limited to 5 companies; narrow domain scope

---

_本份評分回饋由自動化評分管線（Anthropic + OpenAI 雙模型獨立評分 → 平均 → rescale → 老師加分）產出，僅作為個人學習參考。若對評分有疑問請於課堂或 office hour 提出。_
