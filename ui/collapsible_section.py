"""
Collapsible Section — R7 Accordion Pattern for Options Panel.
Provides a clickable header that expands/collapses content.
"""
import customtkinter as ctk
from office_converter.utils.logging_setup import get_logger

logger = get_logger("CollapsibleSection")


class CollapsibleSection(ctk.CTkFrame):
    """Accordion-style collapsible section for options panel.
    
    Usage:
        section = CollapsibleSection(parent, title="🎨 Quality", expanded=True)
        section.pack(fill="x")
        # Add widgets to section.content
        ctk.CTkLabel(section.content, text="Some option").pack()
    """
    
    def __init__(self, parent, title: str, expanded: bool = False, **kwargs):
        # Remove corner_radius from kwargs if present, use our default
        corner_radius = kwargs.pop("corner_radius", 8)
        super().__init__(parent, corner_radius=corner_radius, **kwargs)
        
        self._expanded = expanded
        self._title = title
        
        # Header (clickable toggle)
        self.header = ctk.CTkButton(
            self,
            text=f"{'▼' if expanded else '▶'} {title}",
            fg_color="transparent",
            hover_color=("gray85", "gray30"),
            anchor="w",
            command=self.toggle,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            corner_radius=6,
            text_color=("gray10", "gray90")
        )
        self.header.pack(fill="x", padx=5, pady=(5, 0))
        
        # Content frame
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        if expanded:
            self.content.pack(fill="x", padx=12, pady=(2, 8))
    
    def toggle(self):
        """Toggle expanded/collapsed state."""
        self._expanded = not self._expanded
        arrow = "▼" if self._expanded else "▶"
        self.header.configure(text=f"{arrow} {self._title}")
        
        if self._expanded:
            self.content.pack(fill="x", padx=12, pady=(2, 8))
        else:
            self.content.pack_forget()
    
    def expand(self):
        """Force expand."""
        if not self._expanded:
            self.toggle()
    
    def collapse(self):
        """Force collapse."""
        if self._expanded:
            self.toggle()
    
    @property
    def is_expanded(self) -> bool:
        return self._expanded
