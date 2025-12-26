"""
Performance Benchmark: Legacy UI vs Reactor UI
Measures startup time and basic initialization.
"""

import time
import sys
import os

# Add path - scripts is inside office_converter, so go up one level
script_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.dirname(script_dir)  # office_converter
parent_dir = os.path.dirname(package_dir)  # Auto
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def benchmark_legacy_import():
    """Benchmark time to import legacy UI module."""
    start = time.perf_counter()
    from office_converter.ui.main_window_pro import ConverterProApp
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_reactor_import():
    """Benchmark time to import Reactor UI module."""
    start = time.perf_counter()
    from office_converter.grid.reactor.reactor_app import ReactorApp
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_grid_init():
    """Benchmark time to initialize ConversionGrid (no workers)."""
    start = time.perf_counter()
    from office_converter.grid import ConversionGrid
    # Just import, don't start workers
    elapsed = time.perf_counter() - start
    return elapsed


def main():
    print("=" * 60)
    print("PERFORMANCE BENCHMARK: Office Converter Pro")
    print("=" * 60)
    print()
    
    # Benchmark imports
    print("1. Module Import Benchmark")
    print("-" * 40)
    
    legacy_time = benchmark_legacy_import()
    print(f"   Legacy UI (main_window_pro): {legacy_time*1000:.1f} ms")
    
    reactor_time = benchmark_reactor_import()
    print(f"   Reactor UI (reactor_app):    {reactor_time*1000:.1f} ms")
    
    grid_time = benchmark_grid_init()
    print(f"   Grid Core (ConversionGrid):  {grid_time*1000:.1f} ms")
    
    print()
    print("2. Comparison")
    print("-" * 40)
    
    if reactor_time < legacy_time:
        improvement = ((legacy_time - reactor_time) / legacy_time) * 100
        print(f"   ✅ Reactor is {improvement:.1f}% faster than Legacy")
    else:
        overhead = ((reactor_time - legacy_time) / legacy_time) * 100
        print(f"   ⚠️ Reactor has {overhead:.1f}% overhead vs Legacy")
    
    print()
    print("3. Summary")
    print("-" * 40)
    print(f"   Total Legacy load:  {legacy_time*1000:.1f} ms")
    print(f"   Total Reactor load: {reactor_time*1000:.1f} ms")
    print(f"   Grid init overhead: {grid_time*1000:.1f} ms")
    print()
    print("=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
