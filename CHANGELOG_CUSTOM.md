# Changelog Custom

Mọi thay đổi so với `ROADMAP.md` (khoá tại v1.0, 2026-07-09) được ghi lại ở đây kèm lý do, theo đúng quy định ở đầu file đó.

---

## 2026-07-10 — Thêm Quick Test mode (không có trong ROADMAP.md gốc)

**Thay đổi:** Thêm chế độ chạy thứ 2 cho pipeline — "Quick Test" — bên cạnh "Full Analysis" (hành vi gốc, không đổi). Quick Test chỉ chạy KeyVolume Agent + Liquidity Sweep Agent + Final Advisor, bỏ qua toàn bộ 4 Analyst + Bull/Bear Debate + Research Manager + Trader + Risk Debate + Portfolio Manager.

**Lý do:** Sau khi Phase 5-7 hoàn thành (KeyVolume, Liquidity Sweep, Final Advisor), việc lặp lại phát triển/debug 3 node này đòi hỏi chạy toàn bộ Full Analysis (~12+ LLM call/lần) — chậm và tốn kém không cần thiết cho mục đích thuần kiểm thử/debug các node mới. Quick Test giảm số lệnh gọi LLM xuống còn 1-3 (tuỳ 2 cờ KeyVolume/Liquidity Sweep bật/tắt).

**Phạm vi:** Không nằm trong 9 Phase gốc của ROADMAP.md (dừng ở Phase 9 "Post-MVP"). Đây là công cụ phát triển nội bộ, không phải deliverable advisory report cho người dùng cuối — không ảnh hưởng Quy tắc 1-6 (Advisory only vẫn giữ nguyên: Final Advisor trong Quick Test vẫn có disclaimer "Advisory only", không tự bịa dữ liệu thiếu).

**File liên quan:** `docs/agents/quick_test_design.md` (thiết kế đầy đủ), `TEST_PLAN.md`/`SESSION_LOG.md` (mục "Quick Test mode").

**Cam kết đã giữ:** Full Analysis không đổi hành vi — xác nhận bằng test cấu trúc graph (số node/thứ tự y hệt trước khi thêm Quick Test) + test sống (xem TEST_PLAN.md).
