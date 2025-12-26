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

class FileToolsEngine:
    """Main engine for processing file rules."""
    
    def __init__(self):
        self.rules: List[RenameRule] = []
        
    def add_rule(self, rule: RenameRule):
        self.rules.append(rule)
        
    def clear_rules(self):
        self.rules = []
        
    def preview(self, files: List[str]) -> List[RenamePreview]:
        """Generate preview for a list of files."""
        results = []
        seen_names = set()
        
        for i, file_path in enumerate(files):
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            
            # Apply all rules
            curr_name = name
            curr_ext = ext
            
            for rule in self.rules:
                try:
                    curr_name, curr_ext = rule.apply(curr_name, curr_ext, index=i)
                except Exception as e:
                    logger.error(f"Rule {rule} failed on {filename}: {e}")
                    
            new_filename = f"{curr_name}{curr_ext}"
            
            # Check status
            status = "ok"
            err = ""
            
            if new_filename == filename:
                status = "unchanged"
            elif new_filename in seen_names:
                status = "conflict"
                err = "Trùng tên với file khác trong danh sách"
            elif os.path.exists(os.path.join(directory, new_filename)):
                # If renaming case-only on Windows (e.g. abc.txt -> ABC.txt), existence check returns True
                # but it IS allowed. We need to check if it's the SAME file.
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
                
            except Exception as e:
                logger.error(f"Rename failed: {e}")
                results.append((p.original_path, False, str(e)))
                
        return results
