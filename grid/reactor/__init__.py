"""
Reactor UI Module - Event-Driven Architecture

Phase 3: Decoupled UI with Command Pattern and Event Bus.

Components:
- commands.py: Command Pattern (UI actions → Commands → Grid)
- events.py: Event Bus (Grid results → Events → UI)
- virtual_list.py: Virtual scrolling list widget
- optimistic.py: Optimistic state management
- bridge.py: Grid ↔ UI integration
- reactor_app.py: Main application window
"""

__version__ = "3.0.0"
__author__ = "TungDo"

from .commands import Command, CommandBus, CommandResult, ExecutionContext
from .events import Event, EventBus
from .reactor_app import ReactorApp

__all__ = [
    'Command',
    'CommandBus',
    'CommandResult',
    'ExecutionContext',
    'Event',
    'EventBus',
    'ReactorApp',
]
