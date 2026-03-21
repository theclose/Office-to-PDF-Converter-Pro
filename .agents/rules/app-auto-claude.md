---
trigger: always_on
---

Khi bắt đầu mỗi conversation mới hoặc nhận yêu cầu liên quan đến code:
1. LUÔN đọc file CLAUDE.md ở root project TRƯỚC KHI làm bất kỳ điều gì khác.
2. Sử dụng thông tin trong CLAUDE.md làm context cho toàn bộ conversation.
3. Khi làm việc với code trong subdirectory cụ thể → đọc CLAUDE.md của subdirectory đó:
   - converters/ → đọc converters/CLAUDE.md (COM rules, quality mapping)
   - ui/ → đọc ui/CLAUDE.md (GUI layout rules, visual verify)
   - core/ → đọc core/CLAUDE.md (engine, PDF processing)
4. Khi cần chi tiết → đọc docs/ tương ứng:
   - docs/architecture.md (file map, LOC, config)
   - docs/converters-guide.md (COM, fallback chains)
   - docs/gui-rules.md (pack_propagate, thread safety)
   - docs/known-traps.md (bẫy đã biết — ĐỌC KHI DEBUG)
5. SAU MỖI THAY ĐỔI CODE liên quan đến converters/, core/, ui/, utils/ → chạy workflow /update-claude-md (verify-first).
6. Tuân thủ tất cả Critical Rules trong CLAUDE.md (COM STA, Tkinter, Force-Stop, GUI Layout, Quality System, Testing, Pre-flight).
7. Khi fix bug → PHẢI thêm entry vào docs/known-traps.md (ghi WHY + HOW TO AVOID).