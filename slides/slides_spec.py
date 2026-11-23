# -*- coding: utf-8 -*-
"""
簡報的「內容規格」：每一頁用哪些 Wiki 頁面、要回答學習者什麼問題。

規則（build_slides.py 會檢查）
  * wiki：這一頁的資料來自哪些 Wiki 頁面。頁面上出現的數字，必須在這些頁面的『有證據的句子』裡。
  * question：學習者會問的問題。會丟給 wiki_query 看看，檢索結果裡有沒有這一頁引用的頁面。
  * quote 區塊：英文原文，會逐字比對來源文件。
  * fiction 區塊：虛構範例，只能用 Wiki『虛構』小節裡的數字，並自動加上「虛構範例」標籤。
  * %%n_sources%% 這類佔位符由 build 時用 lint 的實際統計填入，不手打。
"""

SLIDES = [
    # ------------------------------------------------------------------ 1
    dict(id="s01", kind="title", title="看懂公司怎麼成長",
         subtitle="Volume · Price · Mix",
         lead="用五家美國消費品公司的真實財報，學會把「營收成長」拆開來看",
         meta="資料來源：LLM Wiki，%%n_sources%% 份來源、%%n_evidence%% 條逐字引文，全部通過程式比對",
         wiki=[]),
    # ------------------------------------------------------------------ 2
    dict(id="s02", kind="content", kicker="開始之前", title="學完這份簡報，你可以…",
         wiki=[],
         blocks=[
             dict(t="olist", items=[
                 "用白話說出 **Volume（銷量）、Price（價格）、Mix（組合）** 各是什麼",
                 "看懂一個成長數字，是「賣得更多」、「賣得更貴」，還是「賣的東西變了」",
                 "認出財報裡最常見的三個陷阱：**單季雜訊、各家報法不同、mix 的雙重意思**",
             ]),
             dict(t="callout", md="每一頁底部都標著這頁的資料出自 Wiki 的哪一頁。Wiki 裡的每個數字都附英文原文，並由程式逐句比對過。"),
         ]),
    # ------------------------------------------------------------------ 3
    dict(id="s03", kind="content", kicker="先問一個問題", title="營收成長 5%，是好消息嗎？",
         question="KO Q4 有機營收成長 5% 銷量只成長 1%",
         wiki=["sources/ko-q4-2025"],
         blocks=[
             dict(t="stats", items=[
                 dict(v="+5%", l="可口可樂 Q4 2025 有機營收成長", c="total"),
                 dict(v="+1%", l="同一季的銷量（單位箱數）成長", c="vol"),
             ]),
             dict(t="text", md="同樣是成長，可能是**賣得更多**，也可能只是**賣得更貴**。這份簡報教你分辨。"),
             dict(t="quote", src="ko-q4-2025", who="可口可樂財務長，2025 Q4 法說會",
                  text="we grew organic revenues 5%. Unit case growth was 1%."),
         ]),
    # ------------------------------------------------------------------ 4
    dict(id="s04", kind="content", kicker="三個基本詞", title="三個詞，拆開看成長",
         question="銷量 價格 組合 是什麼 volume price mix",
         wiki=["concepts/volume", "concepts/price", "concepts/mix"],
         blocks=[
             dict(t="cards", items=[
                 dict(c="vol", h="Volume｜銷量", p="賣出去**多少東西**（幾箱、幾件），不管賣多少錢。"),
                 dict(c="price", h="Price｜價格", p="**同一個東西**賣的價錢變了多少：漲價、降價、促銷深淺。"),
                 dict(c="mix", h="Mix｜組合", p="賣的**結構**變了：貴的賣得多還是便宜的？大包裝還是小包裝？哪個通路？"),
             ]),
             dict(t="callout", md="銷量是最誠實的需求訊號：漲價能讓營收變大，但顧客買的件數變少，代表需求其實在流失。"),
         ]),
    # ------------------------------------------------------------------ 5
    dict(id="s05", kind="content", kicker="公式", title="成長可以加起來：銷量 + 價格 + 組合",
         question="有機成長 銷量 價格 組合 加總 匯率 併購",
         wiki=["concepts/organic-growth"],
         blocks=[
             dict(t="equation", parts=[
                 dict(t="Volume", c="vol"), dict(op="+"), dict(t="Price", c="price"), dict(op="+"),
                 dict(t="Mix", c="mix"), dict(op="="), dict(t="有機成長", c="total"),
             ]),
             dict(t="text", md="再加上**匯率**與**買賣公司**的影響，才是帳面上的總營收成長。"),
             dict(t="fiction", md="假設某飲料公司：銷量 +2%、價格 +3%、組合 −1%，有機成長約 **+4%**。匯率讓營收少 2%，總營收約 **+2%**。"),
             dict(t="callout", md="同樣是 +4%，可能是「賣得多」，也可能只是「賣得貴」，健康程度不同。"),
         ]),
    # ------------------------------------------------------------------ 6
    dict(id="s06", kind="content", kicker="公式成立嗎？", title="真實數字也能加起來",
         question="KO KHC PG 全年 成長 加起來 價格 銷量 匯率",
         wiki=["concepts/organic-growth", "sources/ko-10k-fy2025", "sources/khc-10k-fy2025", "sources/pg-q2-fy2026"],
         blocks=[
             dict(t="eqrow", label="KO｜2025 全年｜10-K", parts=[
                 dict(t="銷量", v="+1", c="vol"), dict(op="+"), dict(t="price/mix", v="+4", c="price"), dict(op="+"),
                 dict(t="匯率", v="−2", c="neutral"), dict(op="+"), dict(t="併購出售", v="−1", c="neutral"),
                 dict(op="="), dict(t="營收", v="+2", c="total")]),
             dict(t="eqrow", label="KHC｜2025 全年｜10-K", parts=[
                 dict(t="價格", v="+0.7", c="price"), dict(op="+"), dict(t="volume/mix", v="−4.1", c="vol"),
                 dict(op="="), dict(t="有機淨銷售", v="−3.4", c="total")]),
             dict(t="eqrow", label="PG｜FY2026 Q2｜法說會", parts=[
                 dict(t="銷量", v="−1", c="vol"), dict(op="+"), dict(t="價格", v="+1", c="price"), dict(op="+"),
                 dict(t="組合", v="持平", c="mix"), dict(op="="), dict(t="有機銷售", v="持平", c="total")]),
             dict(t="text", md="三家公司的拆法不同（這是後面的陷阱），但都符合「各項加起來等於整體」。"),
         ]),
    # ------------------------------------------------------------------ 7
    dict(id="s07", kind="content", kicker="名詞", title="「有機成長」就是只看本業",
         question="有機銷售 organic sales 定義 排除 併購 匯率",
         wiki=["concepts/organic-growth", "sources/pg-10k-fy2025"],
         blocks=[
             dict(t="cards", items=[
                 dict(c="neutral", h="拿掉的干擾 ①", p="**匯率**：美元強弱讓海外營收換算後變大或變小。"),
                 dict(c="neutral", h="拿掉的干擾 ②", p="**買賣公司**：買進別人的營收、賣掉部門而少掉的營收。"),
             ]),
             dict(t="quote", src="pg-10k-fy2025", who="寶僑 10-K（FY2025 有機銷售 +2%）",
                  text="Organic sales, which exclude the impact of acquisitions and divestitures and foreign exchange, increased 2%."),
             dict(t="text", md="法說會上說的「成長」，多半就是有機成長：它最能反映管理層能控制的部分。"),
         ]),
    # ------------------------------------------------------------------ 8
    dict(id="s08", kind="content", kicker="案例 1｜可口可樂", title="價格 4、組合 −3，price/mix 只剩 1",
         question="KO Q4 price/mix 只有 1% 底層價格 4% 四個季度",
         wiki=["concepts/mix", "concepts/timing-and-base-effects", "sources/ko-q4-2025"],
         blocks=[
             dict(t="split", left=[
                 dict(t="waterfall", title="KO 2025 Q4：price/mix 怎麼來", steps=[
                     dict(label="漲價", v=4, c="price"),
                     dict(label="不利的組合", v=-3, c="mix"),
                     dict(label="price/mix", v=1, c="total", total=True)]),
             ], right=[
                 dict(t="text", md="CEO 的簡化看法：把組合的單季波動拿掉，Q4 就是**底層價格 4 + 銷量 1 = 5%** 的營收成長。"),
                 dict(t="quote", src="ko-q4-2025", who="可口可樂 CEO",
                      text="If you take that, what you see is 4% underlying price and 1% volume. So you see the fourth quarter in simple terms as a 5% revenue growth quarter"),
                 dict(t="callout", md="他的建議是看**四個季度**，不要只看一季。這是 KO 管理層的說法，不是通用規則。"),
             ]),
         ]),
    # ------------------------------------------------------------------ 9
    dict(id="s09", kind="content", kicker="案例 1 的延伸", title="mix 變負，不一定是壞事",
         question="mix 變差 club 通路 大包裝 單位價格 銷量增加",
         wiki=["concepts/mix", "concepts/price", "sources/ko-10k-fy2025", "sources/kmb-q4-2025"],
         blocks=[
             dict(t="split", left=[
                 dict(t="text", md="**mix 包含什麼？**（可口可樂 10-K 的定義）"),
                 dict(t="bullets", items=["品類、產品、包裝的組合", "通路與地區的組合", "再加上公司自己的訂價行動（所以才叫 price/mix）"]),
                 dict(t="quote", src="ko-10k-fy2025", who="可口可樂 10-K",
                      text="the mix of categories, products and packages sold; and the mix of channels and geographic territories where the sales occurred"),
             ], right=[
                 dict(t="text", md="**金百利克拉克的例子**"),
                 dict(t="flow", items=["顧客在 club 通路改買大包裝", "銷量增加", "平均單價下降，價格那一欄被拖累"]),
                 dict(t="quote", src="kmb-q4-2025", who="金百利克拉克管理層",
                      text="they're buying larger pack sizes at a lower price per unit. So you see more volume, but a little bit of a drag on pricing"),
             ]),
         ]),
    # ------------------------------------------------------------------ 10
    dict(id="s10", kind="content", kicker="關鍵觀念", title="price/mix 不是量出來的，是倒推出來的",
         question="price/mix 剩餘值 倒推 計算方式 總變動 扣掉",
         wiki=["concepts/mix", "sources/ko-10k-fy2025"],
         blocks=[
             dict(t="equation", parts=[
                 dict(t="price/mix", c="price"), dict(op="="), dict(t="營收總變動", c="total"), dict(op="−"),
                 dict(t="銷量", c="vol"), dict(op="−"), dict(t="匯率", c="neutral"), dict(op="−"), dict(t="併購出售", c="neutral"),
             ]),
             dict(t="eqrow", label="代回 KO 2025 全年", parts=[
                 dict(t="營收", v="+2", c="total"), dict(op="−"), dict(t="銷量", v="+1", c="vol"),
                 dict(op="−"), dict(t="匯率", v="−2", c="neutral"), dict(op="−"), dict(t="併購出售", v="−1", c="neutral"),
                 dict(op="="), dict(t="price/mix", v="+4", c="price")]),
             dict(t="quote", src="ko-10k-fy2025", who="可口可樂 10-K",
                  text="The impact of price/mix is calculated by subtracting the change in net operating revenues resulting from volume increases or decreases, fluctuations in foreign currency exchange rates, and acquisitions and divestitures from the total change in net operating revenues."),
             dict(t="callout", md="所以 price/mix 是「剩下的」：價格漲跌、產品、包裝、通路、地區的影響都混在裡面。"),
         ]),
    # ------------------------------------------------------------------ 11
    dict(id="s11", kind="content", kicker="案例 2｜寶僑", title="銷量 −3，但有 2 點是「去年太好」",
         question="PG 北美 銷量 下降 基期 囤貨 港口罷工",
         wiki=["concepts/timing-and-base-effects", "sources/pg-q2-fy2026"],
         blocks=[
             dict(t="split", left=[
                 dict(t="stackbar", title="寶僑北美銷量變化（FY2026 Q2）", total=dict(label="銷量", v=3),
                      parts=[dict(label="基期因素", v=2, hatch=True), dict(label="其他", v=None)]),
                 dict(t="text", md="北美有機銷售 **−2%**。銷量 **−3 點**，其中約 **2 點**來自基期。"),
             ], right=[
                 dict(t="text", md="**基期**＝拿來比較的去年同期。去年同期大家囤貨，今年就顯得弱。"),
                 dict(t="quote", src="pg-q2-fy2026", who="寶僑財務長",
                      text="the base period included trade and consumer pantry loading, driven by port strikes and hurricanes in early October"),
                 dict(t="callout", md="管理層事前就說這會是全年最弱的一季；Family Care 下降約 10%，主因也是基期。要看下一季是否真的回升。"),
             ]),
         ]),
    # ------------------------------------------------------------------ 12
    dict(id="s12", kind="content", kicker="陷阱 1", title="各家報法不同：mix 跟誰綁在一起？",
         question="各家報法不同 price/mix volume/mix 10-K 拆法",
         wiki=["concepts/reporting-conventions", "sources/ko-10k-fy2025", "sources/khc-10k-fy2025", "sources/pg-10k-fy2025", "sources/kmb-10k-fy2025"],
         blocks=[
             dict(t="table", head=["公司（10-K）", "怎麼拆成長", "mix 跟誰綁在一起"],
                  rows=[["KO", "銷量、price/mix、匯率、併購出售", "**價格**（Price/Mix）"],
                        ["KHC", "Price、Volume/Mix", "**銷量**（Volume/Mix）"],
                        ["PG", "volume、匯率、price、mix、other", "**單獨一欄**"],
                        ["KMB", "敘述「銷量」與「較低的價格與組合」", "敘述中與價格並列"]]),
             dict(t="callout", md="KO 全年 price/mix 是 **+4%**（含組合）；KHC 全年價格是 **+0.7** 個百分點（不含組合）。兩個數字**不能直接比大小**。"),
             dict(t="text", md="**看到 mix，先問：它跟誰綁在一起？**"),
         ]),
    # ------------------------------------------------------------------ 13
    dict(id="s13", kind="content", kicker="案例 3｜卡夫亨氏", title="漲價救不了銷量",
         question="KHC 價格 銷量 volume/mix 下滑 咖啡 漲價 投資",
         wiki=["sources/khc-10k-fy2025", "sources/khc-q4-2025", "concepts/price", "concepts/value-and-affordability"],
         blocks=[
             dict(t="split", left=[
                 dict(t="waterfall", title="KHC 2025 全年：有機淨銷售（百分點）", steps=[
                     dict(label="價格", v=0.7, c="price"),
                     dict(label="volume/mix", v=-4.1, c="vol"),
                     dict(label="有機淨銷售", v=-3.4, c="total", total=True)]),
             ], right=[
                 dict(t="text", md="漲價是為了**抵銷成本**，不代表需求強。"),
                 dict(t="quote", src="khc-10k-fy2025", who="卡夫亨氏 10-K",
                      text="Higher pricing was taken in certain categories to mitigate higher input costs, primarily in coffee."),
                 dict(t="callout", md="新任管理層的對策：增加約 600 million 美元的投資，約一半花在價格、產品、包裝；目標是「以銷量帶動」的成長。"),
             ]),
         ]),
    # ------------------------------------------------------------------ 14
    dict(id="s14", kind="content", kicker="為什麼 price 與 mix 會動", title="消費者更會比價，公司怎麼回應？",
         question="價值導向 開口價 價格階梯 好 更好 最好 降價 消費者壓力",
         wiki=["concepts/value-and-affordability", "sources/kmb-q4-2025", "sources/ko-q4-2025", "sources/khc-q4-2025", "sources/wmt-q4-fy2026"],
         blocks=[
             dict(t="cards", items=[
                 dict(c="neutral", h="KMB", p="用「好、更好、最好」價格階梯，每一階都有有競爭力的產品。"),
                 dict(c="neutral", h="KO", p="調整價格／包裝架構，聚焦「絕對價格帶」的入門款。"),
                 dict(c="neutral", h="KHC", p="把投資花在「對的開口價」、產品與包裝。"),
                 dict(c="neutral", h="WMT", p="用降價（rollbacks、EDLP）壓低食品價格，讓顧客有餘力買一般商品。"),
             ]),
             dict(t="callout", md="這些動作會**同時改變 price 與 mix**：公司可能主動讓價格或組合變差，來換取銷量。"),
         ]),
    # ------------------------------------------------------------------ 15
    dict(id="s15", kind="content", kicker="陷阱 2", title="零售商的 mix 是「事業組合」",
         question="沃爾瑪 事業組合 廣告 會員 營業利益 成長 比營收快",
         wiki=["concepts/retail-business-mix", "sources/wmt-q4-fy2026"],
         blocks=[
             dict(t="stats", items=[
                 dict(v="+4.9%", l="WMT Q4 營收（固定匯率）", c="total"),
                 dict(v="+10.5%", l="調整後營業利益", c="price"),
                 dict(v="+37%", l="全球廣告事業", c="mix"),
             ]),
             dict(t="text", md="賣商品的毛利很薄；**廣告與會員費**的毛利高很多。這類收入占比變高，獲利就會比營收長得快。廣告加會員費已占營業利益將近三分之一。"),
             dict(t="quote", src="wmt-q4-fy2026", who="沃爾瑪財務長",
                  text="we are improving eCommerce economics with increased contributions from business mix, most notably in higher-margin areas like advertising and membership fees."),
             dict(t="callout", md="沃爾瑪的 mix 是「錢從哪幾種事業賺進來」；品牌商的 mix 是「賣哪種產品、包裝、通路」。同一個字，不同意思。"),
         ]),
    # ------------------------------------------------------------------ 16
    dict(id="s16", kind="content", kicker="成長以外", title="成本壓力：關稅、原物料，以及生產力",
         question="成本 關稅 原物料 生產力 再投資 咖啡",
         wiki=["concepts/cost-and-productivity", "sources/pg-q2-fy2026", "sources/khc-10k-fy2025", "sources/ko-q4-2025"],
         blocks=[
             dict(t="cards", items=[
                 dict(c="neutral", h="寶僑｜關稅", p="預期增加約 500 million 美元的稅前成本。"),
                 dict(c="neutral", h="寶僑｜生產力", p="改善 270 個基點（= 2.7 個百分點），同時持續投資創新。"),
                 dict(c="neutral", h="可口可樂｜成本", p="管理層認為整體成本籃子的影響可控。"),
                 dict(c="neutral", h="卡夫亨氏｜原物料", p="部分品類漲價，是為了抵銷咖啡等投入成本。"),
             ]),
             dict(t="callout", md="成本上升有兩條路：**漲價**（影響 price）或**自己吸收**（壓縮利潤）。生產力改善省下的錢，會拿去投資創新，替未來的銷量鋪路。"),
         ]),
    # ------------------------------------------------------------------ 17
    dict(id="s17", kind="content", kicker="往前看", title="管理層指引：對下一年的預測區間",
         question="指引 guidance 2026 有機營收 成長 區間 市場成長",
         wiki=["concepts/guidance", "sources/ko-q4-2025", "sources/pg-q2-fy2026", "sources/wmt-q4-fy2026", "sources/kmb-q4-2025"],
         blocks=[
             dict(t="table", head=["公司", "指引", "口徑"],
                  rows=[["KO（2026）", "有機營收 +4% 到 5%，期望價與量約 50/50", "有機營收"],
                        ["PG（FY2026）", "有機銷售持平到 +4%；市場成長約 2%", "有機銷售"],
                        ["WMT（FY2027）", "銷售 +3.5% 到 4.5%；營業利益 +6% 到 8%", "固定匯率"],
                        ["KMB", "展望隱含品類成長約 2%", "品類成長"]]),
             dict(t="callout", md="指引是**預期**，不是結果。口徑不同（有機、固定匯率），數字也不能直接比大小。把公司的指引跟「市場成長」比，才看得出它預期跑贏還是跑輸。"),
         ]),
    # ------------------------------------------------------------------ 18
    dict(id="s18", kind="content", kicker="整理", title="三分鐘讀法：四個問題", wiki=[],
         blocks=[
             dict(t="olist", items=[
                 "**銷量有沒有成長？** 它是最誠實的需求訊號。",
                 "**Price 和 Mix 是誰綁誰？** 先看這家公司的拆法，再比較。",
                 "**有沒有單季雜訊？** 基期、出貨時間、多一天少一天。",
                 "**指引比市場成長高還是低？** 看管理層預期跑贏還是跑輸。",
             ]),
         ]),
    # ------------------------------------------------------------------ 19
    dict(id="s19", kind="content", kicker="小測驗", title="換你判斷",
         question="price/mix 價格 不能直接比 基期 銷量 成長",
         wiki=["concepts/mix", "concepts/reporting-conventions", "concepts/timing-and-base-effects", "sources/ko-q4-2025"],
         blocks=[
             dict(t="quiz", items=[
                 dict(q="某公司 Q4 營收成長 5%、銷量成長 1%。你最想追問什麼？",
                      opts=["為什麼成長這麼快？", "另外 4 點是價格還是組合？", "股價會不會漲？"], ans=1,
                      why="5% 扣掉銷量 1%，剩下的要拆成價格與組合。可口可樂 Q4 就是價格約 4 點、組合 −3 點。"),
                 dict(q="KO 全年 price/mix 是 +4%，KHC 全年價格是 +0.7 個百分點。誰漲價漲得比較兇？",
                      opts=["KO", "KHC", "不能直接比"], ans=2,
                      why="KO 的 +4% 包含組合；KHC 的 +0.7 只有價格，組合在 volume/mix 裡。口徑不同。"),
                 dict(q="寶僑北美銷量 −3 點，其中約 2 點來自基期。這代表什麼？",
                      opts=["需求一定變差了", "去年同期囤貨讓基期偏高", "寶僑降價了"], ans=1,
                      why="去年同期有港口罷工與颶風造成的囤貨。要看下一季是否回升，才能判斷需求。"),
             ]),
         ]),
    # ------------------------------------------------------------------ 20 附錄：方法
    dict(id="s20", kind="appendix", kicker="附錄 A｜這份簡報怎麼做出來的", title="取得 → 討論 → 生成 → 檢查 → 簡報", wiki=[],
         blocks=[dict(t="method")]),
    # ------------------------------------------------------------------ 21 附錄：對應表（自動產生）
    dict(id="s21", kind="appendix", kicker="附錄 B｜簡報 ↔ Wiki 對應", title="每一頁的資料從哪裡來", wiki=[],
         blocks=[dict(t="auto_mapping")]),
    # ------------------------------------------------------------------ 22 附錄：來源（自動產生）
    dict(id="s22", kind="appendix", kicker="附錄 C｜資料來源", title="Wiki ingest 的 %%n_sources%% 份來源", wiki=[],
         blocks=[dict(t="auto_sources")]),
]
