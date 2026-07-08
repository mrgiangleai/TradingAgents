# ROADMAP.md — TradingAgents Custom MVP

> **Trạng thái: 🔒 KHÓA (LOCKED)**
> Phiên bản: 1.0 — Ngày khóa: 2026-07-09
> Mọi thay đổi roadmap sau ngày khóa phải được ghi vào `CHANGELOG_CUSTOM.md` kèm lý do.

---

## Mục tiêu dự án

- Fork/clone repo [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) làm nền.
- Tận dụng tối đa hệ thống có sẵn (agent pattern, config, LLM clients, decision log, reflection).
- **Không auto-trade. Chỉ tạo advisory report.**
- Tích hợp KeyVolume và Liquidity Sweep bằng **file CSV/JSON tĩnh** export từ Backtest-Trading-Lab. Chưa dùng API ở giai đoạn MVP.
- Mỗi bước làm trong **1 session Claude riêng**, kết thúc bằng **test + commit**.

---

## ⛔ QUY TẮC CỨNG (bất biến trong toàn bộ MVP)

### Quy tắc 1 — Memory test phải tách riêng
- Mọi lần chạy test/demo phải set `TRADINGAGENTS_MEMORY_LOG_PATH` trỏ tới file memory test riêng (VD: `~/.tradingagents/memory/test_memory.md`).
- Memory "thật" (`prod_memory.md`) chỉ nhận kết quả từ các lần chạy chính thức.
- Có hiệu lực **ngay từ Bước 1.2** (lần demo đầu tiên).
- Mỗi session ghi vào `SESSION_LOG.md` đang dùng memory path nào.

### Quy tắc 2 — Không pull upstream trong MVP
- Đóng băng repo gốc tại **1 commit cụ thể**, ghi hash vào `UPSTREAM.md` ngay tại Bước 1.1.
- Tạo git tag `v0-baseline` tại commit đó.
- Không pull/merge upstream trong toàn bộ MVP. Cập nhật từ upstream chỉ xem xét sau MVP, qua 1 phase riêng.

### Quy tắc 3 — Advisory only
- Mọi output, kể cả Final Advisor, chỉ là khuyến nghị. Không có phase nào tự động đặt lệnh.

### Quy tắc 4 — Quy ước dữ liệu tĩnh & hành vi khi thiếu file
- Đường dẫn file dữ liệu:
  - `data/keyvolume/{SYMBOL}_{YYYY-MM-DD}.csv` — VD: `data/keyvolume/BTCUSDT_2026-07-09.csv`
  - `data/liquidity/{SYMBOL}_{YYYY-MM-DD}.csv` — VD: `data/liquidity/BTCUSDT_2026-07-09.csv`
- **Nếu thiếu file dữ liệu:**
  - Agent phải trả `No data available`.
  - **Không được đoán / bịa tín hiệu.**
  - Pipeline vẫn chạy tiếp nếu có thể (agent khác không bị ảnh hưởng).

### Quy tắc 5 — Toggle chỉ sửa 1 file duy nhất
- Mọi logic bật/tắt agent chỉ nằm ở nơi build graph. Không rải điều kiện `if enabled` vào trong từng agent.

### Quy tắc 6 — Chống lookahead bias
- Tín hiệu tại ngày D chỉ được dùng dữ liệu ≤ ngày D. Áp dụng cho mọi test và backtest (Phase 8).

---

## Phase 0 — Khởi tạo file quản lý dự án (không code)

### Bước 0.1: Tạo bộ file quản lý dự án
- **Mục tiêu:** Có đủ tài liệu nền trước khi đụng code.
- **Việc cần làm:** Tạo các file sau:
  - `PRODUCT_SCOPE.md` — chỉ advisory report, không auto-trade, không kết nối sàn. Có mục "Quy tắc bất biến" chép lại Quy tắc 1–6 ở trên. Có mục "Out of scope".
  - `ROADMAP.md` — chính là file này, đánh dấu 🔒 LOCKED.
  - `UPSTREAM.md` — khung sẵn 4 mục: URL repo gốc / commit hash đóng băng (điền ở Bước 1.1) / quy tắc không pull / lý do.
  - `CHANGELOG_CUSTOM.md` — trống, ghi mọi thay đổi custom. ADR (quyết định kiến trúc) ghi ở cuối file này.
  - `TEST_PLAN.md` — có sẵn mục "Setup trước mọi test": bắt buộc set `TRADINGAGENTS_MEMORY_LOG_PATH` sang memory test.
  - `SESSION_LOG.md` — mỗi session ghi 3 dòng: làm gì / kết quả / việc dở dang + memory path đang dùng. Đây là bộ nhớ nối các session Claude.
- **Cách kiểm tra:** Mở từng file, đọc lại thấy đúng ý định.
- **Điều kiện hoàn thành:** Tất cả file tồn tại. Commit: `chore: init project docs`.

---

## Phase 1 — Setup repo gốc và chạy demo

### Bước 1.1: Cài đặt môi trường + đóng băng upstream
- **Mục tiêu:** Repo gốc chạy được, có điểm neo an toàn.
- **Việc cần làm:**
  - Clone repo, tạo virtualenv, cài đặt, tạo `.env` với 1 API key LLM (model rẻ nhất để test).
  - Ghi commit hash hiện tại vào `UPSTREAM.md`.
  - Tạo git tag `v0-baseline`.
- **Cách kiểm tra:** CLI `tradingagents` khởi động không lỗi; `git tag` liệt kê `v0-baseline`.
- **Điều kiện hoàn thành:** CLI hiện màn hình chọn ticker/ngày. `UPSTREAM.md` có hash. Commit: `chore: setup environment + freeze upstream` (chỉ commit `.env.example`, không commit key thật).

### Bước 1.2: Chạy demo 1 lần, ghi lại baseline
- **Mục tiêu:** Thấy pipeline hoạt động, biết chi phí thực tế, kiểm chứng cách ly memory.
- **Việc cần làm:**
  - **Set `TRADINGAGENTS_MEMORY_LOG_PATH` sang `test_memory.md` TRƯỚC khi chạy** (Quy tắc 1).
  - Chạy 1 ticker mẫu, quan sát log từng agent.
- **Cách kiểm tra:**
  - Có output quyết định cuối; file `test_memory.md` có entry mới.
  - Mở file memory thật → xác nhận **KHÔNG** có entry mới.
- **Điều kiện hoàn thành:** Ghi baseline (thời gian chạy, số API call, chi phí ước tính) vào `TEST_PLAN.md`. Commit: `docs: record baseline demo run`.

---

## Phase 2 — Audit kiến trúc (chỉ đọc, ghi chú — không sửa code)

### Bước 2.1: Ghi lại sơ đồ luồng agent thật
- **Mục tiêu:** Biết chính xác thứ tự agent chạy và cách node nối nhau trong LangGraph.
- **Việc cần làm:** Đọc log Bước 1.2, đối chiếu thư mục `graph/`, vẽ sơ đồ agent nào → agent nào.
- **Cách kiểm tra:** Sơ đồ khớp log thật.
- **Điều kiện hoàn thành:** File `docs/architecture/graph_current.md`. Commit: `docs: audit agent graph`.

### Bước 2.2: Danh sách agent + input/output + mức phụ thuộc
- **Mục tiêu:** Biết mỗi agent nhận gì, trả gì, và output của nó được node nào phía sau tham chiếu đích danh.
- **Việc cần làm:** Đọc `agents/`, lập bảng: Tên agent | Input | Output | Dữ liệu dùng | Node nào đọc output này. Cột cuối quyết định analyst nào "dễ toggle nhất" cho Bước 3.2.
- **Cách kiểm tra:** Bảng khớp log Bước 1.2.
- **Điều kiện hoàn thành:** File `docs/architecture/agents_inventory.md`. Commit: `docs: audit agents inventory`.

### Bước 2.3: Tham chiếu config
- **Mục tiêu:** Hiểu các key trong `default_config.py`, biết đổi hành vi qua config không sửa code lõi.
- **Việc cần làm:** Đọc `default_config.py`, ghi chú từng key + tác dụng. Thử đổi 1 key (VD số vòng debate), chạy lại với memory test.
- **Cách kiểm tra:** Hành vi đổi theo config.
- **Điều kiện hoàn thành:** File `docs/architecture/config_reference.md`. Commit: `docs: audit config reference`.

---

## Phase 3 — Toggle agent bằng config (CHỈ nhóm Analyst)

> **Phạm vi MVP:** chỉ toggle 4 Analyst (Fundamentals, Sentiment, News, Technical).
> Toggle Researcher / Risk Team / Portfolio Manager → **Phase 9 (Post-MVP)**.

### Bước 3.1: Thiết kế trên giấy
- **Mục tiêu:** Quyết định cách tắt analyst không làm hỏng pipeline.
- **Việc cần làm:** Viết `docs/architecture/agent_toggle_design.md`, bắt buộc gồm:
  - Mỗi analyst có 1 cờ `true/false` trong config.
  - **Liệt kê state field nào của graph bị thiếu khi mỗi analyst bị tắt, và node phía sau xử lý field thiếu ra sao** (bỏ qua? điền "N/A"?). Đây là nơi 80% lỗi toggle phát sinh.
  - Hành vi biên: nếu cả 4 analyst đều tắt → pipeline báo lỗi rõ ràng, không chạy với input rỗng.
  - Nhắc lại Quy tắc 5: chỉ sửa 1 file nơi build graph.
- **Cách kiểm tra:** Đọc lại, trả lời được: "Tắt Sentiment Analyst thì Researcher đọc gì?"
- **Điều kiện hoàn thành:** File thiết kế tồn tại, tự duyệt. Commit: `docs: design analyst toggle`.

### Bước 3.2: Toggle 1 analyst (đường dễ nhất)
- **Mục tiêu:** Kiểm chứng cơ chế trên analyst ít bị tham chiếu đích danh nhất (chọn từ bảng 2.2).
- **Việc cần làm:** Thêm cờ config, sửa đúng chỗ build graph để bỏ qua analyst khi cờ = false.
- **Cách kiểm tra:** Chạy 2 lần (bật/tắt) với memory test, so sánh output, không crash.
- **Điều kiện hoàn thành:** Ghi kết quả vào `TEST_PLAN.md`. Commit: `feat: add toggle for [tên analyst]`.

### Bước 3.3: Toggle 3 analyst còn lại
- **Mục tiêu:** Cả 4 analyst đều toggle được.
- **Việc cần làm:** Lặp pattern Bước 3.2 cho từng analyst — **mỗi analyst 1 commit riêng** trong cùng session (pattern giống hệt nên gộp session được, commit tách để revert từng cái).
- **Cách kiểm tra:** Tắt từng analyst riêng lẻ, không lỗi.
- **Điều kiện hoàn thành:** 3 commit: `feat: add toggle for [tên]` × 3. Bảng `TEST_PLAN.md` đánh ✅ đủ 4.

### Bước 3.4: Test tổ hợp
- **Mục tiêu:** Cơ chế toggle ổn định với nhiều analyst tắt cùng lúc.
- **Việc cần làm:** Test: tắt 2, tắt 3, tắt cả 4 (kỳ vọng: báo lỗi rõ ràng theo thiết kế 3.1).
- **Cách kiểm tra:** Không có crash bất ngờ; trường hợp cả 4 tắt ra thông báo lỗi dễ hiểu.
- **Điều kiện hoàn thành:** Kết quả tổ hợp ghi vào `TEST_PLAN.md`. Commit: `test: analyst toggle combinations`.

---

## Phase 4 — Chuẩn bị dữ liệu CSV/JSON tĩnh

### Bước 4.1: Đặc tả format + quy ước mapping
- **Mục tiêu:** Định nghĩa dứt khoát cấu trúc dữ liệu và cách pipeline tìm file theo (ticker, date).
- **Việc cần làm:** Lấy file mẫu thật từ Backtest-Trading-Lab, viết `docs/data/keyvolume_data_format.md` gồm:
  - Tên cột, kiểu dữ liệu, ví dụ dòng dữ liệu thật (ẩn thông tin nhạy cảm nếu có).
  - Quy ước đặt tên file: `data/keyvolume/{SYMBOL}_{YYYY-MM-DD}.csv` (Quy tắc 4).
  - Hành vi khi thiếu file: agent trả `No data available`, không đoán, pipeline chạy tiếp.
  - Ghi rõ timezone và format ngày của dữ liệu, đối chiếu với format ngày pipeline gốc dùng.
- **Cách kiểm tra:** Mở file mẫu, đối chiếu từng cột với ghi chú.
- **Điều kiện hoàn thành:** File spec tồn tại, có ví dụ thật. Commit: `docs: document keyvolume data format + file mapping`.

### Bước 4.2: Tạo thư mục dữ liệu trong repo
- **Mục tiêu:** Nơi cố định để pipeline đọc file.
- **Việc cần làm:** Tạo `data/keyvolume/` và `data/liquidity/`. Thêm vào `.gitignore` nếu dữ liệu nhạy cảm; giữ mỗi thư mục ít nhất 1 file mẫu nhỏ đặt tên đúng quy ước để test.
- **Cách kiểm tra:** File mẫu tồn tại, tên đúng format `{SYMBOL}_{YYYY-MM-DD}.csv`.
- **Điều kiện hoàn thành:** Commit: `chore: add sample data folders`.

### Bước 4.3: Viết loader đơn giản
- **Mục tiêu:** Đọc CSV/JSON thành dữ liệu Python, độc lập với hệ thống.
- **Việc cần làm:** Viết hàm `load_keyvolume_data(symbol, date)`:
  - Tự ghép đường dẫn theo quy ước Quy tắc 4.
  - File không tồn tại → trả về giá trị đặc biệt (None hoặc marker `No data available`), **không raise crash pipeline**.
  - Kiểm tra khớp ngày: ngày trong dữ liệu phải khớp ngày trong tên file (bắt lỗi timezone/format lệch).
- **Cách kiểm tra:** Chạy hàm với: (a) file mẫu tồn tại → dữ liệu đúng; (b) symbol/date không có file → trả `No data available`, không crash.
- **Điều kiện hoàn thành:** Cả 2 trường hợp pass, ghi vào `TEST_PLAN.md`. Commit: `feat: add keyvolume data loader`.

---

## Phase 5 — KeyVolume Agent (dữ liệu tĩnh)

### Bước 5.1: Thiết kế agent
- **Mục tiêu:** Định nghĩa input/output trước khi code.
- **Việc cần làm:** Viết `docs/agents/keyvolume_agent_design.md`:
  - Input: dữ liệu từ loader Bước 4.3.
  - Output: **structured output bắt buộc** (theo pattern Portfolio Manager có sẵn) với các field cố định tối thiểu: `signal` (bullish/bearish/neutral/no_data), `confidence`, `evidence` (ngắn gọn).
  - Hành vi khi loader trả `No data available`: output `signal = no_data`, không gọi LLM đoán mò.
- **Cách kiểm tra:** Đọc lại, hình dung được output mẫu cụ thể.
- **Điều kiện hoàn thành:** File thiết kế tồn tại. Commit: `docs: design keyvolume agent`.

### Bước 5.2a: Test prompt thủ công với dữ liệu mẫu
- **Mục tiêu:** Xác nhận prompt cho ra output đúng schema **trước khi** viết code agent — tách lỗi prompt khỏi lỗi code.
- **Việc cần làm:** Viết prompt, dán dữ liệu mẫu vào, chạy thủ công với LLM (qua chat hoặc script 5 dòng), lặp chỉnh prompt tới khi output ổn định đúng schema.
- **Cách kiểm tra:** Chạy prompt 3 lần với cùng dữ liệu → output đúng schema cả 3 lần; thử với dữ liệu "xấu" (ít dòng, giá trị lạ) → không bịa tín hiệu.
- **Điều kiện hoàn thành:** Prompt cuối lưu vào `docs/agents/keyvolume_agent_prompt.md`. Commit: `docs: finalize keyvolume agent prompt`.

### Bước 5.2b: Bọc prompt thành code agent (standalone)
- **Mục tiêu:** Agent chạy độc lập, chưa nối pipeline.
- **Việc cần làm:** Viết agent theo pattern `agents/` có sẵn, dùng prompt 5.2a + loader 4.3.
- **Cách kiểm tra:** Chạy agent riêng với: (a) dữ liệu mẫu → output đúng schema; (b) symbol/date không có file → `signal = no_data`.
- **Điều kiện hoàn thành:** Cả 2 case pass. Commit: `feat: add standalone keyvolume agent`.

### Bước 5.3: Gắn vào pipeline qua toggle
- **Mục tiêu:** Agent mới xuất hiện trong report, bật/tắt được qua config.
- **Việc cần làm:** Thêm node vào graph (đúng 1 file build graph — Quy tắc 5), thêm cờ config.
- **Cách kiểm tra:** Chạy full pipeline (memory test) 3 lần: bật + có dữ liệu / bật + thiếu file / tắt. So sánh report.
- **Điều kiện hoàn thành:** Cả 3 case ổn, ghi `TEST_PLAN.md`. Commit: `feat: integrate keyvolume agent into pipeline`.

---

## Phase 6 — Liquidity Sweep Agent

> Lặp lại cấu trúc Phase 5. Dữ liệu đọc từ `data/liquidity/{SYMBOL}_{YYYY-MM-DD}.csv`.

### Bước 6.1: Thiết kế agent + đặc tả dữ liệu liquidity
- **Việc cần làm:** Viết `docs/agents/liquidity_sweep_agent_design.md`. Nếu format file liquidity khác keyvolume → viết thêm `docs/data/liquidity_data_format.md` (mini-4.1) và mở rộng loader (mini-4.3) trong cùng session này.
- **Điều kiện hoàn thành:** Commit: `docs: design liquidity sweep agent`.

### Bước 6.2a: Test prompt thủ công
- Giống 5.2a. Commit: `docs: finalize liquidity sweep agent prompt`.

### Bước 6.2b: Code agent standalone
- Giống 5.2b, gồm case thiếu file → `no_data`. Commit: `feat: add standalone liquidity sweep agent`.

### Bước 6.3: Gắn vào pipeline + test tổ hợp 2 agent mới
- **Cách kiểm tra:** Chạy đủ **4 tổ hợp** bật/tắt (KeyVolume × LiquiditySweep) với memory test, không xung đột.
- **Điều kiện hoàn thành:** 4 tổ hợp ghi `TEST_PLAN.md`. Commit: `feat: integrate liquidity sweep agent into pipeline`.

---

## Phase 7 — Market Bias / Final Advisor

### Bước 7.1: Thiết kế node tổng hợp cuối
- **Mục tiêu:** Quyết định node này gộp vào Portfolio Manager có sẵn hay là bước mới sau nó.
- **Việc cần làm:** Viết `docs/agents/final_advisor_design.md`:
  - Input: toàn bộ tín hiệu (agent gốc + KeyVolume + Liquidity Sweep).
  - Output: 1 advisory report tổng hợp — khuyến nghị + lý do + mức tin cậy. **Ghi rõ "advisory only" trong thiết kế** (Quy tắc 3).
  - Xử lý tín hiệu `no_data` hoặc agent bị tắt: ghi "không có dữ liệu", không lỗi.
  - Không phá format decision log hiện có (Phase 8 phụ thuộc).
- **Điều kiện hoàn thành:** Thiết kế tồn tại. Commit: `docs: design final advisor node`.

### Bước 7.2: Cài đặt Final Advisor
- **Mục tiêu:** Report cuối dễ đọc, luôn sinh ra được.
- **Việc cần làm:** Code node theo thiết kế 7.1, structured output.
- **Cách kiểm tra:** Chạy full pipeline (memory test) với cấu hình mặc định (mọi agent bật, có dữ liệu), đọc report bằng mắt — dễ hiểu, có lý do rõ.
- **Điều kiện hoàn thành:** Report chuẩn sinh ra. Commit: `feat: add final advisor node`.

### Bước 7.3: Test các tổ hợp bật/tắt (session riêng)
- **Mục tiêu:** Final Advisor không crash trong mọi cấu hình.
- **Việc cần làm:** Chạy các tổ hợp đại diện (không cần vét cạn — chọn theo rủi ro): mỗi agent mới tắt riêng / cả 2 tắt / thiếu file dữ liệu / 1–2 analyst tắt.
- **Cách kiểm tra:** Mọi tổ hợp đều ra report hợp lệ hoặc thông báo lỗi rõ ràng.
- **Điều kiện hoàn thành:** Bảng kết quả trong `TEST_PLAN.md`. Commit: `test: final advisor toggle combinations`.

---

## Phase 8 — Decision Log & Backtest Evidence

### Bước 8.1: Mở rộng decision log
- **Mục tiêu:** Log lưu thêm tín hiệu KeyVolume, Liquidity Sweep, Market Bias — tương thích ngược.
- **Việc cần làm:** Sửa `reporting.py` thêm field mới; agent tắt/no_data → field ghi giá trị rỗng hợp lý, không lỗi.
- **Cách kiểm tra:** Chạy lại (memory test), file log có field mới; log cũ vẫn đọc được (cơ chế reflection không vỡ).
- **Điều kiện hoàn thành:** Backward-compatible xác nhận. Commit: `feat: extend decision log with new agent signals`.

### Bước 8.2: Script so sánh đơn giản (backtest evidence tối giản)
- **Mục tiêu:** Bằng chứng thô: tín hiệu từng đưa ra khớp diễn biến giá trong dữ liệu tĩnh đến đâu.
- **Việc cần làm:** Viết script nhỏ đọc decision log + file dữ liệu tĩnh, in bảng: ngày | tín hiệu | giá sau đó.
  - **Tuân thủ Quy tắc 6:** tín hiệu ngày D chỉ đối chiếu với dữ liệu ≤ D tại thời điểm sinh tín hiệu; "giá sau đó" chỉ dùng để chấm điểm, không được lọt vào input agent.
- **Cách kiểm tra:** Chạy trên vài dòng mẫu, đọc bảng bằng mắt, hợp lý.
- **Điều kiện hoàn thành:** Có file output làm bằng chứng đầu tiên. Commit: `feat: add simple backtest evidence script`.

---

## Phase 9 — Post-MVP (KHÔNG làm trong MVP, chỉ ghi để không quên)

- Toggle cho Researcher / Risk Team / Portfolio Manager.
- Chuyển dữ liệu tĩnh → API/connector KeyVolume thật.
- Xem xét cập nhật upstream (gỡ đóng băng, qua phase merge riêng).
- Mở rộng backtest (nhiều ticker, khung thời gian dài, metric alpha vs benchmark).

---

## Bảng file quản lý dự án (tạo ở Phase 0)

| File | Mục đích |
|---|---|
| `PRODUCT_SCOPE.md` | Phạm vi + Quy tắc bất biến 1–6 + Out of scope |
| `ROADMAP.md` | File này — 🔒 LOCKED |
| `UPSTREAM.md` | URL + commit hash đóng băng + quy tắc không pull + lý do |
| `CHANGELOG_CUSTOM.md` | Nhật ký thay đổi custom + ADR (ghi cuối file) |
| `TEST_PLAN.md` | Setup memory test bắt buộc + kết quả test từng phase |
| `SESSION_LOG.md` | Bộ nhớ nối các session: làm gì / kết quả / dở dang / memory path |
| `docs/architecture/` | Audit Phase 2 + thiết kế toggle |
| `docs/agents/` | Thiết kế + prompt từng agent mới |
| `docs/data/` | Format dữ liệu tĩnh + quy ước mapping |

---

## Rủi ro & lưu ý

1. **Chất lượng dữ liệu tĩnh quyết định chất lượng tín hiệu.** Dữ liệu mẫu quá ít/không đại diện → tín hiệu không đáng tin. Cần dữ liệu đủ đa dạng trước khi tin kết quả Phase 8.
2. **Chi phí LLM:** luôn test với model rẻ, chỉ dùng model mạnh khi logic đã đúng.
3. **Reflection loop:** memory test tách riêng (Quy tắc 1) chính là để bảo vệ cơ chế này — kiểm tra lại sau mỗi phase có sửa `reporting.py`.
4. **Commit nhỏ, revert dễ:** mỗi bước 1 commit (Phase 3.3 mỗi analyst 1 commit) — điểm an toàn để lùi.
5. **Không sửa code lõi nếu tránh được:** ưu tiên thêm file mới + cờ config.
6. **Timezone/format ngày** giữa dữ liệu Backtest-Trading-Lab và pipeline gốc — đã có kiểm tra khớp ngày trong loader (4.3), không bỏ qua bước này.
7. **Lookahead bias** (Quy tắc 6) — rủi ro âm thầm nhất của backtest với dữ liệu tĩnh; đã ràng buộc trong 8.2.

---

## Checklist khóa roadmap

- [x] 2 quy tắc cứng: memory test tách riêng + đóng băng upstream
- [x] Điểm vá 1: tag `v0-baseline` + hash trong `UPSTREAM.md` (Bước 1.1)
- [x] Điểm vá 2: quy ước mapping file ↔ ticker/date + hành vi thiếu file (Quy tắc 4, Bước 4.1)
- [x] Điểm vá 3: Phase 3 thu hẹp còn nhóm Analyst; phần còn lại → Phase 9
- [x] Điểm vá 4: tách 5.2 → 5.2a/5.2b; tách 7.2 → 7.2/7.3
- [x] Điểm vá 5: thêm `SESSION_LOG.md`

**Roadmap khóa tại phiên bản 1.0. Bắt đầu từ Phase 0, Bước 0.1.**
