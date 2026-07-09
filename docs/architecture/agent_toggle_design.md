# Thiết kế Agent Toggle — nhóm Analyst — Phase 3.1 (thiết kế trên giấy, không sửa code)

> Phạm vi: **chỉ 4 Analyst** (Market, Sentiment, News, Fundamentals). Không thiết kế toggle cho Researcher / Risk Team / Portfolio Manager — các node đó bị khoá cứng trong `setup.py` và bị đẩy sang Phase 9 theo `ROADMAP.md`.
>
> Nguồn đối chiếu (đọc, không sửa): [`graph_current.md`](graph_current.md) (Phase 2.1), [`agents_inventory.md`](agents_inventory.md) (Phase 2.2), [`config_reference.md`](config_reference.md) (Phase 2.3), và đọc trực tiếp `tradingagents/graph/setup.py`, `analyst_execution.py`, `propagation.py`, `trading_graph.py`, `tradingagents/agents/researchers/bull_researcher.py`.

---

## 1. Phát hiện nền tảng: cơ chế lọc analyst đã tồn tại sẵn ở tầng build graph

Trước khi thiết kế cờ config, cần ghi nhận một sự thật quan trọng đọc được từ code hiện tại:

- `GraphSetup.setup_graph(selected_analysts=(...))` (`setup.py`) và `build_analyst_execution_plan(selected_analysts)` (`analyst_execution.py`) **đã hỗ trợ sẵn** việc build graph với **bất kỳ tập con nào** của 4 analyst, theo đúng thứ tự truyền vào — đây không phải tính năng cần viết mới ở Phase 3.
- `build_analyst_execution_plan` đã tự raise `ValueError("at least one analyst must be selected")` nếu tập rỗng — đây chính là cơ chế xử lý "cả 4 tắt" mà Bước 3.1 yêu cầu thiết kế, **đã có sẵn**, không cần code mới.
- Cái duy nhất **chưa tồn tại**: không có đường nối từ **config** (`default_config.py` / env var) tới tham số `selected_analysts`. Hiện `selected_analysts` chỉ đến từ tham số constructor `TradingAgentsGraph(selected_analysts=...)`, do CLI truyền vào thủ công (`cli/main.py`) sau khi hỏi người dùng chọn analyst tương tác — không đọc config.

→ Kết luận thiết kế: Phase 3 **không cần đụng `setup.py` hay `analyst_execution.py`**. Việc cần làm chỉ là: (a) thêm cờ vào config, (b) tại **đúng 1 điểm** trong `trading_graph.py`, lọc `selected_analysts` theo cờ config trước khi gọi `self.graph_setup.setup_graph(...)`.

---

## 2. Cờ config: 4 boolean độc lập, mỗi analyst 1 cờ

| Config key (mới, thêm vào `default_config.py`) | Default | Wire key tương ứng (`ANALYST_NODE_SPECS`) | Env var override (theo cơ chế `_ENV_OVERRIDES` có sẵn) |
|---|---|---|---|
| `enable_market_analyst` | `True` | `market` | `TRADINGAGENTS_ENABLE_MARKET_ANALYST` |
| `enable_sentiment_analyst` | `True` | `social` (tên wire key giữ nguyên để tương thích ngược, tên config key dùng "sentiment" khớp label hiển thị hiện tại "Sentiment Analyst") | `TRADINGAGENTS_ENABLE_SENTIMENT_ANALYST` |
| `enable_news_analyst` | `True` | `news` | `TRADINGAGENTS_ENABLE_NEWS_ANALYST` |
| `enable_fundamentals_analyst` | `True` | `fundamentals` | `TRADINGAGENTS_ENABLE_FUNDAMENTALS_ANALYST` |

Lý do chọn **4 key boolean phẳng** thay vì 1 dict `{"market": True, ...}`:
- Khớp đúng nghĩa đen roadmap: "Mỗi analyst có 1 cờ `true/false` trong config".
- Tận dụng được cơ chế `_ENV_OVERRIDES` sẵn có (`config_reference.md` mục 1) — cơ chế này ép kiểu theo type của default hiện tại (`bool`/`int`/`float`/`str`), **không hỗ trợ dict lồng nhau**. Dùng key phẳng nghĩa là mỗi analyst tắt/bật độc lập được qua 1 biến môi trường, đúng pattern đã dùng để test `TRADINGAGENTS_MAX_DEBATE_ROUNDS` ở Phase 2.3 — cần thiết cho Bước 3.4 (test tổ hợp bật/tắt) chạy lặp lại được mà không sửa code mỗi lần.
- Mặc định `True` cho cả 4 → hành vi hiện tại (baseline Phase 1.2, 4 analyst mặc định bật) **không đổi** khi chưa ai set cờ nào.

---

## 3. Nơi áp dụng cờ — đúng 1 file (Quy tắc 5)

**File duy nhất bị sửa ở Bước 3.2/3.3: `tradingagents/graph/trading_graph.py`.**

Không sửa `setup.py` (đã đủ tổng quát — nhận `selected_analysts` là tập con bất kỳ). Không sửa `analyst_execution.py` (đã có xử lý tập rỗng). Không sửa `default_config.py` theo nghĩa "vi phạm Quy tắc 5" — thêm key mới vào đó là bình thường (đã ghi rõ trong `config_reference.md` mục 4: Quy tắc 5 chỉ áp dụng cho *graph build*, không áp dụng cho việc khai báo config key).

Vị trí sửa cụ thể: trong `TradingAgentsGraph.__init__`, ngay trước dòng hiện tại

```python
self.selected_analysts = tuple(selected_analysts)
self.workflow = self.graph_setup.setup_graph(selected_analysts)
```

chèn một bước lọc theo config (minh hoạ ý tưởng cho Bước 3.2, **không phải code final**):

```python
_ANALYST_CONFIG_FLAG = {
    "market": "enable_market_analyst",
    "social": "enable_sentiment_analyst",
    "news": "enable_news_analyst",
    "fundamentals": "enable_fundamentals_analyst",
}

filtered_analysts = tuple(
    key for key in selected_analysts
    if self.config.get(_ANALYST_CONFIG_FLAG[key], True)
)

self.selected_analysts = filtered_analysts          # dùng bản đã lọc, không phải bản gốc
self.workflow = self.graph_setup.setup_graph(filtered_analysts)
```

Điểm quan trọng cần giữ khi cài đặt thật (Bước 3.2):
- **`self.selected_analysts` phải là tuple đã lọc**, không phải tham số gốc — vì nó được dùng trong `_run_signature()` (dòng ~356) để tạo checkpoint thread ID (`"analysts=" + ",".join(self.selected_analysts)`). Nếu gán sai (giữ bản gốc chưa lọc), đổi cờ config sẽ **không invalidate checkpoint cũ** → graph có thể resume nhầm từ trạng thái được build với tập analyst khác (vi phạm chú thích `#1089` sẵn có trong code).
- Tập lọc là **giao (intersection)** giữa `selected_analysts` truyền vào constructor (mặc định cả 4, hoặc CLI chọn tay) và cờ config — không thay thế hoàn toàn tham số constructor. Điều này giữ nguyên tính năng CLI chọn analyst tương tác đã có, đồng thời cho phép config làm lớp tắt/bật toàn cục (chủ yếu dùng khi gọi `TradingAgentsGraph(config=config)` theo kiểu lập trình, giống cách Phase 2.3 test `max_debate_rounds`).
- Đây là **1 khối logic duy nhất** — không rải điều kiện `if enabled` vào bất kỳ file `agents/analysts/*.py` nào (đúng Quy tắc 5).

---

## 4. Analyst bị tắt → state field nào thiếu, node nào đọc, xử lý ra sao

### 4.1 Sự thật nền: field report **không bao giờ bị thiếu key**, chỉ **rỗng**

`Propagator.create_initial_state()` (`propagation.py:65-68`) luôn khởi tạo cả 4 field này thành chuỗi rỗng `""`, **không phụ thuộc `selected_analysts`**:

```python
"market_report": "",
"fundamentals_report": "",
"sentiment_report": "",
"news_report": "",
```

→ Khi 1 analyst bị lọc khỏi `selected_analysts` (Bước 3.2), node tương ứng đơn giản **không xuất hiện trong graph nữa** — không ai ghi đè field đó — nên field giữ nguyên giá trị khởi tạo `""` suốt vòng đời state. **Không có `KeyError` xảy ra ở bất kỳ node nào** vì mọi node đọc field bằng `state["xxx_report"]` (indexing trực tiếp, xem `bull_researcher.py:14-17`) và key luôn tồn tại trong dict — chỉ giá trị là chuỗi rỗng thay vì có nội dung.

### 4.2 Bảng ánh xạ: analyst tắt → field rỗng → node đọc → hành vi

| Analyst tắt (config `False`) | State field giữ nguyên `""` | Node đọc trực tiếp field này (5 node giống nhau cho cả 4 analyst — xem `agents_inventory.md` mục 1 & 3) | Xử lý khi rỗng (quyết định Bước 3.1) |
|---|---|---|---|
| Market Analyst | `market_report` | Bull Researcher, Bear Researcher, Aggressive/Conservative/Neutral Analyst | **Bỏ qua — giữ nguyên chuỗi rỗng, không sửa prompt.** Dòng `Market research report: {market_research_report}` trong 5 prompt trở thành `Market research report: ` (rỗng sau dấu `:`). |
| Sentiment Analyst | `sentiment_report` | (giống trên) | Bỏ qua — `Social media sentiment report: ` rỗng. |
| News Analyst | `news_report` | (giống trên) | Bỏ qua — `Latest world affairs news: ` rỗng. |
| Fundamentals Analyst | `fundamentals_report` | (giống trên) | Bỏ qua — `{fundamentals_label}: ` rỗng. Lưu ý: `fundamentals_label` hiện chỉ đổi theo `asset_type` (`"Company fundamentals report"` vs `"Asset fundamentals report (may be unavailable for crypto)"`), **không** đổi theo trạng thái bật/tắt — xem mục 4.4. |

**Quyết định 3.1-A — "bỏ qua", không điền `N/A`:** Phase 3 (Bước 3.2/3.3) **không sửa bất kỳ file nào trong `agents/researchers/`, `agents/risk_mgmt/`** để thêm nhánh rẽ "nếu report rỗng thì ghi N/A". Lý do:
1. **Quy tắc 5** cấm rải điều kiện bật/tắt vào từng agent — nếu thêm logic "phát hiện report rỗng → đổi label" vào cả 5 node × 4 report, đó chính là kiểu rải điều kiện mà Quy tắc 5 muốn tránh, dù bản chất không phải cờ `enabled` mà là kiểm tra giá trị rỗng.
2. Chuỗi rỗng sau dấu `:` đã là tín hiệu đủ rõ cho LLM (model suy luận vẫn hiểu "không có nội dung" từ 1 dòng trống, so với các dòng khác có nội dung) — không có bằng chứng cần `N/A` tường minh mới hoạt động đúng ở MVP.
3. Giữ phạm vi Bước 3.2/3.3 nhỏ nhất có thể (đúng 1 file `trading_graph.py`), tránh sửa 5 file × 4 report = tăng bề mặt lỗi không cần thiết cho MVP.

→ Đây là điểm tự duyệt trực tiếp trả lời câu hỏi mẫu của roadmap:

> **"Tắt Sentiment Analyst thì Researcher đọc gì?"**
> Bull/Bear Researcher vẫn đọc `state["sentiment_report"]` như bình thường (không có nhánh rẽ nào bỏ qua dòng này) — nhận về chuỗi rỗng `""` (giá trị khởi tạo từ `propagation.py`, không ai ghi đè vì Sentiment Analyst không chạy). Dòng prompt tương ứng hiển thị `Social media sentiment report: ` (rỗng sau dấu hai chấm). Debate vẫn chạy bình thường dựa trên 3 report còn lại + lịch sử debate — không crash, không lỗi, không có xử lý đặc biệt nào được thêm vào `bull_researcher.py`/`bear_researcher.py`.

### 4.3 Ghi chú theo dõi chất lượng (không phải việc phải làm ở Phase 3)

Nếu sau này (ngoài phạm vi MVP) thấy chất lượng debate giảm rõ rệt khi tắt nhiều analyst vì prompt có nhiều dòng rỗng gây nhiễu, hướng cải thiện khả dĩ là thêm 1 hàm dùng chung trong `agents/utils/agent_utils.py` (nơi đã có `get_instrument_context_from_state`, `get_language_instruction`) để format lại 4 dòng report — vẫn là **1 điểm sửa duy nhất được tái sử dụng bởi 5 node**, không phải rải logic riêng lẻ. Ghi nhận ý tưởng này để không quên, **không thực hiện ở Phase 3**.

### 4.4 Khác biệt cần lưu ý: `fundamentals_label` theo `asset_type`, không theo cờ toggle

`bull_researcher.py:21-25` (và lặp lại y hệt ở `bear_researcher.py` + 3 file risk debator) đã có sẵn:

```python
fundamentals_label = (
    "Company fundamentals report"
    if asset_type == "stock"
    else "Asset fundamentals report (may be unavailable for crypto)"
)
```

Đây là nhánh rẽ theo **`asset_type`** (stock vs crypto), **không liên quan** đến việc Fundamentals Analyst có bị tắt qua config hay không — 2 khái niệm độc lập, không trộn lẫn. Khi tắt Fundamentals Analyst qua config trên 1 ticker stock, label vẫn là `"Company fundamentals report"` (vì `asset_type == "stock"` không đổi), chỉ nội dung sau nó rỗng. Đây chính là dữ liệu quan sát được ghi trong `agents_inventory.md` mục 3 — nhắc lại ở đây để tránh nhầm lẫn khi cài đặt Bước 3.2.

---

## 5. Hành vi biên: tắt cả 4 analyst

**Đã có sẵn cơ chế, không cần code mới.** Sau bước lọc ở mục 3, nếu cả 4 cờ config đều `False` (hoặc `selected_analysts` truyền vào rỗng), `filtered_analysts` là tuple rỗng `()`. Gọi `self.graph_setup.setup_graph(())` → `build_analyst_execution_plan(())` (`analyst_execution.py:66-67`) raise ngay:

```python
raise ValueError("at least one analyst must be selected")
```

Đặc điểm quan trọng của lỗi này (khớp yêu cầu roadmap "báo lỗi rõ ràng, không chạy với input rỗng"):
- Raise tại **thời điểm khởi tạo `TradingAgentsGraph()`** (trong `__init__`, trước khi `propagate()` từng được gọi) — **fail-fast trước khi tốn bất kỳ lệnh gọi LLM/API nào**, không lãng phí chi phí.
- Là `ValueError` với message tiếng Anh rõ ràng, không phải crash im lặng hay stack trace khó hiểu từ LangGraph.

**Khuyến nghị nhỏ cho Bước 3.2 (không bắt buộc, chỉ ghi nhận):** có thể cân nhắc bọc lại message tại đúng điểm lọc trong `trading_graph.py` (mục 3) để liệt kê tên 4 config key liên quan, ví dụ `"All analysts disabled by config — enable at least one of enable_market_analyst / enable_sentiment_analyst / enable_news_analyst / enable_fundamentals_analyst"`, giúp người debug không cần lần theo `analyst_execution.py`. Đây vẫn nằm trong cùng 1 file (`trading_graph.py`) nên không vi phạm Quy tắc 5. Quyết định cuối cùng (giữ message gốc hay bọc lại) để Bước 3.4 (test tổ hợp, gồm case tắt cả 4) chốt dựa trên việc message gốc có đủ rõ khi test thật hay không.

---

## 6. Việc KHÔNG làm ở Bước 3.1 (nhắc phạm vi, tránh lấn Bước 3.2/3.3/3.4)

- Không sửa `default_config.py`, `trading_graph.py`, hay bất kỳ file `.py` nào — Bước 3.1 chỉ là thiết kế trên giấy.
- Không cài cờ cho analyst đầu tiên (Bước 3.2) hay 3 analyst còn lại (Bước 3.3).
- Không chạy test tổ hợp bật/tắt (Bước 3.4).
- Không thiết kế/động tới toggle cho Bull/Bear Researcher, Research Manager, Trader, Aggressive/Conservative/Neutral Analyst, Portfolio Manager — các node này khoá cứng trong `setup.py`, thuộc Phase 9 (Post-MVP) theo `ROADMAP.md`.

---

## 7. Tự duyệt (theo yêu cầu "Cách kiểm tra" của Bước 3.1)

- [x] Mỗi trong 4 analyst có 1 cờ `true/false` riêng trong config (mục 2).
- [x] Liệt kê đủ 4 state field bị "đóng băng ở giá trị rỗng" khi analyst tương ứng tắt, và node đọc chúng (mục 4.2).
- [x] Trả lời được câu hỏi mẫu "Tắt Sentiment Analyst thì Researcher đọc gì?" cụ thể, không mơ hồ (mục 4.2).
- [x] Hành vi biên "tắt cả 4" có lỗi rõ ràng, fail-fast, không chạy input rỗng (mục 5).
- [x] Nhắc lại và tuân thủ Quy tắc 5: đúng 1 file (`trading_graph.py`) chứa logic bật/tắt; không rải `if enabled` vào agent (mục 3, mục 4.2 — Quyết định 3.1-A).
