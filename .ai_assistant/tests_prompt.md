# 🧪 Test Generation Request

**Vai trò**: Senior Test Engineer

**Module**: utils
**Functions**: 10

## Functions cần test


### get_pool()
**File**: `utils\com_pool.py:258`
**Docstring**: Get global COM pool instance.
```python
def get_pool() -> COMPool:
    """Get global COM pool instance."""
    global _pool
    if _pool is None:
        _pool = COMPool()
    return _pool


```


### release_pool()
**File**: `utils\com_pool.py:266`
**Docstring**: Release global COM pool.
```python
def release_pool():
    """Release global COM pool."""
    global _pool
    if _pool:
        _pool.release_all()
        _pool = None
```


### get_excel(_retry_count)
**File**: `utils\com_pool.py:84`
**Docstring**: Get or create Excel COM instance.
```python
    def get_excel(self, _retry_count: int = 0) -> Optional[Any]:
        """Get or create Excel COM instance."""
        if _retry_count >= self.MAX_RETRY:
            logger.error("Max retries exceeded for Excel COM creation")
            return None

        with self._lock:
            # Health check existing instance
```


### get_word(_retry_count)
**File**: `utils\com_pool.py:114`
**Docstring**: Get or create Word COM instance.
```python
    def get_word(self, _retry_count: int = 0) -> Optional[Any]:
        """Get or create Word COM instance."""
        if _retry_count >= self.MAX_RETRY:
            logger.error("Max retries exceeded for Word COM creation")
            return None

        with self._lock:
            # Health check existing instance
```


### get_ppt(_retry_count)
**File**: `utils\com_pool.py:144`
**Docstring**: Get or create PowerPoint COM instance.
```python
    def get_ppt(self, _retry_count: int = 0) -> Optional[Any]:
        """Get or create PowerPoint COM instance."""
        if _retry_count >= self.MAX_RETRY:
            logger.error("Max retries exceeded for PowerPoint COM creation")
            return None

        with self._lock:
            # Health check existing instance
```


### release_all()
**File**: `utils\com_pool.py:237`
**Docstring**: Release all COM instances. Call on app exit.
```python
    def release_all(self):
        """Release all COM instances. Call on app exit."""
        with self._lock:
            self._recycle_excel()
            self._recycle_word()
            self._recycle_ppt()
            logger.info("All COM instances released")

```


### get_stats()
**File**: `utils\com_pool.py:245`
**Docstring**: Get usage statistics.
```python
    def get_stats(self) -> Dict[str, int]:
        """Get usage statistics."""
        return {
            "excel_conversions": self._excel_count,
            "word_conversions": self._word_count,
            "ppt_conversions": self._ppt_count
        }

```


### __init__(config_path)
**File**: `utils\config.py:44`
**Docstring**: No docstring
```python
    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return

        if config_path:
            self._config_path = config_path
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```


### load()
**File**: `utils\config.py:59`
**Docstring**: Load config from file.
```python
    def load(self) -> bool:
        """Load config from file."""
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._data = {**copy.deepcopy(DEFAULT_CONFIG), **loaded}
                    logger.info(f"Config loaded from {self._config_path}")
```


### save()
**File**: `utils\config.py:72`
**Docstring**: Save config to file.
```python
    def save(self) -> bool:
        """Save config to file."""
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            logger.info(f"Config saved to {self._config_path}")
            return True
        except Exception as e:
```



## Yêu cầu

Viết pytest test cases cho mỗi function với:
1. **Happy path**: Input hợp lệ
2. **Edge cases**: None, empty, boundary values
3. **Error handling**: Invalid input

## Output Format

Trả về Python code có thể chạy được:
```python
import pytest
# ... test code
```
