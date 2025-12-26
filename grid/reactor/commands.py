"""
Command Pattern - Decouple UI actions from Grid execution

All user actions flow through Commands:
- User clicks button → Create Command → Post to CommandBus
- CommandBus executes async in background thread
- UI never blocks (O(1) post operation)

Commands are:
- Immutable (dataclass frozen)
- Serializable (for replay/undo)
- Validatable (pre-execution checks)
- Traceable (with unique ID and timestamp)
"""

import time
import uuid
import queue
import threading
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List
from pathlib import Path
from concurrent.futures import Future
from collections import deque

logger = logging.getLogger(__name__)


# ============================================================================
# COMMAND BASE CLASSES
# ============================================================================

@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class ExecutionContext:
    """Context provided to commands during execution.
    
    Contains references to grid, state, and other services.
    """
    grid: Any  # ConversionGrid instance
    optimistic_state: Optional[Any] = None  # OptimisticState
    event_bus: Optional[Any] = None  # EventBus
    

@dataclass(frozen=True)
class Command(ABC):
    """Base class for all commands.
    
    Commands represent user actions in an immutable, executable form.
    They decouple UI from business logic via the Command Pattern.
    
    Example:
        >>> cmd = AddFilesCommand(file_paths=["doc1.docx", "doc2.docx"])
        >>> future = command_bus.execute_async(cmd)
        >>> result = future.result(timeout=5.0)
    """
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    
    @abstractmethod
    def execute(self, context: ExecutionContext) -> CommandResult:
        """Execute command with given context.
        
        Args:
            context: Execution context with grid, state, services
            
        Returns:
            CommandResult with success/failure and data
        """
        pass
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Pre-execution validation.
        
        Returns:
            (is_valid, error_message)
        """
        return (True, None)


# ============================================================================
# CONCRETE COMMANDS
# ============================================================================

@dataclass(frozen=True)
class AddFilesCommand(Command):
    """Add files to conversion queue.
    
    Attributes:
        file_paths: List of absolute file paths to add
    """
    file_paths: tuple[str, ...] = ()  # Tuple for immutability
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate file paths exist."""
        if not self.file_paths:
            return (False, "No file paths provided")
        
        missing = [p for p in self.file_paths if not Path(p).exists()]
        if missing:
            return (False, f"{len(missing)} files not found")
        
        return (True, None)
    
    def execute(self, context: ExecutionContext) -> CommandResult:
        """Execute file addition."""
        start_time = time.time()
        
        try:
            # Import ConversionFile here to avoid circular imports
            from grid.models import ConversionFile
            
            # Create ConversionFile objects
            files = []
            errors = []
            
            for path in self.file_paths:
                try:
                    file = ConversionFile(path)
                    files.append(file)
                except Exception as e:
                    errors.append(f"{Path(path).name}: {e}")
            
            # Enqueue to grid
            if files:
                enqueued = context.grid.enqueue_batch(files)
                
                return CommandResult(
                    success=True,
                    data={
                        'enqueued': enqueued,
                        'files': files,
                        'errors': errors
                    },
                    duration=time.time() - start_time
                )
            else:
                return CommandResult(
                    success=False,
                    error=f"No valid files: {', '.join(errors)}",
                    duration=time.time() - start_time
                )
                
        except Exception as e:
            logger.error(f"AddFilesCommand failed: {e}")
            return CommandResult(
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )


@dataclass(frozen=True)
class RemoveFilesCommand(Command):
    """Remove files from queue (before conversion starts).
    
    Attributes:
        file_hashes: File hashes to remove
    """
    file_hashes: tuple[str, ...] = ()
    
    def execute(self, context: ExecutionContext) -> CommandResult:
        """Execute file removal."""
        # Note: This would require adding remove capability to grid/scheduler
        # For now, return not implemented
        return CommandResult(
            success=False,
            error="Remove not yet implemented in grid layer"
        )


@dataclass(frozen=True)
class ClearQueueCommand(Command):
    """Clear all pending files from queue."""
    
    def execute(self, context: ExecutionContext) -> CommandResult:
        """Execute queue clear."""
        start_time = time.time()
        
        try:
            # Clear scheduler
            cleared = context.grid.scheduler.clear()
            
            return CommandResult(
                success=True,
                data={'cleared': cleared},
                duration=time.time() - start_time
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )


@dataclass(frozen=True)
class StartConversionCommand(Command):
    """Start conversion process (if not already running)."""
    
    def execute(self, context: ExecutionContext) -> CommandResult:
        """Execute conversion start."""
        # Grid auto-processes queued files, so this is mostly a no-op
        # Just verify grid is active
        if context.grid.pool.state.value != 'active':
            return CommandResult(
                success=False,
                error="Grid not in active state"
            )
        
        return CommandResult(
            success=True,
            data={'message': 'Conversion running'}
        )


@dataclass(frozen=True)
class StopConversionCommand(Command):
    """Stop conversion process gracefully."""
    force: bool = False  # Force immediate stop vs graceful
    
    def execute(self, context: ExecutionContext) -> CommandResult:
        """Execute conversion stop."""
        start_time = time.time()
        
        try:
            # Clear pending queue
            cleared = context.grid.scheduler.clear()
            
            # If force, could terminate workers (not implemented yet)
            if self.force:
                logger.warning("Force stop not yet implemented")
            
            return CommandResult(
                success=True,
                data={'cleared_pending': cleared},
                duration=time.time() - start_time
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )


@dataclass(frozen=True)
class ResetCircuitBreakerCommand(Command):
    """Reset circuit breaker for a file (allow retry).
    
    Attributes:
        file_hash: File hash to reset
    """
    file_hash: str = ""
    
    def execute(self, context: ExecutionContext) -> CommandResult:
        """Execute circuit breaker reset."""
        try:
            # Reset in circuit breaker coordinator
            # Would need to pass ConversionFile, but we only have hash
            # This is a limitation - need to refactor coordinator to accept hash
            
            return CommandResult(
                success=False,
                error="Reset by hash not yet implemented in coordinator"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=str(e)
            )


# =============================================================================
# COMMAND BUS - Async Dispatcher
# ============================================================================

class CommandBus:
    """Asynchronous command dispatcher with queue and history.
    
    Features:
    - O(1) command posting (never blocks UI)
    - Background thread executes commands
    - Future-based result retrieval
    - Command history for replay/debugging
    - Error handling and logging
    
    Example:
        >>> bus = CommandBus(context)
        >>> future = bus.execute_async(AddFilesCommand([...]))
        >>> result = future.result(timeout=5.0)
        >>> print(f"Success: {result.success}")
    """
    
    def __init__(self, context: ExecutionContext):
        """Initialize command bus.
        
        Args:
            context: Execution context for commands
        """
        self.context = context
        
        # Command queue (thread-safe)
        self._queue: queue.Queue = queue.Queue()
        
        # Command history (last 100 commands)
        self._history: deque = deque(maxlen=100)
        self._history_lock = threading.Lock()
        
        # Executor thread
        self._stop_event = threading.Event()
        self._executor_thread = threading.Thread(
            target=self._execute_loop,
            daemon=True,
            name="CommandBusExecutor"
        )
        self._executor_thread.start()
        
        # Statistics
        self.total_executed = 0
        self.total_failed = 0
        
        logger.info("CommandBus started")
    
    def execute_async(self, command: Command) -> Future:
        """Post command for async execution.
        
        Complexity: O(1) - Just queue.put()
        Never blocks UI thread!
        
        Args:
            command: Command to execute
            
        Returns:
            Future that will contain CommandResult
        """
        # Validate command
        is_valid, error = command.validate()
        if not is_valid:
            # Return failed future immediately
            future = Future()
            future.set_result(CommandResult(
                success=False,
                error=f"Validation failed: {error}"
            ))
            return future
        
        # Create future
        future = Future()
        
        # Post to queue
        self._queue.put((command, future))
        
        logger.debug(f"Posted command: {command.__class__.__name__} ({command.command_id})")
        
        return future
    
    def execute_sync(self, command: Command, timeout: float = 30.0) -> CommandResult:
        """Execute command synchronously (blocks until complete).
        
        Args:
            command: Command to execute
            timeout: Maximum seconds to wait
            
        Returns:
            CommandResult
            
        Raises:
            TimeoutError: If command doesn't complete in time
        """
        future = self.execute_async(command)
        return future.result(timeout=timeout)
    
    def get_history(self, count: int = 10) -> List[tuple[Command, CommandResult]]:
        """Get recent command history.
        
        Args:
            count: Number of recent commands to return
            
        Returns:
            List of (command, result) tuples
        """
        with self._history_lock:
            return list(self._history)[-count:]
    
    def get_stats(self) -> dict:
        """Get command bus statistics."""
        return {
            'total_executed': self.total_executed,
            'total_failed': self.total_failed,
            'queue_size': self._queue.qsize(),
            'history_size': len(self._history),
        }
    
    def shutdown(self, timeout: float = 5.0):
        """Shutdown command bus gracefully.
        
        Args:
            timeout: Max seconds to wait for pending commands
        """
        logger.info("CommandBus shutdown initiated")
        self._stop_event.set()
        
        # Wait for executor thread
        self._executor_thread.join(timeout=timeout)
        
        if self._executor_thread.is_alive():
            logger.warning("CommandBus executor did not stop cleanly")
    
    # =========================================================================
    # INTERNAL
    # =========================================================================
    
    def _execute_loop(self):
        """Worker thread that executes commands."""
        logger.info("Command executor thread started")
        
        while not self._stop_event.is_set():
            try:
                # Get next command (with timeout to check stop event)
                try:
                    command, future = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Execute command
                try:
                    result = command.execute(self.context)
                    future.set_result(result)
                    
                    # Update stats
                    if result.success:
                        self.total_executed += 1
                    else:
                        self.total_failed += 1
                    
                    # Add to history
                    with self._history_lock:
                        self._history.append((command, result))
                    
                    logger.debug(
                        f"Executed {command.__class__.__name__}: "
                        f"{'success' if result.success else 'failed'} "
                        f"({result.duration:.3f}s)"
                    )
                    
                except Exception as e:
                    # Command execution raised exception
                    logger.error(f"Command execution error: {e}", exc_info=True)
                    
                    result = CommandResult(
                        success=False,
                        error=f"Execution exception: {e}"
                    )
                    future.set_exception(e)
                    self.total_failed += 1
                    
                    with self._history_lock:
                        self._history.append((command, result))
                
            except Exception as e:
                logger.error(f"Command bus error: {e}", exc_info=True)
        
        logger.info("Command executor thread stopped")
