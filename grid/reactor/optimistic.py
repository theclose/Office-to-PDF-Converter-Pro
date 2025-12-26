"""
Optimistic State Management - Instant UI Feedback

Provides immediate UI updates while background operations complete.

Flow:
1. User action → Create optimistic item with temp ID
2. UI shows optimistic state immediately ("Validating...")
3. Command executes in background
4. Event published with real data
5. Reconcile: temp ID → real item

Example:
    >>> state = OptimisticState()
    >>> temp_id = state.add_optimistic({"name": "file.docx", "status": "validating"})
    >>> # UI shows "validating" immediately
    >>> 
    >>> # Later, when command completes:
    >>> real_file = ConversionFile("file.docx")
    >>> state.reconcile(temp_id, real_file)
    >>> # UI updates to show real file
"""

import uuid
import time
import logging
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OptimisticItem:
    """Temporary item shown during optimistic update."""
    temp_id: str
    data: Any
    created_at: float = field(default_factory=time.time)
    reconciled: bool = False


class OptimisticState:
    """Manages optimistic UI updates with reconciliation.
    
    Tracks temporary items until they are reconciled with real data.
    Prevents race conditions between UI updates and background execution.
    
    Example:
        >>> state = OptimisticState()
        >>> 
        >>> # User adds files
        >>> temp_id = state.add_optimistic({
        ...     'filename': 'doc.docx',
        ...     'status': 'validating'
        ... })
        >>> 
        >>> # UI shows temp item immediately
        >>> items = state.get_merged_items(real_items=[])
        >>> assert items[0]['status'] == 'validating'
        >>> 
        >>> # Command completes, real file created
        >>> real_file = ConversionFile('doc.docx')
        >>> state.reconcile(temp_id, real_file)
        >>> 
        >>> # UI now shows real file
        >>> items = state.get_merged_items(real_items=[real_file])
        >>> assert real_file in items
    """
    
    def __init__(self):
        """Initialize optimistic state manager."""
        self._optimistic_items: Dict[str, OptimisticItem] = {}
        self._reconciliation_map: Dict[str, Any] = {}  # temp_id → real_item
        self._lock = threading.Lock()
        
        # Statistics
        self.total_optimistic = 0
        self.total_reconciled = 0
        self.total_failed = 0
    
    def add_optimistic(self, data: Any) -> str:
        """Add optimistic item.
        
        Args:
            data: Temporary item data (dict or object)
            
        Returns:
            Temporary ID for this item
        """
        temp_id = f"temp-{uuid.uuid4().hex[:8]}"
        
        with self._lock:
            item = OptimisticItem(
                temp_id=temp_id,
                data=data
            )
            self._optimistic_items[temp_id] = item
            self.total_optimistic += 1
        
        logger.debug(f"Added optimistic item: {temp_id}")
        return temp_id
    
    def reconcile(self, temp_id: str, real_item: Any):
        """Reconcile optimistic item with real data.
        
        Args:
            temp_id: Temporary ID from add_optimistic()
            real_item: Real item from grid
        """
        with self._lock:
            if temp_id in self._optimistic_items:
                # Mark as reconciled
                self._optimistic_items[temp_id].reconciled = True
                self._reconciliation_map[temp_id] = real_item
                self.total_reconciled += 1
                
                logger.debug(f"Reconciled {temp_id} → {real_item}")
            else:
                logger.warning(f"Reconcile failed: temp_id {temp_id} not found")
    
    def mark_failed(self, temp_id: str, error: str):
        """Mark optimistic item as failed.
        
        Args:
            temp_id: Temporary ID
            error: Error message
        """
        with self._lock:
            if temp_id in self._optimistic_items:
                item = self._optimistic_items[temp_id]
                item.reconciled = True
                
                # Store error in reconciliation map
                self._reconciliation_map[temp_id] = {
                    'error': error,
                    'status': 'failed'
                }
                self.total_failed += 1
                
                logger.debug(f"Marked {temp_id} as failed: {error}")
    
    def remove_optimistic(self, temp_id: str):
        """Remove optimistic item (cleanup after reconciliation).
        
        Args:
            temp_id: Temporary ID to remove
        """
        with self._lock:
            if temp_id in self._optimistic_items:
                del self._optimistic_items[temp_id]
            if temp_id in self._reconciliation_map:
                del self._reconciliation_map[temp_id]
    
    def get_merged_items(self, real_items: List[Any]) -> List[Any]:
        """Get combined list of real items + un-reconciled optimistic items.
        
        Args:
            real_items: List of real items from grid
            
        Returns:
            Merged list (optimistic first, then real)
        """
        with self._lock:
            merged = []
            
            # Add un-reconciled optimistic items first (show at top)
            for item in self._optimistic_items.values():
                if not item.reconciled:
                    merged.append(item.data)
            
            # Add real items
            merged.extend(real_items)
            
            return merged
    
    def cleanup_old(self, max_age_seconds: float = 60.0):
        """Remove old reconciled items.
        
        Args:
            max_age_seconds: Maximum age to keep reconciled items
        """
        current_time = time.time()
        
        with self._lock:
            to_remove = []
            
            for temp_id, item in self._optimistic_items.items():
                if item.reconciled:
                    age = current_time - item.created_at
                    if age > max_age_seconds:
                        to_remove.append(temp_id)
            
            for temp_id in to_remove:
                self.remove_optimistic(temp_id)
            
            if to_remove:
                logger.debug(f"Cleaned up {len(to_remove)} old optimistic items")
    
    def get_stats(self) -> dict:
        """Get optimistic state statistics.
        
        Returns:
            Dict with statistics
        """
        with self._lock:
            unreconciled = sum(
                1 for item in self._optimistic_items.values()
                if not item.reconciled
            )
            
            return {
                'total_optimistic': self.total_optimistic,
                'total_reconciled': self.total_reconciled,
                'total_failed': self.total_failed,
                'current_unreconciled': unreconciled,
            }
