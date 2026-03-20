---
trigger: always_on
---

Khi bắt đầu mỗi conversation mới hoặc nhận yêu cầu liên quan đến code:
1. LUÔN đọc file CLAUDE.md ở root project TRƯỚC KHI làm bất kỳ điều gì khác.
2. Sử dụng thông tin trong CLAUDE.md làm context cho toàn bộ conversation.
3. SAU MỖI THAY ĐỔI CODE liên quan đến converters/, core/, ui/, utils/, hoặc requirements.txt → tự động chạy workflow /update-claude-md để cập nhật CLAUDE.md.
4. Tuân thủ tất cả Critical Rules trong CLAUDE.md (COM STA, Tkinter thread-safety, Force-Stop, Pre-flight, Testing).