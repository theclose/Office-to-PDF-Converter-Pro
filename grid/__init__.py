"""
Autonomous Conversion Grid - Core Module

High-performance, fault-tolerant document conversion system.

Architecture:
- Clustered Priority Queue (Min-Heap) for O(log n) scheduling
- Bloom Filter for O(1) quarantine lookups
- Circuit Breaker pattern for resilience
- Hot Spare worker pool for zero-downtime failover

Phase 1: Core Data Structures
- models.py: Immutable data models
- scheduler.py: Min-Heap scheduler
- quarantine.py: Bloom Filter quarantine

Phase 2: Worker Pool & Circuit Breaker (CURRENT)
- worker.py: Isolated worker processes
- pool.py: Worker pool manager with hot spare
- circuit_breaker.py: Cross-worker failure coordination
- grid.py: High-level grid controller
"""

__version__ = "2.0.0"
__author__ = "VNTime JSC"

# Phase 1 exports
from .models import FileType, ConversionFile, Priority, CircuitBreakerState
from .scheduler import ClusteredPriorityQueue
from .quarantine import BloomFilterQuarantine

# Phase 2 exports
from .worker import WorkerProcess, WorkerConfig
from .pool import WorkerPool, PoolConfig, PoolState
from .circuit_breaker import CircuitBreakerCoordinator, CircuitBreakerConfig
from .grid import ConversionGrid

__all__ = [
    # Phase 1
    'FileType',
    'ConversionFile',
    'Priority',
    'CircuitBreakerState',
    'ClusteredPriorityQueue',
    'BloomFilterQuarantine',
    # Phase 2
    'WorkerProcess',
    'WorkerConfig',
    'WorkerPool',
    'PoolConfig',
    'PoolState',
    'CircuitBreakerCoordinator',
    'CircuitBreakerConfig',
    'ConversionGrid',
]
