"""
Event System - Pub/Sub for Grid → UI Communication

Grid emits events when work completes:
- Worker completes file → FileCompletedEvent
- Worker fails file → FileFailedEvent
- Progress updates → ProgressEvent

UI subscribes to events and updates reactively.

Features:
- Type-safe event subscriptions
- Debouncing for rapid events (progress updates)
- Thread-safe event publishing
- Multiple subscribers per event type
"""

import time
import uuid
import threading
import logging
from abc import ABC
from dataclasses import dataclass, field
from typing import Type, Callable, Dict, List, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================================
# EVENT BASE CLASSES
# ============================================================================

@dataclass
class Event(ABC):
    """Base class for all events.
    
    Events represent things that happened in the grid.
    They are immutable notifications sent from grid to UI.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)


# ============================================================================
# GRID EVENTS
# ============================================================================

@dataclass
class FileAddedEvent(Event):
    """File was added to the grid.
    
    Attributes:
        file: ConversionFile that was added
        temp_id: Temporary ID from optimistic update (for reconciliation)
    """
    file: Any = None  # ConversionFile
    temp_id: Optional[str] = None


@dataclass
class FileCompletedEvent(Event):
    """File conversion completed successfully.
    
    Attributes:
        file: ConversionFile that completed
        result: Result dict with output_path, duration, etc.
    """
    file: Any = None  # ConversionFile
    result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FileFailedEvent(Event):
    """File conversion failed.
    
    Attributes:
        file: ConversionFile that failed
        error: Error message
    """
    file: Any = None  # ConversionFile
    error: str = ""


@dataclass
class ProgressEvent(Event):
    """Overall conversion progress update.
    
    Attributes:
        completed: Number of files completed
        total: Total files submitted
        current_file: Optional filename being processed
    """
    completed: int = 0
    total: int = 0
    current_file: Optional[str] = None
    
    @property
    def percent(self) -> float:
        """Calculate progress percentage."""
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100.0


@dataclass
class WorkerDeathEvent(Event):
    """Worker process died unexpectedly.
    
    Attributes:
        worker_id: ID of dead worker
        failover_time: Time taken to failover (seconds)
    """
    worker_id: int = 0
    failover_time: float = 0.0


@dataclass
class LoadSheddingEvent(Event):
    """Load shedding activated/deactivated.
    
    Attributes:
        active: True if shedding active, False if recovered
        available_ram_mb: Current available RAM
    """
    active: bool = False
    available_ram_mb: float = 0.0


@dataclass
class QuarantineEvent(Event):
    """File was quarantined due to repeated failures.
    
    Attributes:
        file: ConversionFile that was quarantined
        failure_count: Number of failures before quarantine
    """
    file: Any = None  # ConversionFile
    failure_count: int = 0


@dataclass
class CircuitBreakerEvent(Event):
    """Circuit breaker state changed.
    
    Attributes:
        file_hash: File that triggered circuit breaker
        state: New state (OPEN, CLOSED, HALF_OPEN)
    """
    file_hash: str = ""
    state: str = ""


# ============================================================================
# EVENT BUS - Pub/Sub Dispatcher
# ============================================================================

class EventBus:
    """Thread-safe pub/sub event dispatcher with debouncing.
    
    Features:
    - Type-safe subscriptions (subscribe to specific event class)
    - Multiple subscribers per event type
    - Debouncing for rapid events (e.g., progress updates)
    - Thread-safe publishing
    - Subscription management
    
    Example:
        >>> bus = EventBus()
        >>> 
        >>> def on_progress(event: ProgressEvent):
        ...     print(f"Progress: {event.percent:.1f}%")
        >>> 
        >>> bus.subscribe(ProgressEvent, on_progress)
        >>> bus.publish(ProgressEvent(completed=50, total=100))
        Progress: 50.0%
    """
    
    def __init__(self):
        """Initialize event bus."""
        # Subscribers: event_type → [callback1, callback2, ...]
        self._subscribers: Dict[Type[Event], List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # Debounce timers: event_type → Timer
        self._debounce_timers: Dict[Type[Event], threading.Timer] = {}
        self._debounce_lock = threading.Lock()
        
        # Statistics
        self.total_published = 0
        self.total_debounced = 0
        
        logger.info("EventBus initialized")
    
    def subscribe(self, event_type: Type[Event], callback: Callable[[Event], None]):
        """Subscribe to an event type.
        
        Args:
            event_type: Class of event to subscribe to
            callback: Function to call when event published
            
        Example:
            >>> bus.subscribe(FileCompletedEvent, on_file_done)
        """
        with self._lock:
            self._subscribers[event_type].append(callback)
        
        logger.debug(f"Subscribed to {event_type.__name__}: {callback.__name__}")
    
    def unsubscribe(self, event_type: Type[Event], callback: Callable):
        """Unsubscribe from an event type.
        
        Args:
            event_type: Event class
            callback: Callback to remove
        """
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from {event_type.__name__}")
    
    def publish(self, event: Event, debounce_ms: int = 0):
        """Publish event to all subscribers.
        
        Args:
            event: Event instance to publish
            debounce_ms: Optional debounce delay (milliseconds)
                        If > 0, events of same type within delay are batched
        
        Example:
            >>> bus.publish(ProgressEvent(completed=50, total=100), debounce_ms=100)
        """
        if debounce_ms > 0:
            self._debounced_publish(event, debounce_ms)
        else:
            self._do_publish(event)
    
    def publish_async(self, event: Event, debounce_ms: int = 0):
        """Publish event in background thread (non-blocking).
        
        Args:
            event: Event to publish
            debounce_ms: Optional debounce delay
        """
        threading.Thread(
            target=lambda: self.publish(event, debounce_ms),
            daemon=True
        ).start()
    
    def get_stats(self) -> dict:
        """Get event bus statistics."""
        with self._lock:
            subscriber_counts = {
                event_type.__name__: len(callbacks)
                for event_type, callbacks in self._subscribers.items()
            }
        
        return {
            'total_published': self.total_published,
            'total_debounced': self.total_debounced,
            'subscriber_counts': subscriber_counts,
        }
    
    # =========================================================================
    # INTERNAL
    # =========================================================================
    
    def _do_publish(self, event: Event):
        """Actually publish event to subscribers."""
        event_type = type(event)
        
        with self._lock:
            callbacks = self._subscribers.get(event_type, [])
        
        if not callbacks:
            logger.debug(f"No subscribers for {event_type.__name__}")
            return
        
        # Call each subscriber
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(
                    f"Event callback failed: {callback.__name__} "
                    f"for {event_type.__name__}: {e}",
                    exc_info=True
                )
        
        self.total_published += 1
        
        logger.debug(
            f"Published {event_type.__name__} to {len(callbacks)} subscribers"
        )
    
    def _debounced_publish(self, event: Event, debounce_ms: int):
        """Publish with debouncing (batch rapid events).
        
        If another event of same type arrives within debounce_ms,
        the previous one is cancelled and only the latest is published.
        """
        event_type = type(event)
        
        with self._debounce_lock:
            # Cancel existing timer for this event type
            if event_type in self._debounce_timers:
                self._debounce_timers[event_type].cancel()
                self.total_debounced += 1
            
            # Schedule new publish
            timer = threading.Timer(
                debounce_ms / 1000.0,
                lambda: self._do_publish(event)
            )
            timer.start()
            self._debounce_timers[event_type] = timer


# ============================================================================
# UTILITY: Event Aggregator
# ============================================================================

class EventAggregator:
    """Aggregates multiple events into a single callback.
    
    Useful for reducing UI update frequency.
    
    Example:
        >>> aggregator = EventAggregator(
        ...     event_types=[FileCompletedEvent, FileFailedEvent],
        ...     callback=update_ui,
        ...     window_ms=500  # Update UI every 500ms max
        ... )
        >>> bus.subscribe(FileCompletedEvent, aggregator.on_event)
        >>> bus.subscribe(FileFailedEvent, aggregator.on_event)
    """
    
    def __init__(
        self,
        event_types: List[Type[Event]],
        callback: Callable[[List[Event]], None],
        window_ms: int = 500
    ):
        """Initialize aggregator.
        
        Args:
            event_types: Types of events to aggregate
            callback: Called with list of events
            window_ms: Aggregation window (milliseconds)
        """
        self.event_types = event_types
        self.callback = callback
        self.window_ms = window_ms
        
        self._events: List[Event] = []
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
    
    def on_event(self, event: Event):
        """Receive an event (call from EventBus callback)."""
        with self._lock:
            self._events.append(event)
            
            # Start timer if not running
            if self._timer is None:
                self._timer = threading.Timer(
                    self.window_ms / 1000.0,
                    self._flush
                )
                self._timer.start()
    
    def _flush(self):
        """Flush accumulated events to callback."""
        with self._lock:
            if self._events:
                try:
                    self.callback(self._events.copy())
                except Exception as e:
                    logger.error(f"Aggregator callback failed: {e}")
                
                self._events.clear()
            
            self._timer = None
