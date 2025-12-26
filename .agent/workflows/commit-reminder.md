---
description: Quy trình commit code sau mỗi thay đổi
---

# Auto-Commit Workflow

## Quy tắc cho Antigravity

**SAU MỖI LẦN THAY ĐỔI CODE** (edit file, tạo file mới, xóa file), phải:

1. Hỏi user: "Bạn có muốn commit thay đổi này không?"
2. Nếu user đồng ý, chạy:
   ```
   python scripts/auto_commit.py "mô tả thay đổi"
   ```

## Loại thay đổi và bump type

| Thay đổi | Bump | Ví dụ |
|----------|------|-------|
| Fix bug nhỏ | patch | `"fix: Sửa lỗi XYZ"` |
| Thêm feature | minor | `"feat: Thêm tính năng ABC" minor` |
| Breaking change | major | `"breaking: Thay đổi API" major` |

## Commit message format

```
[type]: [mô tả ngắn gọn]
```

Types: feat, fix, refactor, docs, test, chore
