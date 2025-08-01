#!/usr/bin/env python3
"""
Flow Meter Startup Script
Simple script to start flow meter monitoring on Raspberry Pi.
This will automatically detect tapped kegs and start monitoring their flow meters.
"""

import sys
import os
import time
import signal
import logging
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

try:
    from flow_meter_integration import MultiTapFlowSystem
    from keg_app import SessionLocal, Keg, KegStatus
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running this on a Raspberry Pi with all dependencies installed.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('flow_meter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_current_tap_config():
    """
    Get current tap configuration based on what kegs are tapped.
    Returns configuration for active taps only.
    """
    try:
        session = SessionLocal()
        tapped_kegs = session.query(Keg).filter(Keg.status == KegStatus.TAPPED).all()
        session.close()
        
        # Default GPIO pin mapping for 4 taps
        # Adjust these GPIO pins based on your actual wiring
        gpio_pins = {1: 4, 2: 17, 3: 27, 4: 22}
        
        tap_configs = []
        for keg in tapped_kegs:
            if keg.tap_position and keg.tap_position in gpio_pins:
                tap_configs.append({
                    "tap_number": keg.tap_position,
                    "gpio_pin": gpio_pins[keg.tap_position],
                    "pulses_per_liter": 450.0  # Default for YF-S201, adjust as needed
                })
                logger.info(f"Found tapped keg: {keg.name} at tap {keg.tap_position}")
        
        return tap_configs
    except Exception as e:
        logger.error(f"Error getting tap configuration: {e}")
        return []

def main():
    """Main startup function."""
    logger.info("=== Flow Meter System Starting ===")
    
    # Check if we're on a Raspberry Pi
    try:
        import RPi.GPIO as GPIO
        logger.info("RPi.GPIO detected - running on Raspberry Pi")
    except ImportError:
        logger.warning("RPi.GPIO not available - flow meters will run in simulation mode")
    
    # Get current tap configuration
    tap_configs = get_current_tap_config()
    
    if not tap_configs:
        logger.warning("No tapped kegs found. Make sure kegs are tapped in the web interface first.")
        logger.info("You can still start the system - it will monitor for newly tapped kegs.")
        # Create empty config to start the system
        tap_configs = []
    
    # Create and start the flow system
    try:
        flow_system = MultiTapFlowSystem(tap_configs)
        
        # Setup signal handlers for clean shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            flow_system.stop_all()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start monitoring
        flow_system.start_all()
        
        logger.info("Flow meter system started successfully!")
        logger.info(f"Monitoring {len(tap_configs)} taps")
        logger.info("Press Ctrl+C to stop, or send SIGTERM to shutdown cleanly")
        
        # Main monitoring loop
        while flow_system.running:
            time.sleep(30)  # Status update every 30 seconds
            
            # Log system status
            status = flow_system.get_system_status()
            if status['active_taps'] > 0:
                logger.info(f"System running: {status['active_taps']} active taps")
                for tap_num, tap_status in status['taps'].items():
                    volume_ml = tap_status['total_volume_dispensed_ml']
                    flow_rate = tap_status['current_flow_rate_ml_per_min']
                    if volume_ml > 0 or flow_rate > 0:
                        logger.info(f"  Tap {tap_num}: {volume_ml:.1f}ml total, {flow_rate:.1f}ml/min")
    
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        try:
            flow_system.stop_all()
        except:
            pass
        logger.info("Flow meter system shutdown complete")

if __name__ == "__main__":
    main()