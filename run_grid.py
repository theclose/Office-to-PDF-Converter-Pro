"""
Autonomous Conversion Grid - Production Entry Point

This is the new, hardened entry point using the grid architecture.

CRITICAL: Shim layer is installed FIRST to neutralize legacy UI.

Usage:
    python run_grid.py
"""

import sys
import logging
import time
from pathlib import Path

# ============================================================================
# STEP 1: Install Shim Layer (MUST BE FIRST)
# ============================================================================

# Add grid to path if needed
sys.path.insert(0, str(Path(__file__).parent))

from grid.shim import install_shim_layer

# Install shim BEFORE any other imports
install_shim_layer()
print("✅ Shim Layer installed - Legacy UI neutralized")

# ============================================================================
# STEP 2: Import Grid Components
# ============================================================================

from grid import ConversionGrid
from grid.reactor.commands import CommandBus, ExecutionContext
from grid.reactor.events import EventBus

# ============================================================================
# STEP 3: Setup Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('grid.log')
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for Autonomous Conversion Grid."""
    logger.info("="*60)
    logger.info("Autonomous Conversion Grid - Starting")
    logger.info("="*60)
    
    try:
        # Create grid
        logger.info("Initializing ConversionGrid...")
        grid = ConversionGrid(
            num_workers=4,
            enable_hot_spare=True,
            on_file_complete=lambda f, r: logger.info(f"✓ Completed: {f.filename}"),
            on_file_error=lambda f, e: logger.error(f"✗ Failed: {f.filename} - {e}")
        )
        
        # Start grid
        logger.info("Starting worker pool...")
        grid.start()
        
        # Display status
        stats = grid.get_stats()
        logger.info(f"Grid operational: {stats['pool']['active_workers']} workers active")
        if stats['pool']['hot_spare_ready']:
            logger.info("Hot spare ready for failover")
        
        # TODO: Launch Reactor UI (Phase 3)
        # For now, run in command-line mode
        logger.info("")
        logger.info("="*60)
        logger.info("Grid is running. Press Ctrl+C to stop.")
        logger.info("="*60)
        logger.info("")
        logger.info("Next: Implement Reactor UI (Phase 3) for graphical interface")
        
        # Keep alive
        try:
            while True:
                time.sleep(5)
                
                # Periodic stats (optional)
                stats = grid.get_stats()
                if stats['total_enqueued'] > 0:
                    logger.info(
                        f"Progress: {stats['total_completed']}/{stats['total_enqueued']} "
                        f"({stats['success_rate']:.1f}% success)"
                    )
        
        except KeyboardInterrupt:
            logger.info("")
            logger.info("Shutdown requested by user")
        
        # Graceful shutdown
        logger.info("Shutting down grid...")
        grid.shutdown(timeout=30)
        
        # Final stats
        stats = grid.get_stats()
        logger.info("")
        logger.info("="*60)
        logger.info("Shutdown complete. Final statistics:")
        logger.info(f"  Total processed: {stats['total_completed'] + stats['total_failed']}")
        logger.info(f"  Successful: {stats['total_completed']}")
        logger.info(f"  Failed: {stats['total_failed']}")
        logger.info(f"  Success rate: {stats['success_rate']:.1f}%")
        logger.info(f"  Uptime: {stats['uptime_seconds']:.0f}s")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
