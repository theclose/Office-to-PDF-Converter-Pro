"""
Test Suite for Shim Layer

Verifies that import hook correctly neutralizes legacy UI modules.
"""

import pytest
import sys
from unittest.mock import patch

from grid.shim import (
    install_shim_layer,
    uninstall_shim_layer,
    is_shim_installed,
    verify_neutralization,
    get_shim_stats,
    NEUTRALIZED_MODULES
)


class TestShimLayer:
    """Test shim layer functionality."""
    
    def setup_method(self):
        """Setup before each test."""
        # Ensure clean state
        if is_shim_installed():
            uninstall_shim_layer()
    
    def teardown_method(self):
        """Cleanup after each test."""
        if is_shim_installed():
            uninstall_shim_layer()
    
    def test_installation(self):
        """Test shim layer installation."""
        # Initially not installed
        assert not is_shim_installed()
        
        # Install
        result = install_shim_layer()
        assert result is True
        assert is_shim_installed()
        
        # Install again (should return False)
        result = install_shim_layer()
        assert result is False
    
    def test_uninstallation(self):
        """Test shim layer uninstallation."""
        install_shim_layer()
        assert is_shim_installed()
        
        # Uninstall
        result = uninstall_shim_layer()
        assert result is True
        assert not is_shim_installed()
        
        # Uninstall again
        result = uninstall_shim_layer()
        assert result is False
    
    def test_legacy_import_neutralization(self):
        """Test that legacy modules are neutralized."""
        install_shim_layer()
        
        # Import legacy module directly
        import ui.main_window  # noqa: F401
        
        # Get module from sys.modules
        import sys
        m = sys.modules['ui.main_window']
        
        # Should be shimmed
        assert hasattr(m, 'SHIMMED')
        assert m.SHIMMED is True
        assert verify_neutralization('ui.main_window')
        
        # Should have documentation
        assert 'LEGACY MODULE NEUTRALIZED' in m.__doc__
        
        # Should not have actual UI code
        assert not hasattr(m, 'ConverterProApp')
    
    def test_multiple_legacy_imports(self):
        """Test neutralizing multiple modules."""
        install_shim_layer()
        
        # Import multiple legacy modules
        import ui.main_window  # noqa: F401
        import ui.main_window_pro  # noqa: F401
        
        # Both should be shimmed
        assert verify_neutralization('ui.main_window')
        assert verify_neutralization('ui.main_window_pro')
    
    def test_normal_imports_unaffected(self):
        """Test that normal imports still work."""
        install_shim_layer()
        
        # Normal imports should work
        import os
        import sys
        from grid.models import ConversionFile
        
        # Should NOT be shimmed
        assert not hasattr(os, 'SHIMMED')
        assert not hasattr(sys, 'SHIMMED')
        assert not hasattr(ConversionFile, 'SHIMMED')
    
    def test_shim_stats(self):
        """Test shim statistics."""
        install_shim_layer()
        
        # Import some modules
        import ui.main_window  # noqa: F401
        import ui.main_window_pro  # noqa: F401
        
        # Get stats
        stats = get_shim_stats()
        
        assert stats['installed'] is True
        assert stats['neutralized_count'] >= 2
        assert stats['shimmed_count'] >= 2
        assert 'ui.main_window' in stats['shimmed_modules']
        assert 'ui.main_window_pro' in stats['shimmed_modules']
    
    def test_uninstall_clears_shimmed_modules(self):
        """Test that uninstall removes shimmed modules from sys.modules."""
        install_shim_layer()
        
        # Import legacy module
        import ui.main_window
        assert 'ui.main_window' in sys.modules
        
        # Uninstall
        uninstall_shim_layer()
        
        # Should be removed from sys.modules
        assert 'ui.main_window' not in sys.modules
    
    def test_custom_neutralized_modules(self):
        """Test installing shim with custom module list."""
        custom_modules = ['custom.module1', 'custom.module2']
        
        install_shim_layer(neutralized_modules=custom_modules)
        
        # Should intercept custom modules
        # (Can't actually import them unless they exist, but shim should be configured)
        stats = get_shim_stats()
        assert stats['installed'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
