#!/usr/bin/env python
"""
Flow Meter Integration Example
Shows how to integrate the flow meter with the existing keg tracking system.

This script demonstrates:
1. Setting up flow meters for multiple taps
2. Integrating with the SQLAlchemy database
3. Automatically logging pour events
4. Real-time keg volume updates
5. Web API integration
"""

import time
import requests
import signal
import sys
import logging
from flow_meter import FlowMeter, KegFlowTracker
from keg_app import SessionLocal, subtract_volume, log_pour_event, Keg, KegStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiTapFlowSystem(object):
    """
    Manages multiple flow meters for a multi-tap keg system.
    Integrates with the existing Flask web application and database.
    """
    
    def __init__(self, tap_configs, flask_base_url="http://localhost:5000"):
        """
        Initialize multi-tap flow system.
        
        Args:
            tap_configs: List of dictionaries with tap configuration:
                        [{"tap_number": 1, "gpio_pin": 18, "pulses_per_liter": 450}, ...]
            flask_base_url: Base URL of the Flask web application
        """
        self.tap_configs = tap_configs
        self.flask_base_url = flask_base_url
        self.flow_trackers = {}
        self.running = False
        
        # Setup signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Received signal %d, shutting down..." % signum)
        self.stop_all()
        sys.exit(0)
    
    def _update_keg_volume_db(self, keg_id, volume_liters):
        """Update keg volume in database directly."""
        try:
            session = SessionLocal()
            keg = subtract_volume(session, keg_id, volume_liters)
            if keg:
                logger.info("Updated keg %d: -%.1fml, remaining: %.2fL" % (keg_id, volume_liters*1000, keg.volume_remaining))
            else:
                logger.warning("Failed to update keg %d volume" % keg_id)
            session.close()
        except Exception as e:
            logger.error("Database error updating keg %d: %s" % (keg_id, str(e)))
    
    def _log_pour_event_db(self, keg_id: int, volume_liters: float):
        """Log pour event to database directly."""
        try:
            session = SessionLocal()
            event = log_pour_event(session, keg_id, volume_liters)
            if event:
                logger.info(f"Logged pour event: keg {keg_id}, {volume_liters*1000:.1f}ml")
            session.close()
        except Exception as e:
            logger.error(f"Database error logging pour for keg {keg_id}: {e}")
    
    def _update_keg_volume_api(self, keg_id: int, volume_liters: float):
        """Update keg volume via Flask API."""
        try:
            url = f"{self.flask_base_url}/api/flow/{keg_id}"
            data = {"volume_dispensed": volume_liters}
            response = requests.post(url, json=data, timeout=5)
            
            if response.status_code == 200:
                logger.info(f"API updated keg {keg_id}: -{volume_liters*1000:.1f}ml")
            else:
                logger.warning(f"API update failed for keg {keg_id}: {response.status_code}")
                # Fallback to direct database update
                self._update_keg_volume_db(keg_id, volume_liters)
                self._log_pour_event_db(keg_id, volume_liters)
                
        except requests.RequestException as e:
            logger.warning(f"API request failed for keg {keg_id}: {e}")
            # Fallback to direct database update
            self._update_keg_volume_db(keg_id, volume_liters)
            self._log_pour_event_db(keg_id, volume_liters)
    
    def get_tapped_kegs(self) -> Dict[int, int]:
        """Get mapping of tap positions to keg IDs."""
        try:
            session = SessionLocal()
            tapped_kegs = session.query(Keg).filter(Keg.status == KegStatus.TAPPED).all()
            tap_to_keg = {keg.tap_position: keg.id for keg in tapped_kegs if keg.tap_position}
            session.close()
            return tap_to_keg
        except Exception as e:
            logger.error(f"Error getting tapped kegs: {e}")
            return {}
    
    def setup_tap(self, tap_number: int, gpio_pin: int, pulses_per_liter: float = 450.0):
        """Setup a flow meter for a specific tap."""
        try:
            # Get keg ID for this tap
            tap_to_keg = self.get_tapped_kegs()
            keg_id = tap_to_keg.get(tap_number)
            
            if not keg_id:
                logger.warning(f"No keg tapped at position {tap_number}, skipping setup")
                return False
            
            # Create flow meter
            flow_meter = FlowMeter(gpio_pin=gpio_pin, pulses_per_liter=pulses_per_liter)
            
            # Load calibration if exists
            config_file = f"tap_{tap_number}_config.json"
            flow_meter.load_calibration(config_file)
            
            # Create keg flow tracker
            tracker = KegFlowTracker(flow_meter, keg_id, pour_threshold_ml=50.0)
            
            # Set up callbacks - prefer API, fallback to direct DB
            tracker.update_keg_callback = self._update_keg_volume_api
            tracker.log_pour_callback = lambda kid, vol: None  # API handles both update and logging
            
            # Store tracker
            self.flow_trackers[tap_number] = tracker
            
            logger.info(f"Setup tap {tap_number} (GPIO {gpio_pin}) for keg {keg_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up tap {tap_number}: {e}")
            return False
    
    def start_tap(self, tap_number: int):
        """Start monitoring a specific tap."""
        if tap_number in self.flow_trackers:
            self.flow_trackers[tap_number].start_tracking()
            logger.info(f"Started monitoring tap {tap_number}")
        else:
            logger.warning(f"Tap {tap_number} not configured")
    
    def stop_tap(self, tap_number: int):
        """Stop monitoring a specific tap."""
        if tap_number in self.flow_trackers:
            self.flow_trackers[tap_number].stop_tracking()
            self.flow_trackers[tap_number].flow_meter.cleanup()
            logger.info(f"Stopped monitoring tap {tap_number}")
    
    def start_all(self):
        """Start monitoring all configured taps."""
        logger.info("Starting multi-tap flow monitoring system...")
        
        # Setup all taps
        for config in self.tap_configs:
            tap_num = config['tap_number']
            gpio_pin = config['gpio_pin']
            pulses_per_liter = config.get('pulses_per_liter', 450.0)
            
            if self.setup_tap(tap_num, gpio_pin, pulses_per_liter):
                self.start_tap(tap_num)
        
        self.running = True
        logger.info(f"Started monitoring {len(self.flow_trackers)} taps")
    
    def stop_all(self):
        """Stop monitoring all taps."""
        if not self.running:
            return
        
        logger.info("Stopping all flow meters...")
        for tap_number in list(self.flow_trackers.keys()):
            self.stop_tap(tap_number)
        
        self.flow_trackers.clear()
        self.running = False
        logger.info("All flow meters stopped")
    
    def get_system_status(self) -> Dict:
        """Get status of all taps and flow meters."""
        status = {
            'running': self.running,
            'active_taps': len(self.flow_trackers),
            'taps': {}
        }
        
        for tap_number, tracker in self.flow_trackers.items():
            status['taps'][tap_number] = tracker.get_pour_stats()
        
        return status
    
    def calibrate_tap(self, tap_number: int, known_volume_liters: float):
        """Calibrate a specific tap's flow meter."""
        if tap_number in self.flow_trackers:
            tracker = self.flow_trackers[tap_number]
            tracker.flow_meter.calibrate(known_volume_liters)
            
            # Save calibration
            config_file = f"tap_{tap_number}_config.json"
            tracker.flow_meter.save_calibration(config_file)
            
            logger.info(f"Calibrated tap {tap_number} with {known_volume_liters}L")
        else:
            logger.warning(f"Tap {tap_number} not found for calibration")
    
    def reset_tap_volume(self, tap_number: int):
        """Reset volume counter for a specific tap."""
        if tap_number in self.flow_trackers:
            self.flow_trackers[tap_number].flow_meter.reset()
            logger.info(f"Reset volume counter for tap {tap_number}")


def main():
    """Main function demonstrating the flow meter system."""
    
    # Configuration for 4-tap system
    # Adjust GPIO pins and calibration values for your setup
    tap_configs = [
        {"tap_number": 1, "gpio_pin": 4, "pulses_per_liter": 450.0},   # YF-S201 on GPIO 4
        {"tap_number": 2, "gpio_pin": 17, "pulses_per_liter": 450.0}, # YF-S201 on GPIO 17
        {"tap_number": 3, "gpio_pin": 27, "pulses_per_liter": 450.0}, # YF-S201 on GPIO 27
        {"tap_number": 4, "gpio_pin": 22, "pulses_per_liter": 450.0}, # YF-S201 on GPIO 22
    ]
    
    # Create and start the system
    flow_system = MultiTapFlowSystem(tap_configs)
    
    try:
        # Start monitoring
        flow_system.start_all()
        
        # Main monitoring loop
        logger.info("Flow meter system running. Press Ctrl+C to stop.")
        while flow_system.running:
            time.sleep(10)  # Status update every 10 seconds
            
            # Print system status
            status = flow_system.get_system_status()
            logger.info(f"System status: {status['active_taps']} active taps")
            
            for tap_num, tap_status in status['taps'].items():
                volume_ml = tap_status['total_volume_dispensed_ml']
                flow_rate = tap_status['current_flow_rate_ml_per_min']
                logger.info(f"  Tap {tap_num}: {volume_ml:.1f}ml total, {flow_rate:.1f}ml/min")
    
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        flow_system.stop_all()
        logger.info("Flow meter system shutdown complete")


def calibration_example():
    """Example of how to calibrate flow meters."""
    print("\n=== Flow Meter Calibration Example ===")
    print("1. Pour a known volume (e.g., 500ml) through the flow meter")
    print("2. Note the pulse count")
    print("3. Calculate pulses per liter")
    print("4. Update configuration")
    
    # Example calibration process
    flow_meter = FlowMeter(gpio_pin=18, pulses_per_liter=450.0)  # Initial guess
    
    try:
        flow_meter.start_monitoring()
        print("\nFlow meter started. Pour 500ml of liquid and press Enter...")
        input()
        
        # Get pulse count
        pulse_count = flow_meter.pulse_count
        known_volume = 0.5  # 500ml = 0.5L
        
        if pulse_count > 0:
            # Calculate actual pulses per liter
            actual_ppl = pulse_count / known_volume
            print(f"\nCalibration results:")
            print(f"  Pulses detected: {pulse_count}")
            print(f"  Known volume: {known_volume}L")
            print(f"  Calculated: {actual_ppl:.2f} pulses/L")
            
            # Apply calibration
            flow_meter.calibrate(known_volume)
            flow_meter.save_calibration("calibration_example.json")
            print(f"  Calibration saved!")
        else:
            print("No pulses detected. Check flow meter connection.")
    
    finally:
        flow_meter.stop_monitoring()
        flow_meter.cleanup()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "calibrate":
        calibration_example()
    else:
        main()