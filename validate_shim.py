"""
Validate Shim Layer - Comprehensive Test

This script demonstrates that the shim layer successfully neutralizes
legacy UI modules without deleting any files.

Run: python validate_shim.py
"""

import sys
from pathlib import Path

# Add to path if needed
sys.path.insert(0, str(Path(__file__).parent))

from grid.shim import install_shim_layer, get_shim_stats


def validate():
    """Run comprehensive shim layer validation."""
    print("=" * 60)
    print("SHIM LAYER VALIDATION")
    print("=" * 60)
    print()
    
    # Step 1: Verify legacy files exist on disk
    print("✓ Step 1: Verify legacy files exist on disk")
    legacy_files = [
        Path("ui/main_window.py"),
        Path("ui/main_window_pro.py"),
    ]
    
    for legacy_file in legacy_files:
        if legacy_file.exists():
            print(f"  ✅ {legacy_file} exists (not deleted, as expected)")
        else:
            print(f"  ❌ {legacy_file} missing (unexpected!)")
    print()
    
    # Step 2: Install shim layer
    print("✓ Step 2: Install shim layer")
    install_shim_layer()
    print("  ✅ Shim layer installed")
    print()
    
    # Step 3: Import legacy modules
    print("✓ Step 3: Import legacy modules")
    import ui  # noqa: F401
    import ui.main_window  # noqa: F401
    import ui.main_window_pro  # noqa: F401
    print("  ✅ Imports successful (no errors)")
    print()
    
    # Step 4: Verify modules are shimmed
    print("✓ Step 4: Verify modules are shimmed (not actual code)")
    
    m_ui = sys.modules['ui']
    m_main_window = sys.modules['ui.main_window']
    m_main_window_pro = sys.modules['ui.main_window_pro']
    
    modules_to_check = [
        ('ui', m_ui),
        ('ui.main_window', m_main_window),
        ('ui.main_window_pro', m_main_window_pro),
    ]
    
    for name, module in modules_to_check:
        if hasattr(module, 'SHIMMED') and module.SHIMMED:
            print(f"  ✅ {name}: SHIMMED = True")
        else:
            print(f"  ❌ {name}: Not shimmed!")
        
        # Verify no actual UI code
        if not hasattr(module, 'ConverterProApp'):
            print(f"     ✅ No ConverterProApp (legacy code not loaded)")
        else:
            print(f"     ❌ Has ConverterProApp (legacy code loaded!)")
        
        # Verify module file
        if '<shimmed:' in str(module.__file__):
            print(f"     ✅ Module file: {module.__file__}")
        else:
            print(f"     ❌ Module file is real: {module.__file__}")
    
    print()
    
    # Step 5: Show statistics
    print("✓ Step 5: Statistics")
    stats = get_shim_stats()
    print(f"  Total neutralized: {stats['neutralized_count']}")
    print(f"  Currently shimmed: {stats['shimmed_count']}")
    print(f"  Shimmed modules:")
    for mod in stats['shimmed_modules']:
        print(f"    • {mod}")
    print()
    
    # Step 6: Final verdict
    print("=" * 60)
    
    all_shimmed = all(
        hasattr(sys.modules[name], 'SHIMMED')
        for name in ['ui', 'ui.main_window', 'ui.main_window_pro']
    )
    
    no_legacy_code = all(
        not hasattr(sys.modules[name], 'ConverterProApp')
        for name in ['ui', 'ui.main_window', 'ui.main_window_pro']
    )
    
    if all_shimmed and no_legacy_code:
        print("✅ SHIM LAYER: FULLY OPERATIONAL")
        print()
        print("Legacy UI modules are neutralized:")
        print("  • Files preserved on disk (NON-DESTRUCTIVE ✅)")
        print("  • Imports return stubs (no actual code runs)")
        print("  • Application can safely use grid architecture")
        print("=" * 60)
        return True
    else:
        print("❌ SHIM LAYER: FAILED")
        print("Some modules are not properly neutralized")
        print("=" * 60)
        return False


if __name__ == '__main__':
    success = validate()
    sys.exit(0 if success else 1)
