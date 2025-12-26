"""
GridBridge - Connects ConversionGrid to UI Events

Translates grid callbacks into EventBus events for reactive UI updates.

Architecture:
┌─────────────┐
│    Grid     │ (Phase 2 - Worker Pool)
└──────┬──────┘
       │ Callbacks (on_file_complete, etc.)
       ↓
┌─────────────┐
│ GridBridge  │ (This module)
└──────┬──────┘
       │ Events (FileCompletedEvent, etc.)
       ↓
┌─────────────┐
│  EventBus   │ (Phase 3 - Reactor)
└──────┬──────┘
       │ Subscriptions
       ↓
┌─────────────┐
│     UI      │ (ReactorApp)
└─────────────┘

Example:
    >>> grid = ConversionGrid(...)
    >>> event_bus = EventBus()
    >>> bridge = GridBridge(grid, event_bus)
    >>> 
    >>> # UI subscribes to events
    >>> event_bus.subscribe(FileCompletedEvent, on_file_done)
    >>> 
    >>> # Grid callback → Event → UI update
"""

import logging
from typing import Any

from grid import ConversionGrid
from grid.reactor.events import (
    EventBus,
    FileAddedEvent,
    FileCompletedEvent,
    FileFailedEvent,
    ProgressEvent,
    WorkerDeathEvent,
    LoadSheddingEvent,
    QuarantineEvent,
    CircuitBreakerEvent
)

logger = logging.getLogger(__name__)


class GridBridge:
    """Bridge between ConversionGrid and EventBus.
    
    Wires grid callbacks to event publications for reactive UI.
    
    Example:
        >>> grid = ConversionGrid(num_workers=4)
        >>> event_bus = EventBus()
        >>> bridge = GridBridge(grid, event_bus)
        >>> 
        >>> grid.start()
        >>> # Grid events now published to EventBus automatically
    """
    
    def __init__(self, grid: ConversionGrid, event_bus: EventBus):
        """Initialize bridge.
        
        Args:
            grid: ConversionGrid instance
            event_bus: EventBus for publishing events
        """
        self.grid = grid
        self.event_bus = event_bus
        
        # Wire callbacks
        self._wire_callbacks()
        
        logger.info("GridBridge initialized - Grid connected to EventBus")
    
    def _wire_callbacks(self):
        """Connect grid callbacks to event publications."""
        # File completion events
        self.grid.on_file_complete = self._on_file_complete
        self.grid.on_file_error = self._on_file_error
        self.grid.on_progress = self._on_progress
        
        # Worker pool events (if available)
        if hasattr(self.grid.pool, 'on_worker_death'):
            self.grid.pool.on_worker_death = self._on_worker_death
        
        logger.debug("Grid callbacks wired to EventBus")
    
    # ========================================================================
    # CALLBACK HANDLERS
    # ========================================================================
    
    def _on_file_complete(self, file: Any, result: dict):
        """Handle file completion.
        
        Args:
            file: ConversionFile that completed
            result: Result dict with output_path, duration, etc.
        """
        logger.debug(f"Grid callback: file completed - {file.filename}")
        
        # Publish event (with debouncing for rapid completions)
        self.event_bus.publish(
            FileCompletedEvent(file=file, result=result),
            debounce_ms=0  # No debounce for completions (want immediate UI update)
        )
    
    def _on_file_error(self, file: Any, error: str):
        """Handle file error.
        
        Args:
            file: ConversionFile that failed
            error: Error message
        """
        logger.debug(f"Grid callback: file failed - {file.filename}: {error}")
        
        # Publish event
        self.event_bus.publish(
            FileFailedEvent(file=file, error=error)
        )
        
        # Check if quarantined
        if file.file_hash in self.grid.quarantine:
            self.event_bus.publish(
                QuarantineEvent(
                    file=file,
                    failure_count=self.grid.circuit_breaker.get_circuit_state(file).failure_count
                )
            )
    
    def _on_progress(self, completed: int, total: int, current_file: str):
        """Handle progress update.
        
        Args:
            completed: Number of files completed
            total: Total files submitted
            current_file: Optional current file being processed
        """
        logger.debug(f"Grid callback: progress - {completed}/{total}")
        
        # Publish with debouncing (progress updates are frequent)
        self.event_bus.publish(
            ProgressEvent(
                completed=completed,
                total=total,
                current_file=current_file
            ),
            debounce_ms=100  # Batch progress updates every 100ms
        )
    
    def _on_worker_death(self, worker_id: int):
        """Handle worker death.
        
        Args:
            worker_id: ID of dead worker
        """
        logger.warning(f"Grid callback: worker {worker_id} died")
        
        # Publish event
        self.event_bus.publish(
            WorkerDeathEvent(
                worker_id=worker_id,
                failover_time=0.0  # TODO: Track actual failover time
            )
        )
    
    # ========================================================================
    # UTILITY
    # ========================================================================
    
    def get_stats(self) -> dict:
        """Get combined grid and event bus statistics.
        
        Returns:
            Dict with grid stats and event stats
        """
        grid_stats = self.grid.get_stats()
        event_stats = self.event_bus.get_stats()
        
        return {
            'grid': grid_stats,
            'events': event_stats,
        }
