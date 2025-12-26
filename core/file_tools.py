"""
Core logic for File Tools (Rename, Manage).
Implements Command Pattern for rename rules.
"""
import os
import re
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Vietnamese Accent Map
_VIETNAMESE_MAP = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'đ': 'd',
    'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
    'À': 'A', 'Á': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
    'Ă': 'A', 'Ằ': 'A', 'Ắ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
    'Â': 'A', 'Ầ': 'A', 'Ấ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
    'Đ': 'D',
    'È': 'E', 'É': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
    'Ê': 'E', 'Ề': 'E', 'Ế': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
    'Ì': 'I', 'Í': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
    'Ò': 'O', 'Ó': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
    'Ô': 'O', 'Ồ': 'O', 'Ố': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
    'Ơ': 'O', 'Ờ': 'O', 'Ớ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
    'Ù': 'U', 'Ú': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
    'Ư': 'U', 'Ừ': 'U', 'Ứ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
    'Ỳ': 'Y', 'Ý': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y'
}

def remove_vietnamese_accents(text: str) -> str:
    """Remove Vietnamese accents from text."""
    result = []
    for char in text:
        result.append(_VIETNAMESE_MAP.get(char, char))
    return "".join(result)

@dataclass
class RenamePreview:
    """Result of a preview operation."""
    original_path: str
    new_filename: str
    status: str = "ok"  # ok, conflict, error, unchanged
    error_msg: str = ""
    
    @property
    def has_changed(self) -> bool:
        return os.path.basename(self.original_path) != self.new_filename

class RenameRule(ABC):
    """Abstract base class for a rename rule."""
    
    @abstractmethod
    def apply(self, name: str, extension: str, index: int = 0) -> Tuple[str, str]:
        """
        Apply rule to filename.
        Returns (new_name, new_extension)
        """
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        """User facing description of what this rule does."""
        pass

class CaseRule(RenameRule):
    """Change case of filename."""
    def __init__(self, mode: str = "lower"):
        self.mode = mode  # lower, upper, title, capitalize
        
    def apply(self, name: str, extension: str, index: int = 0) -> Tuple[str, str]:
        if self.mode == "lower":
            return name.lower(), extension.lower()
        elif self.mode == "upper":
            return name.upper(), extension.upper()
        elif self.mode == "title":
            return name.title(), extension # Keep ext as is usually
        elif self.mode == "capitalize":
            return name.capitalize(), extension
        return name, extension

    @property
    def description(self) -> str:
        return f"Change case to {self.mode}"

class ReplaceRule(RenameRule):
    """Replace text."""
    def __init__(self, old: str, new: str, ignore_case: bool = True):
        self.old = old
        self.new = new
        self.ignore_case = ignore_case
        
    def apply(self, name: str, extension: str, index: int = 0) -> Tuple[str, str]:
        if not self.old:
            return name, extension
            
        if self.ignore_case:
            pattern = re.compile(re.escape(self.old), re.IGNORECASE)
            new_name = pattern.sub(self.new, name)
        else:
            new_name = name.replace(self.old, self.new)
            
        return new_name, extension

    @property
    def description(self) -> str:
        return f"Replace '{self.old}' with '{self.new}'"

class RemoveAccentsRule(RenameRule):
    """Remove Vietnamese accents."""
    def __init__(self, only_name: bool = True):
        self.only_name = only_name
        
    def apply(self, name: str, extension: str, index: int = 0) -> Tuple[str, str]:
        new_name = remove_vietnamese_accents(name)
        if not self.only_name:
            # Also remove from extension if requested (rare)
            new_ext = remove_vietnamese_accents(extension)
            return new_name, new_ext
        return new_name, extension

    @property
    def description(self) -> str:
        return "Remove Vietnamese accents"

class TrimRule(RenameRule):
    """Trim whitespace."""
    def apply(self, name: str, extension: str, index: int = 0) -> Tuple[str, str]:
        return name.strip(), extension.strip()

    @property
    def description(self) -> str:
        return "Trim whitespace"

class AddStringRule(RenameRule):
    """Add string at start or end."""
    def __init__(self, text: str, at_start: bool = True):
        self.text = text
        self.at_start = at_start
        
    def apply(self, name: str, extension: str, index: int = 0) -> Tuple[str, str]:
        if self.at_start:
            return f"{self.text}{name}", extension
        else:
            return f"{name}{self.text}", extension

    @property
    def description(self) -> str:
        pos = "Start" if self.at_start else "End"
        return f"Add '{self.text}' to {pos}"

class SequenceRule(RenameRule):
    """Add sequence number."""
    def __init__(self, start: int = 1, step: int = 1, padding: int = 3, separator: str = "_", at_start: bool = False):
        self.start = start
        self.step = step
        self.padding = padding
        self.separator = separator
        self.at_start = at_start
        
    def apply(self, name: str, extension: str, index: int = 0) -> Tuple[str, str]:
        num = self.start + (index * self.step)
        num_str = str(num).zfill(self.padding)
        
        if self.at_start:
            # 001_Filename
            return f"{num_str}{self.separator}{name}", extension
        else:
            # Filename_001
            return f"{name}{self.separator}{num_str}", extension

    @property
    def description(self) -> str:
        return f"Numbering ({self.start}, {self.step}...)"

class ExtensionRule(RenameRule):
    """Change extension."""
    def __init__(self, mode: str = "preserve", new_ext: str = ""):
        self.mode = mode # preserve, lower, upper, new
        self.new_ext = new_ext
        
    def apply(self, name: str, extension: str, index: int = 0) -> Tuple[str, str]:
        if self.mode == "lower":
            return name, extension.lower()
        elif self.mode == "upper":
            return name.upper(), extension.upper()
        elif self.mode == "new":
            # Ensure dot
            ext = self.new_ext if self.new_ext.startswith(".") else f".{self.new_ext}"
            return name, ext
        return name, extension

    @property
    def description(self) -> str:
        return f"Extension: {self.mode}"

import hashlib

import hashlib
import stat
import ctypes
from datetime import datetime

@dataclass
class DuplicateGroup:
    """Group of duplicate files."""
    hash_val: str
    size: int
    files: List[str] # List of absolute paths

class EmptyFolderCleaner:
    """Finds and deletes empty folders."""
    
    def find_empty_folders(self, roots: List[str]) -> List[str]:
        """Find invalid/empty folders recursively (bottom-up)."""
        empty_folders = []
        
        for root_path in roots:
            if not os.path.exists(root_path): continue
            
            for root, dirs, files in os.walk(root_path, topdown=False):
                # Filter out system files that might be hidden but considered 'empty' user-wise?
                # For now strict emptiness (or only ignored files)
                
                # Check actual content
                try:
                    entries = os.listdir(root)
                    if not entries:
                        empty_folders.append(root)
                    elif all(e in ['.DS_Store', 'Thumbs.db'] for e in entries):
                         empty_folders.append(root)
                except OSError:
                    pass
                    
        return empty_folders

    def delete_folders(self, folders: List[str]) -> List[Tuple[str, bool, str]]:
        results = []
        for f in folders:
            try:
                # Remove common junk first if cleaning
                for junk in ['.DS_Store', 'Thumbs.db']:
                    junk_path = os.path.join(f, junk)
                    if os.path.exists(junk_path):
                        os.remove(junk_path)
                
                os.rmdir(f)
                results.append((f, True, "Deleted"))
            except Exception as e:
                results.append((f, False, str(e)))
        return results

class AttributeManager:
    """Manages file attributes and timestamps."""
    
    def set_dates(self, path: str, created: float = None, modified: float = None, accessed: float = None):
        """Set file timestamps."""
        try:
            # Modified & Accessed
            if modified is not None or accessed is not None:
                # os.utime takes (atime, mtime)
                # If one is None, use current? Or keep existing.
                current = os.stat(path)
                atime = accessed if accessed is not None else current.st_atime
                mtime = modified if modified is not None else current.st_mtime
                os.utime(path, (atime, mtime))
                
            # Created (Windows specific mainly)
            if created is not None and os.name == 'nt':
                # Set creation time on Windows is harder using standard lib
                # Using ctypes or win32_setcttime via other libraries.
                # Since we don't want extra deps, we might skip or use simple hack if possible.
                # Alternatively if user uses pywin32 (we don't check for it yet strictly).
                # Actually, standard python 'os.utime' does NOT set creation time.
                pass # TODO: Implement Windows SetCreationTime if critical.
                
            return True, "Updated timestamps"
        except Exception as e:
            return False, str(e)

    def set_attributes(self, path: str, readonly: bool = None, hidden: bool = None):
        """Set file attributes (Windows)."""
        try:
            if readonly is not None:
                current_mode = os.stat(path).st_mode
                if readonly:
                    os.chmod(path, current_mode | stat.S_IREAD) # Add read
                    os.chmod(path, current_mode & ~stat.S_IWRITE) # Remove write
                else:
                    os.chmod(path, current_mode | stat.S_IWRITE)
            
            if hidden is not None and os.name == 'nt':
                # Use ctypes for Hidden attribute
                FILE_ATTRIBUTE_HIDDEN = 0x02
                ret = ctypes.windll.kernel32.GetFileAttributesW(path)
                if ret != -1:
                    if hidden:
                        ctypes.windll.kernel32.SetFileAttributesW(path, ret | FILE_ATTRIBUTE_HIDDEN)
                    else:
                        ctypes.windll.kernel32.SetFileAttributesW(path, ret & ~FILE_ATTRIBUTE_HIDDEN)
                        
            return True, "Updated attributes"
        except Exception as e:
            return False, str(e)

class DuplicateFinder:
    """Finds duplicate files efficiently."""
    
    def __init__(self):
        self._abort = False
        
    def abort(self):
        self._abort = True
        
    def _calculate_hash(self, filepath: str, block_size: int = 65536) -> str:
        """Calculate MD5 hash of a file."""
        md5 = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                while True:
                    if self._abort: return ""
                    data = f.read(block_size)
                    if not data:
                        break
                    md5.update(data)
            return md5.hexdigest()
        except Exception as e:
            logger.error(f"Hash error {filepath}: {e}")
            return ""

    def find_duplicates(self, paths: List[str], recursive: bool = True) -> List[DuplicateGroup]:
        """
        Find duplicates in given paths.
        Strategy: Size -> Hash.
        """
        self._abort = False
        files_by_size = {}
        
        # 1. Scan and group by size
        all_files = []
        for path in paths:
            if os.path.isfile(path):
                all_files.append(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    if self._abort: return []
                    for f in files:
                        all_files.append(os.path.join(root, f))
                        
        for fpath in all_files:
            try:
                size = os.path.getsize(fpath)
                if size not in files_by_size:
                    files_by_size[size] = []
                files_by_size[size].append(fpath)
            except OSError:
                continue
                
        # 2. Filter groups with > 1 file
        potential_dupes = {s: fs for s, fs in files_by_size.items() if len(fs) > 1}
        
        # 3. Hash check for collisions
        results = []
        
        for size, file_list in potential_dupes.items():
            if self._abort: break
            
            # Group by hash within size group
            files_by_hash = {}
            for fpath in file_list:
                if self._abort: break
                file_hash = self._calculate_hash(fpath)
                if not file_hash: continue
                
                if file_hash not in files_by_hash:
                    files_by_hash[file_hash] = []
                files_by_hash[file_hash].append(fpath)
                
            # Add confirmed duplicates
            for h, paths in files_by_hash.items():
                if len(paths) > 1:
                    results.append(DuplicateGroup(hash_val=h, size=size, files=paths))
                    
        return results

import json
import time

@dataclass
class Transaction:
    """A record of file rename operations for undo."""
    timestamp: float
    operations: List[dict] # [{"old": str, "new": str}]

class TransactionLog:
    """Manages transaction history for undo functionality."""
    def __init__(self, log_dir: str = "logs/transactions"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
    def log(self, operations: List[Tuple[str, str]]):
        """Log a successful batch rename."""
        if not operations:
            return
            
        record = {
            "timestamp": time.time(),
            "operations": [{"old": op[0], "new": op[1]} for op in operations]
        }
        
        filename = f"transaction_{int(record['timestamp'])}.json"
        path = os.path.join(self.log_dir, filename)
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write transaction log: {e}")

    def get_last_transaction(self) -> Optional[Transaction]:
        """Get the most recent transaction."""
        try:
            files = sorted([f for f in os.listdir(self.log_dir) if f.startswith("transaction_")], reverse=True)
            if not files:
                return None
                
            path = os.path.join(self.log_dir, files[0])
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return Transaction(timestamp=data['timestamp'], operations=data['operations'])
        except Exception as e:
            logger.error(f"Failed to read transaction log: {e}")
            return None
            
    def remove_transaction_file(self, timestamp: float):
        """Remove a transaction file after undo."""
        filename = f"transaction_{int(timestamp)}.json"
        path = os.path.join(self.log_dir, filename)
        if os.path.exists(path):
            os.remove(path)

class FileToolsEngine:
    """Main engine for processing file rules."""
    
    def __init__(self):
        self.rules: List[RenameRule] = []
        self.transaction_log = TransactionLog()
        
    def add_rule(self, rule: RenameRule):
        self.rules.append(rule)
        
    def clear_rules(self):
        self.rules = []
        
    def undo_last_transaction(self) -> List[Tuple[str, bool, str]]:
        """
        Undo the last rename operation.
        Returns results similar to execute().
        """
        last_tx = self.transaction_log.get_last_transaction()
        if not last_tx:
            return []
            
        results = []
        # Reverse operations: new -> old
        # Process in reverse order to handle potential chains (A->B, B->C) correctly
        for op in reversed(last_tx.operations):
            old_path = op['old']
            new_path_current = op['new'] # This is what it currently is
            
            try:
                if not os.path.exists(new_path_current):
                    results.append((new_path_current, False, "File not found"))
                    continue
                    
                os.rename(new_path_current, old_path)
                results.append((new_path_current, True, f"Restored -> {os.path.basename(old_path)}"))
                
            except Exception as e:
                logger.error(f"Undo failed for {new_path_current}: {e}")
                results.append((new_path_current, False, str(e)))
                
        # If any success, remove the log
        if any(r[1] for r in results):
            self.transaction_log.remove_transaction_file(last_tx.timestamp)
            
        return results

    def preview(self, files: List[str]) -> List[RenamePreview]:
        """Generate preview for a list of files."""
        results = []
        seen_names = set()
        
        for i, file_path in enumerate(files):
            # Same preview logic as before ...
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            
            curr_name = name
            curr_ext = ext
            
            for rule in self.rules:
                try:
                    curr_name, curr_ext = rule.apply(curr_name, curr_ext, index=i)
                except Exception as e:
                    logger.error(f"Rule {rule} failed on {filename}: {e}")
                    
            new_filename = f"{curr_name}{curr_ext}"
            
            status = "ok"
            err = ""
            
            if new_filename == filename:
                status = "unchanged"
            elif new_filename in seen_names:
                status = "conflict"
                err = "Trùng tên với file khác trong list"
            elif os.path.exists(os.path.join(directory, new_filename)):
                if new_filename.lower() != filename.lower():
                     status = "conflict"
                     err = "File đã tồn tại"
            
            seen_names.add(new_filename)
            
            results.append(RenamePreview(
                original_path=file_path,
                new_filename=new_filename,
                status=status,
                error_msg=err
            ))
            
        return results

    def execute(self, files: List[str]) -> List[Tuple[str, bool, str]]:
        """
        Execute rename.
        Returns list of (original, success, message)
        """
        previews = self.preview(files)
        results = []
        successful_ops = [] # Tuples of (old_path, new_full_path) for logging
        
        for p in previews:
            if p.status == "unchanged":
                results.append((p.original_path, True, "Không thay đổi"))
                continue
            if p.status == "conflict":
                results.append((p.original_path, False, p.error_msg))
                continue
                
            try:
                directory = os.path.dirname(p.original_path)
                new_path = os.path.join(directory, p.new_filename)
                
                os.rename(p.original_path, new_path)
                results.append((p.original_path, True, f"-> {p.new_filename}"))
                successful_ops.append((p.original_path, new_path))
                
            except Exception as e:
                logger.error(f"Rename failed: {e}")
                results.append((p.original_path, False, str(e)))
        
        # Log transaction if any success
        if successful_ops:
            self.transaction_log.log(successful_ops)
                
        return results
