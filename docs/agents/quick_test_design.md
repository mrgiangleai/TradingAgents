# Quick Test mode — design (post-Phase-7, custom addition — see CHANGELOG_CUSTOM.md)

> Not part of the original locked `ROADMAP.md` phase list. Added as a dev/debug tool once KeyVolume, Liquidity Sweep, and Final Advisor (Phase 5-7) all existed and iterating on them meant paying for the entire 12-node analyst/debate/risk/portfolio chain every single run.

---

## 1. Mục tiêu

Giảm tối đa số lần gọi LLM khi phát triển/debug KeyVolume Agent, Liquidity Sweep Agent, hoặc Final Advisor — không cần chạy lại toàn bộ Full Analysis (4 analyst + debate + research + trader + risk debate + portfolio manager = tối thiểu ~12+ LLM call) mỗi lần chỉ muốn kiểm tra 1 trong 3 node mới.

**Full Analysis không đổi hành vi.** Đây là yêu cầu cứng — mọi thay đổi đều đi qua nhánh `if quick_test_mode:` mới, tách biệt hoàn toàn khỏi code path hiện có.

## 2. Graph shape

`START -> [KeyVolume Agent nếu bật] -> [Liquidity Sweep Agent nếu bật] -> Final Advisor -> END`

- Tái dùng đúng 2 cờ đã có (`enable_keyvolume_agent`/`enable_liquidity_sweep_agent`) — Quick Test không phải cờ thứ 3 kiểm soát 2 agent này, nó chỉ kiểm soát việc CÓ chạy 4 analyst/debate/research/trader/risk/portfolio hay không.
- `GraphSetup.setup_graph(quick_test_mode=True)` early-return sang `_setup_quick_test_graph()` — 1 method hoàn toàn tách biệt, không share code với nhánh Full Analysis (ngoài việc tái dùng đúng pattern "supplementary_nodes chain" đã có từ Phase 5.3/6.3, giờ chain tới "Final Advisor" thay vì analyst đầu tiên).
- Nếu cả 2 cờ tắt: graph chỉ còn `START -> Final Advisor -> END` — Final Advisor vẫn chạy (không phải lỗi, xem mục 4), chỉ là không có tín hiệu bổ sung nào để tổng hợp ngoài việc thiếu Portfolio Manager decision.

## 3. Vì sao Final Advisor cần sửa (không phải "sửa logic quyết định")

Final Advisor hiện đọc `state["final_trade_decision"]` bằng index trực tiếp — giả định Portfolio Manager luôn chạy trước nó (đúng trong Full Analysis, nơi Portfolio Manager không toggle được). Trong Quick Test, Portfolio Manager không chạy → key này hoàn toàn vắng mặt trong state (không phải `""`, vì `propagation.py::create_initial_state` không khởi tạo field này — xem `final_advisor_design.md` mục 5).

Sửa: `state.get("final_trade_decision")` + placeholder rõ ràng khi vắng mặt (`"Not available -- Quick Test mode skips..."`), đúng nguyên tắc "không tự bịa dữ liệu" đã áp dụng cho KeyVolume/Liquidity Sweep từ Phase 7. Thêm tham số `quick_test_mode: bool = False` vào `create_final_advisor()` chỉ để đổi 1 dòng hướng dẫn "ngắn gọn" trong prompt — schema/structured-output/disclaimer giữ nguyên 100%.

## 4. `_run_graph`/`_log_state` — vì sao không thể dùng nguyên bản Full Analysis

`_log_state` (Full Analysis) index trực tiếp `final_state["trader_investment_plan"]`, `final_state["investment_plan"]`, `final_state["final_trade_decision"]` — cả 3 field này KHÔNG được khởi tạo trong `create_initial_state` (khác `market_report`/`investment_debate_state`/`risk_debate_state`, vốn có khởi tạo `""`/dict rỗng). Trong Quick Test, Trader/Research Manager/Portfolio Manager không chạy → 3 key này vắng mặt hoàn toàn → `_log_state` sẽ `KeyError` nếu dùng nguyên bản.

Giải pháp: nhánh riêng `_log_state_quick_test()` — chỉ ghi 3 field thực sự có thể tồn tại (`keyvolume_report`/`liquidity_sweep_report`/`final_advisory_report`, đều qua `.get()`), ghi ra file tên khác (`quick_test_log_{date}.json`, không phải `full_states_log_{date}.json`) để không lẫn vào decision log Phase 8 sẽ mở rộng sau này (Phase 8 build trên format Full Analysis, không cần biết Quick Test tồn tại).

`memory_log.store_decision()` và `_resolve_pending_entries()` (gọi Reflector — 1 LLM call nữa) đều bị **bỏ qua hoàn toàn** trong Quick Test: không có `final_trade_decision` thật để nhớ/phản tư, và mục tiêu chính là giảm tối đa LLM call — không lý do gì để âm thầm cộng thêm 1 lệnh gọi Reflector.

`process_signal()` (rating 5 bậc trả về từ `propagate()`) đọc `final_advisory_report` thay vì `final_trade_decision` trong Quick Test — `parse_rating()` (heuristic có sẵn, không LLM) đã đủ tổng quát để tìm rating word trong bất kỳ text nào, không cần sửa `signal_processing.py`/`rating.py`.

## 5. CLI

Step 0 (trước cả Step 1 chọn ticker): chọn "Full Analysis" (mặc định) hoặc "Quick Test". Nếu chọn Quick Test: bỏ qua Step 4 (chọn analyst — không liên quan) và Step 5 (research depth — không có debate). Step 6-9 (LLM provider/model/reasoning/supplementary signals) vẫn hỏi bình thường — Quick Test vẫn cần model để gọi KeyVolume/Liquidity Sweep/Final Advisor.

`run_quick_test()` là hàm **hoàn toàn tách biệt** khỏi `run_analysis()` — không dùng `Live` layout/`AnalystWallTimeTracker` (thiết kế riêng cho 12-node Full Analysis, không khớp graph 1-3 node của Quick Test). Chỉ gọi thẳng `graph.propagate()`, in kết quả + thống kê (wall time/LLM calls/tokens qua `StatsCallbackHandler` có sẵn), rồi `display_complete_report()` (đã tự động chỉ hiện Section VI/VII/VIII vì các field khác vắng mặt — không cần sửa gì thêm ở `display_complete_report`/`reporting.py`).

## 6. Việc KHÔNG làm

- Không thêm cờ enable/disable cho Final Advisor (vẫn luôn chạy, kể cả trong Quick Test).
- Không sửa `analyst_execution.py`, bất kỳ analyst/researcher/risk-debator/portfolio-manager file nào.
- Không sửa `reporting.py`/`display_complete_report()` (đã đủ tổng quát từ Phase 7 nhờ `.get()` guards).
- Không đụng Backtest-Trading-Lab.
- Không mở rộng decision log chính thức (Phase 8, chưa làm) — `quick_test_log_*.json` là file riêng, tạm thời, không phải một phần format Phase 8 sẽ chuẩn hoá.
