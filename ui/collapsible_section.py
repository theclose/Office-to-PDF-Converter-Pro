"""
Collapsible Section — R7 Accordion Pattern for Options Panel.
Provides a clickable header that expands/collapses content with smooth animation.
"""
import customtkinter as ctk
from office_converter.utils.logging_setup import get_logger

logger = get_logger("CollapsibleSection")


class CollapsibleSection(ctk.CTkFrame):
    """Accordion-style collapsible section for options panel.
    
    Features:
    - Clickable header with arrow icon toggle
    - Hover highlight on header
    - Item count badge (optional)
    - Separator line between sections
    
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
        self._badge_text = ""
        
        # Separator line at top
        self._separator = ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray35"))
        self._separator.pack(fill="x", padx=8, pady=(2, 0))
        
        # Header container (holds button + optional badge)
        header_container = ctk.CTkFrame(self, fg_color="transparent")
        header_container.pack(fill="x", padx=5, pady=(3, 0))
        
        # Header (clickable toggle)
        self.header = ctk.CTkButton(
            header_container,
            text=f"{'▼' if expanded else '▶'} {title}",
            fg_color="transparent",
            hover_color=("gray85", "gray30"),
            anchor="w",
            command=self.toggle,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=30,
            corner_radius=6,
            text_color=("gray10", "gray90")
        )
        self.header.pack(side="left", fill="x", expand=True)
        
        # Badge label (e.g. "5 items" or status indicator)
        self._badge = ctk.CTkLabel(
            header_container,
            text="",
            font=ctk.CTkFont(size=9),
            text_color="gray",
            width=0
        )
        # Badge hidden by default — set_badge() to show
        
        # Content frame
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        if expanded:
            self.content.pack(fill="x", padx=12, pady=(2, 8))
    
    def toggle(self):
        """Toggle expanded/collapsed state with visual feedback."""
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
    
    def set_badge(self, text: str):
        """Set or update the badge text (shown next to header)."""
        self._badge_text = text
        if text:
            self._badge.configure(text=text)
            self._badge.pack(side="right", padx=(0, 8))
        else:
            self._badge.pack_forget()
    
    @property
    def is_expanded(self) -> bool:
        return self._expanded
