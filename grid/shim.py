"""
Shim Layer - Import Hook for Legacy UI Neutralization

Intercepts imports of legacy UI modules and returns stub modules instead.
This allows us to logically isolate legacy code WITHOUT physically deleting files.

Constraint: NON-DESTRUCTIVE refactoring
Solution: sys.meta_path import hook returns empty modules for legacy UI

Usage:
    from grid.shim import install_shim_layer
    install_shim_layer()  # Must be called BEFORE any other imports
    
    # Now legacy imports are neutralized
    import ui.main_window  # Returns stub, no actual code runs
"""

import sys
import logging
import types
from importlib.abc import MetaPathFinder, Loader
from typing import Optional, List

logger = logging.getLogger(__name__)


# ============================================================================
# NEUTRALIZED MODULES
# ============================================================================

# Modules that will be intercepted and replaced with stubs
NEUTRALIZED_MODULES = [
    'ui',  # Package itself (prevents __init__.py imports)
    'ui.main_window',
    'ui.main_window_pro',
    'ui.converter_app',
    'ui.converter_ui',
]


# ============================================================================
# SHIM LOADER
# ============================================================================

class ShimLoader(Loader):
    """Custom loader that returns stub modules.
    
    When Python tries to import a neutralized module, this loader
    creates an empty module with documentation explaining it's been replaced.
    """
    
    def __init__(self, fullname: str):
        """Initialize loader.
        
        Args:
            fullname: Fully qualified module name (e.g., 'ui.main_window')
        """
        self.fullname = fullname
    
    def create_module(self, spec):
        """Create the module object (Python 3.4+ import protocol).
        
        Returns None to use default module creation.
        """
        return None  # Use default module creation
    
    def exec_module(self, module):
        """Execute module initialization (Python 3.4+ import protocol).
        
        This is where we populate the stub module.
        """
        # Add module metadata
        module.__file__ = f"<shimmed: {self.fullname}>"
        module.__package__ = self.fullname.rpartition('.')[0]
        
        # Add documentation
        module.__doc__ = f"""
╔══════════════════════════════════════════════════════════════╗
║                  LEGACY MODULE NEUTRALIZED                   ║
╚══════════════════════════════════════════════════════════════╝

This module ({self.fullname}) has been replaced by the Grid architecture.

All functionality is now provided by:
  • grid.ConversionGrid (core engine)
  • grid.reactor.ReactorApp (UI)

Legacy code is preserved but inactive. No files were deleted.

For migration guide, see: docs/migration.md
"""
        
        # Add stub attributes to prevent AttributeError
        module.SHIMMED = True
        module.LEGACY_MODULE = True
        module.__all__ = []  # Export nothing
        
        logger.info(f"🛡️ Shim Layer: Neutralized import of '{self.fullname}'")
    
    # Fallback for older Python (deprecated but may be needed)
    def load_module(self, fullname: str) -> types.ModuleType:
        """Create and return stub module (deprecated API, fallback only)."""
        # Create empty module
        mod = types.ModuleType(fullname)
        mod.__loader__ = self
        mod.__file__ = f"<shimmed: {fullname}>"
        mod.__package__ = fullname.rpartition('.')[0]
        
        # Add documentation
        mod.__doc__ = f"""
╔══════════════════════════════════════════════════════════════╗
║                  LEGACY MODULE NEUTRALIZED                   ║
╚══════════════════════════════════════════════════════════════╝

This module ({fullname}) has been replaced by the Grid architecture.
"""
        
        # Add stub attributes
        mod.SHIMMED = True
        mod.LEGACY_MODULE = True
        
        # Register in sys.modules
        sys.modules[fullname] = mod
        
        logger.info(f"🛡️ Shim Layer: Neutralized import of '{fullname}' (legacy API)")
        
        return mod


# ============================================================================
# META PATH FINDER
# ============================================================================

class LegacyUIShim(MetaPathFinder):
    """Meta path finder that intercepts legacy UI imports.
    
    Installed at the front of sys.meta_path, this finder is consulted
    before Python's normal import machinery. When a neutralized module
    is imported, it creates a stub module instead of loading the actual code.
    """
    
    def __init__(self, neutralized_modules: List[str]):
        """Initialize shim finder.
        
        Args:
            neutralized_modules: List of module names to intercept
        """
        self.neutralized_modules = set(neutralized_modules)
    
    def find_spec(self, fullname: str, path, target=None):
        """Find module spec (modern import API).
        
        Args:
            fullname: Fully qualified module name
            path: Package search path
            target: Target module (unused)
            
        Returns:
            ModuleSpec for shimmed module, None otherwise
        """
        if fullname in self.neutralized_modules:
            logger.debug(f"Shim Layer: Intercepting '{fullname}'")
            
            # Create spec for shimmed module
            from importlib.machinery import ModuleSpec
            from importlib.util import spec_from_loader
            
            loader = ShimLoader(fullname)
            spec = spec_from_loader(fullname, loader)
            
            return spec
        
        return None
    
    def find_module(self, fullname: str, path: Optional[List[str]] = None):
        """Deprecated fallback for older Python versions."""
        if fullname in self.neutralized_modules:
            logger.debug(f"Shim Layer: Intercepting '{fullname}' (legacy API)")
            return ShimLoader(fullname)
        
        return None


# ============================================================================
# INSTALLATION
# ============================================================================

_shim_installed = False


def install_shim_layer(neutralized_modules: Optional[List[str]] = None) -> bool:
    """Install shim layer to neutralize legacy UI.
    
    CRITICAL: Must be called BEFORE importing any legacy modules.
    Typically called at the very top of the entry point.
    
    Strategy:
    1. Pre-populate sys.modules with stub modules
    2. Install meta path finder as backup
    
    This ensures Python finds our stub in sys.modules FIRST,
    before any finder even attempts to load from disk.
    
    Args:
        neutralized_modules: Optional list of modules to neutralize
                           (defaults to NEUTRALIZED_MODULES)
    
    Returns:
        True if installed, False if already installed
        
    Example:
        >>> from grid.shim import install_shim_layer
        >>> install_shim_layer()  # FIRST line in main.py
        >>> 
        >>> # Now safe to import grid
        >>> from grid import ConversionGrid
        >>> 
        >>> # Legacy imports return stubs
        >>> import ui.main_window  # Returns stub, not actual module
    """
    global _shim_installed
    
    if _shim_installed:
        logger.warning("Shim layer already installed")
        return False
    
    # Use default if not provided
    if neutralized_modules is None:
        neutralized_modules = NEUTRALIZED_MODULES
    
    # ========================================================================
    # STRATEGY 1: Pre-populate sys.modules (PRIMARY)
    # ========================================================================
    # This is the most reliable approach. By creating stub modules
    # in sys.modules BEFORE any import, we guarantee Python finds
    # our stub first (sys.modules is checked before any finder).
    
    for module_name in neutralized_modules:
        if module_name not in sys.modules:
            # Create stub module
            stub = types.ModuleType(module_name)
            stub.__loader__ = None
            stub.__file__ = f"<shimmed: {module_name}>"
            stub.__package__ = module_name.rpartition('.')[0]
            stub.__path__ = []  # Empty path (no submodules)
            
            # Add documentation
            stub.__doc__ = f"""
╔══════════════════════════════════════════════════════════════╗
║                  LEGACY MODULE NEUTRALIZED                   ║
╚══════════════════════════════════════════════════════════════╝

This module ({module_name}) has been replaced by the Grid architecture.

All functionality is now provided by:
  • grid.ConversionGrid (core engine)
  • grid.reactor.ReactorApp (UI)

Legacy code is preserved but inactive. No files were deleted.

For migration guide, see: docs/migration.md
"""
            
            # Add stub attributes to prevent AttributeError
            stub.SHIMMED = True
            stub.LEGACY_MODULE = True
            stub.__all__ = []  # Export nothing
            
            # Register in sys.modules
            sys.modules[module_name] = stub
            
            logger.debug(f"Pre-populated sys.modules with stub: {module_name}")
    
    # ========================================================================
    # STRATEGY 2: Install meta path finder (BACKUP)
    # ========================================================================
    # This catches any edge cases where a module might be removed from
    # sys.modules and re-imported.
    
    shim_finder = LegacyUIShim(neutralized_modules)
    sys.meta_path.insert(0, shim_finder)
    
    _shim_installed = True
    
    logger.info(
        f"🛡️ Shim Layer installed. "
        f"Neutralized {len(neutralized_modules)} legacy modules."
    )
    logger.debug(f"Neutralized modules: {', '.join(neutralized_modules)}")
    
    return True


def uninstall_shim_layer():
    """Remove shim layer (for testing or rollback).
    
    Returns:
        True if uninstalled, False if wasn't installed
    """
    global _shim_installed
    
    if not _shim_installed:
        return False
    
    # Remove all LegacyUIShim instances from meta_path
    sys.meta_path = [
        finder for finder in sys.meta_path
        if not isinstance(finder, LegacyUIShim)
    ]
    
    # Clear shimmed modules from sys.modules
    for module_name in list(sys.modules.keys()):
        if module_name in NEUTRALIZED_MODULES:
            mod = sys.modules[module_name]
            if hasattr(mod, 'SHIMMED'):
                del sys.modules[module_name]
                logger.debug(f"Removed shimmed module: {module_name}")
    
    _shim_installed = False
    logger.info("🛡️ Shim Layer uninstalled")
    
    return True


def is_shim_installed() -> bool:
    """Check if shim layer is currently installed.
    
    Returns:
        True if installed, False otherwise
    """
    return _shim_installed


def verify_neutralization(module_name: str) -> bool:
    """Verify that a module has been successfully neutralized.
    
    Args:
        module_name: Module to check
        
    Returns:
        True if module is neutralized, False otherwise
    """
    if module_name not in sys.modules:
        return False
    
    mod = sys.modules[module_name]
    return hasattr(mod, 'SHIMMED') and mod.SHIMMED


# ============================================================================
# DIAGNOSTICS
# ============================================================================

def get_shim_stats() -> dict:
    """Get statistics about shimmed modules.
    
    Returns:
        Dict with shim layer statistics
    """
    shimmed = []
    
    for module_name in NEUTRALIZED_MODULES:
        if module_name in sys.modules:
            mod = sys.modules[module_name]
            if hasattr(mod, 'SHIMMED'):
                shimmed.append(module_name)
    
    return {
        'installed': _shim_installed,
        'neutralized_count': len(NEUTRALIZED_MODULES),
        'shimmed_count': len(shimmed),
        'shimmed_modules': shimmed,
    }
