---
description: Auto-save code changes with version bump and git commit
---
Tự động commit code với version bump.

## Cách sử dụng

1. Chạy với commit message mặc định (patch bump):
// turbo
```
python scripts/auto_commit.py "update"
```

2. Hoặc với message cụ thể:
```
python scripts/auto_commit.py "feat: Add new feature"
```

3. Bump version khác (minor/major):
```
python scripts/auto_commit.py "New feature" minor
python scripts/auto_commit.py "Breaking change" major
```

## Tự động chạy mỗi khi thay đổi code

Nếu muốn tự động commit SAU MỖI thay đổi, chạy lệnh:
```
python scripts/auto_commit.py "auto-update"
```

## Auto-update CLAUDE.md

**SAU MỖI COMMIT**, nếu có thay đổi file trong `converters/`, `core/`, `ui/`, `utils/`, hoặc `requirements.txt`:
- Chạy `/update-claude-md` để cập nhật CLAUDE.md
- Điều này đảm bảo AI agents luôn có context mới nhất
