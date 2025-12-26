"""
ReactorApp - Main Application Window

Event-driven UI with Command Pattern and reactive updates.

Features:
- CustomTkinter modern UI
- VirtualListView for file display
- Command-based actions (non-blocking)
- Event-driven updates (reactive)
- Optimistic UI feedback (instant)
- Real-time statistics panel

Usage:
    from grid.reactor import ReactorApp
    
    app = ReactorApp(num_workers=4)
    app.mainloop()
"""

import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
import logging
from typing import Optional
from pathlib import Path

from grid import ConversionGrid
from grid.models import ConversionFile
from grid.reactor.commands import (
    CommandBus,
    ExecutionContext,
    AddFilesCommand,
    ClearQueueCommand,
    StopConversionCommand
)
from grid.reactor.events import (
    EventBus,
    FileAddedEvent,
    FileCompletedEvent,
    FileFailedEvent,
    ProgressEvent,
    WorkerDeathEvent
)
from grid.reactor.optimistic import OptimisticState
from grid.reactor.bridge import GridBridge
from grid.reactor.virtual_list import VirtualListView, VirtualListConfig, default_file_renderer

logger = logging.getLogger(__name__)

# CustomTkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class ReactorApp(ctk.CTk):
    """Main Reactor Application Window.
    
    Modern, event-driven UI for the Autonomous Conversion Grid.
    
    Example:
        >>> app = ReactorApp(num_workers=4, enable_hot_spare=True)
        >>> app.mainloop()
    """
    
    def __init__(
        self,
        num_workers: int = 4,
        enable_hot_spare: bool = True
    ):
        """Initialize application.
        
        Args:
            num_workers: Number of worker processes
            enable_hot_spare: Enable hot spare failover
        """
        super().__init__()
        
        # Window configuration
        self.title("Office Converter - Autonomous Grid")
        self.geometry("1000x700")
        self.minsize(800, 600)
        
        # Grid configuration
        self.num_workers = num_workers
        self.enable_hot_spare = enable_hot_spare
        
        # Initialize grid
        self.grid_instance = ConversionGrid(
            num_workers=num_workers,
            enable_hot_spare=enable_hot_spare
        )
        
        # Event bus
        self.event_bus = EventBus()
        
        # Grid bridge (connects grid callbacks to events)
        self.bridge = GridBridge(self.grid_instance, self.event_bus)
        
        # Command bus
        self.execution_context = ExecutionContext(
            grid=self.grid_instance,
            event_bus=self.event_bus
        )
        self.command_bus = CommandBus(self.execution_context)
        
        # Optimistic state
        self.optimistic_state = OptimisticState()
        
        # UI state
        self.files_list = []
        
        # Setup UI
        self._setup_ui()
        self._subscribe_events()
        
        # Start grid
        self.grid_instance.start()
        
        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        logger.info("ReactorApp initialized")
    
    # ========================================================================
    # UI SETUP
    # ========================================================================
    
    def _setup_ui(self):
        """Setup UI components."""
        # Configure grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        self._create_header()
        
        # Main content (file list)
        self._create_file_list()
        
        # Button bar
        self._create_button_bar()
        
        # Status bar
        self._create_status_bar()
    
    def _create_header(self):
        """Create header with title and stats."""
        header_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", height=80)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header_frame.grid_propagate(False)
        
        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text="🚀 Autonomous Conversion Grid",
            font=("Segoe UI", 24, "bold"),
            text_color="#2fa572"
        )
        title_label.pack(side="left", padx=20, pady=10)
        
        # Stats panel
        self.stats_frame = ctk.CTkFrame(header_frame, fg_color="#2a2a2a")
        self.stats_frame.pack(side="right", padx=20, pady=10, fill="y")
        
        self.stats_label = ctk.CTkLabel(
            self.stats_frame,
            text="Workers: 0  |  Queued: 0  |  Completed: 0  |  Success: 0%",
            font=("Consolas", 11),
            text_color="#cccccc"
        )
        self.stats_label.pack(padx=15, pady=10)
    
    def _create_file_list(self):
        """Create virtual file list."""
        list_frame = ctk.CTkFrame(self, fg_color="#1a1a1a")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Virtual list
        config = VirtualListConfig(
            item_height=35,
            viewport_items=20,
            bg_color="#1a1a1a",
            fg_color="#ffffff",
            selected_color="#2fa572",
            hover_color="#2a2a2a"
        )
        
        self.file_list = VirtualListView(
            list_frame,
            config=config,
            on_item_click=self._on_file_click,
            item_renderer=default_file_renderer
        )
        self.file_list.grid(row=0, column=0, sticky="nsew")
    
    def _create_button_bar(self):
        """Create button bar."""
        button_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", height=60)
        button_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        button_frame.grid_propagate(False)
        
        # Add Files button
        self.add_btn = ctk.CTkButton(
            button_frame,
            text="➕ Add Files",
            command=self._on_add_files,
            width=140,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#2fa572",
            hover_color="#27864f"
        )
        self.add_btn.pack(side="left", padx=(10, 5), pady=10)
        
        # Clear Queue button
        self.clear_btn = ctk.CTkButton(
            button_frame,
            text="🗑️ Clear Queue",
            command=self._on_clear_queue,
            width=140,
            height=40,
            font=("Segoe UI", 13),
            fg_color="#666666",
            hover_color="#555555"
        )
        self.clear_btn.pack(side="left", padx=5, pady=10)
        
        # Stop button
        self.stop_btn = ctk.CTkButton(
            button_frame,
            text="⏹️ Stop",
            command=self._on_stop,
            width=120,
            height=40,
            font=("Segoe UI", 13),
            fg_color="#d32f2f",
            hover_color="#b71c1c"
        )
        self.stop_btn.pack(side="left", padx=5, pady=10)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            button_frame,
            width=300,
            height=20,
            fg_color="#2a2a2a",
            progress_color="#2fa572"
        )
        self.progress_bar.pack(side="right", padx=10, pady=10)
        self.progress_bar.set(0)
    
    def _create_status_bar(self):
        """Create status bar."""
        status_frame = ctk.CTkFrame(self, fg_color="#2a2a2a", height=30)
        status_frame.grid(row=3, column=0, sticky="ew")
        status_frame.grid_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="⚡ Grid operational  |  Ready to convert files",
            font=("Consolas", 10),
            text_color="#888888",
            anchor="w"
        )
        self.status_label.pack(side="left", padx=10, fill="x", expand=True)
    
    # ========================================================================
    # EVENT SUBSCRIPTIONS
    # ========================================================================
    
    def _subscribe_events(self):
        """Subscribe to grid events."""
        self.event_bus.subscribe(FileAddedEvent, self._on_file_added_event)
        self.event_bus.subscribe(FileCompletedEvent, self._on_file_completed_event)
        self.event_bus.subscribe(FileFailedEvent, self._on_file_failed_event)
        self.event_bus.subscribe(ProgressEvent, self._on_progress_event)
        self.event_bus.subscribe(WorkerDeathEvent, self._on_worker_death_event)
        
        logger.debug("Subscribed to grid events")
    
    # ========================================================================
    # COMMAND HANDLERS (UI → Grid)
    # ========================================================================
    
    def _on_add_files(self):
        """Add files button clicked."""
        # File dialog
        file_paths = filedialog.askopenfilenames(
            title="Select Office Files",
            filetypes=[
                ("Office Files", "*.docx *.xlsx *.pptx *.doc *.xls *.ppt"),
                ("All Files", "*.*")
            ]
        )
        
        if not file_paths:
            return
        
        # Optimistic update (instant UI feedback)
        for path in file_paths:
            temp_id = self.optimistic_state.add_optimistic({
                'filename': Path(path).name,
                'status': 'validating',
                'path': path
            })
        
        # Refresh file list immediately
        self._refresh_file_list()
        
        # Execute command (async)
        cmd = AddFilesCommand(file_paths=tuple(file_paths))
        future = self.command_bus.execute_async(cmd)
        
        logger.info(f"Add files command posted: {len(file_paths)} files")
    
    def _on_clear_queue(self):
        """Clear queue button clicked."""
        cmd = ClearQueueCommand()
        self.command_bus.execute_async(cmd)
        
        # Clear optimistic state
        self.files_list.clear()
        self._refresh_file_list()
        
        self._update_status("Queue cleared")
    
    def _on_stop(self):
        """Stop button clicked."""
        cmd = StopConversionCommand()
        self.command_bus.execute_async(cmd)
        
        self._update_status("Stopping conversion...")
    
    # ========================================================================
    # EVENT HANDLERS (Grid → UI)
    # ========================================================================
    
    def _on_file_added_event(self, event: FileAddedEvent):
        """Handle file added to grid."""
        # Reconcile optimistic state
        if event.temp_id:
            self.optimistic_state.reconcile(event.temp_id, event.file)
        
        # Add to files list
        if event.file not in self.files_list:
            self.files_list.append(event.file)
        
        # Refresh UI
        self.after(0, self._refresh_file_list)
        
        logger.debug(f"File added: {event.file.filename}")
    
    def _on_file_completed_event(self, event: FileCompletedEvent):
        """Handle file completion."""
        # Update file status
        # (In real implementation, would update ConversionFile.status)
        
        self._update_status(f"✅ Completed: {event.file.filename}")
        logger.info(f"File completed: {event.file.filename}")
    
    def _on_file_failed_event(self, event: FileFailedEvent):
        """Handle file failure."""
        self._update_status(f"❌ Failed: {event.file.filename} - {event.error}")
        logger.warning(f"File failed: {event.file.filename}: {event.error}")
    
    def _on_progress_event(self, event: ProgressEvent):
        """Handle progress update."""
        # Update progress bar
        if event.total > 0:
            progress = event.completed / event.total
            self.after(0, lambda: self.progress_bar.set(progress))
        
        # Update stats
        self.after(0, self._refresh_stats)
    
    def _on_worker_death_event(self, event: WorkerDeathEvent):
        """Handle worker death."""
        self._update_status(f"⚠️ Worker {event.worker_id} died - failover in progress")
        logger.warning(f"Worker death: {event.worker_id}")
    
    # ========================================================================
    # UI UPDATES
    # ========================================================================
    
    def _refresh_file_list(self):
        """Refresh file list display."""
        # Merge optimistic + real items
        merged = self.optimistic_state.get_merged_items(self.files_list)
        
        # Update virtual list
        self.file_list.set_items(merged)
    
    def _refresh_stats(self):
        """Refresh statistics display."""
        stats = self.grid_instance.get_stats()
        
        # Update stats label
        workers = stats['pool']['active_workers']
        queued = stats['scheduler']['pending']
        completed = stats['total_completed']
        success_rate = stats['success_rate']
        
        self.stats_label.configure(
            text=f"Workers: {workers}  |  Queued: {queued}  |  "
                 f"Completed: {completed}  |  Success: {success_rate:.1f}%"
        )
    
    def _update_status(self, message: str):
        """Update status bar.
        
        Args:
            message: Status message
        """
        self.after(0, lambda: self.status_label.configure(text=message))
    
    def _on_file_click(self, index: int, item):
        """Handle file click in list.
        
        Args:
            index: Item index
            item: Item data
        """
        logger.debug(f"File clicked: {index}, {item}")
    
    # ========================================================================
    # LIFECYCLE
    # ========================================================================
    
    def _on_closing(self):
        """Handle window close."""
        logger.info("Application closing...")
        
        # Update status
        self._update_status("Shutting down grid...")
        
        # Shutdown grid
        self.grid_instance.shutdown(timeout=10.0)
        
        # Destroy window
        self.destroy()
        
        logger.info("Application closed")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Run ReactorApp."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run app
    app = ReactorApp(num_workers=4, enable_hot_spare=True)
    app.mainloop()


if __name__ == '__main__':
    main()
