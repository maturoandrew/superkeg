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
        self.active_pours = {}  # Track active pours by keg_id
        
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
            # Get the keg first
            keg = session.query(Keg).filter(Keg.id == keg_id, Keg.status == KegStatus.TAPPED).first()
            if keg:
                # Update the volume
                keg.volume_remaining = max(0, keg.volume_remaining - volume_liters)
                session.commit()
                # Get the final volume before closing
                final_volume = keg.volume_remaining
                session.close()
                logger.info("Updated keg %d: -%.1fml, remaining: %.2fL" % (keg_id, volume_liters*1000, final_volume))
            else:
                session.close()
                logger.warning("Failed to update keg %d volume - keg not found or not tapped" % keg_id)
        except Exception as e:
            logger.error("Database error updating keg %d: %s" % (keg_id, str(e)))
    
    def _log_pour_event_db(self, keg_id, volume_liters):
        """Log pour event to database directly."""
        try:
            session = SessionLocal()
            from datetime import datetime
            event = PourEvent(keg_id=keg_id, volume_dispensed=volume_liters, timestamp=datetime.utcnow())
            session.add(event)
            session.commit()
            session.close()
            logger.info("Logged pour event: keg %d, %.1fml" % (keg_id, volume_liters*1000))
        except Exception as e:
            logger.error("Database error logging pour for keg %d: %s" % (keg_id, str(e)))
    
    def _track_active_pour(self, keg_id, volume_liters):
        """Track active pour progress for real-time display."""
        from datetime import datetime
        
        if keg_id not in self.active_pours:
            self.active_pours[keg_id] = {
                'start_time': datetime.utcnow(),
                'total_volume': 0,
                'last_update': datetime.utcnow()
            }
        
        self.active_pours[keg_id]['total_volume'] += volume_liters
        self.active_pours[keg_id]['last_update'] = datetime.utcnow()
        
        logger.info("Active pour - Keg %d: %.1fml total" % (keg_id, self.active_pours[keg_id]['total_volume'] * 1000))
    
    def _finish_active_pour(self, keg_id):
        """Mark active pour as finished."""
        if keg_id in self.active_pours:
            total_volume = self.active_pours[keg_id]['total_volume']
            logger.info("Finished pour - Keg %d: %.1fml total" % (keg_id, total_volume * 1000))
            del self.active_pours[keg_id]
    
    def get_active_pours(self):
        """Get current active pours for API."""
        from datetime import datetime
        
        active_pours = []
        completed_pours = []
        
        # Clean up old active pours (older than 10 seconds)
        current_time = datetime.utcnow()
        kegs_to_remove = []
        
        for keg_id, pour_data in self.active_pours.items():
            time_since_update = (current_time - pour_data['last_update']).total_seconds()
            if time_since_update > 10:  # Mark as completed if no updates for 10 seconds
                completed_pours.append({
                    'keg_id': keg_id,
                    'final_volume': pour_data['total_volume']
                })
                kegs_to_remove.append(keg_id)
            else:
                # Get keg name
                try:
                    session = SessionLocal()
                    keg = session.query(Keg).filter(Keg.id == keg_id).first()
                    keg_name = keg.name if keg else 'Unknown Keg'
                    session.close()
                    
                    active_pours.append({
                        'keg_id': keg_id,
                        'keg_name': keg_name,
                        'current_volume': pour_data['total_volume'],
                        'total_volume': min(pour_data['total_volume'] * 2, 0.5)  # Estimate total
                    })
                except Exception as e:
                    logger.error("Error getting keg name for %d: %s" % (keg_id, str(e)))
        
        # Remove completed pours
        for keg_id in kegs_to_remove:
            del self.active_pours[keg_id]
        
        return active_pours, completed_pours
    
    def _update_keg_volume_api(self, keg_id, volume_liters):
        """Update keg volume via Flask API."""
        try:
            url = "%s/api/flow/%d" % (self.flask_base_url, keg_id)
            data = {"volume_dispensed": volume_liters}
            response = requests.post(url, json=data, timeout=5)
            
            if response.status_code == 200:
                logger.info("API updated keg %d: -%.1fml" % (keg_id, volume_liters*1000))
            else:
                logger.warning("API update failed for keg %d: %d" % (keg_id, response.status_code))
                # Fallback to direct database update
                self._update_keg_volume_db(keg_id, volume_liters)
                self._log_pour_event_db(keg_id, volume_liters)
                
        except requests.RequestException as e:
            logger.warning("API request failed for keg %d: %s" % (keg_id, str(e)))
            # Fallback to direct database update
            self._update_keg_volume_db(keg_id, volume_liters)
            self._log_pour_event_db(keg_id, volume_liters)
    
    def get_tapped_kegs(self):
        """Get mapping of tap positions to keg IDs."""
        try:
            session = SessionLocal()
            tapped_kegs = session.query(Keg).filter(Keg.status == KegStatus.TAPPED).all()
            # Create a dictionary with keg data before closing session
            tap_to_keg = {}
            for keg in tapped_kegs:
                if keg.tap_position:
                    tap_to_keg[keg.tap_position] = keg.id
            session.close()
            return tap_to_keg
        except Exception as e:
            logger.error("Error getting tapped kegs: %s" % str(e))
            return {}
    
    def setup_tap(self, tap_number, gpio_pin, pulses_per_liter=450.0):
        """Setup a flow meter for a specific tap."""
        try:
            # Get keg ID for this tap
            tap_to_keg = self.get_tapped_kegs()
            keg_id = tap_to_keg.get(tap_number)
            
            if not keg_id:
                logger.warning("No keg tapped at position %d, skipping setup" % tap_number)
                return False
            
            # Create flow meter
            flow_meter = FlowMeter(gpio_pin=gpio_pin, pulses_per_liter=pulses_per_liter)
            
            # Load calibration if exists
            config_file = "tap_%d_config.json" % tap_number
            flow_meter.load_calibration(config_file)
            
            # Create keg flow tracker
            tracker = KegFlowTracker(flow_meter, keg_id, pour_threshold_ml=50.0)
            
            # Set up callbacks - prefer API, fallback to direct DB
            tracker.update_keg_callback = self._update_keg_volume_api
            tracker.log_pour_callback = lambda kid, vol: None  # API handles both update and logging
            tracker.active_pour_callback = self._track_active_pour  # Track active pours
            
            # Store tracker
            self.flow_trackers[tap_number] = tracker
            
            logger.info("Setup tap %d (GPIO %d) for keg %d" % (tap_number, gpio_pin, keg_id))
            return True
            
        except Exception as e:
            logger.error("Error setting up tap %d: %s" % (tap_number, str(e)))
            return False
    
    def start_tap(self, tap_number):
        """Start monitoring a specific tap."""
        if tap_number in self.flow_trackers:
            self.flow_trackers[tap_number].start_tracking()
            logger.info("Started monitoring tap %d" % tap_number)
        else:
            logger.warning("Tap %d not configured" % tap_number)
    
    def stop_tap(self, tap_number):
        """Stop monitoring a specific tap."""
        if tap_number in self.flow_trackers:
            self.flow_trackers[tap_number].stop_tracking()
            self.flow_trackers[tap_number].flow_meter.cleanup()
            logger.info("Stopped monitoring tap %d" % tap_number)
    
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
        logger.info("Started monitoring %d taps" % len(self.flow_trackers))
    
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
    
    def get_system_status(self):
        """Get status of all taps and flow meters."""
        status = {
            'running': self.running,
            'active_taps': len(self.flow_trackers),
            'taps': {}
        }
        
        for tap_number, tracker in self.flow_trackers.items():
            status['taps'][tap_number] = tracker.get_pour_stats()
        
        return status
    
    def calibrate_tap(self, tap_number, known_volume_liters):
        """Calibrate a specific tap's flow meter."""
        if tap_number in self.flow_trackers:
            tracker = self.flow_trackers[tap_number]
            tracker.flow_meter.calibrate(known_volume_liters)
            
            # Save calibration
            config_file = "tap_%d_config.json" % tap_number
            tracker.flow_meter.save_calibration(config_file)
            
            logger.info("Calibrated tap %d with %.3fL" % (tap_number, known_volume_liters))
        else:
            logger.warning("Tap %d not found for calibration" % tap_number)
    
    def reset_tap_volume(self, tap_number):
        """Reset volume counter for a specific tap."""
        if tap_number in self.flow_trackers:
            self.flow_trackers[tap_number].flow_meter.reset()
            logger.info("Reset volume counter for tap %d" % tap_number)


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
            logger.info("System status: %d active taps" % status['active_taps'])
            
            for tap_num, tap_status in status['taps'].items():
                volume_ml = tap_status['total_volume_dispensed_ml']
                flow_rate = tap_status['current_flow_rate_ml_per_min']
                logger.info("  Tap %d: %.1fml total, %.1fml/min" % (tap_num, volume_ml, flow_rate))
    
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error("Unexpected error: %s" % str(e))
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
            print("\nCalibration results:")
            print("  Pulses detected: %d" % pulse_count)
            print("  Known volume: %.3fL" % known_volume)
            print("  Calculated: %.2f pulses/L" % actual_ppl)
            
            # Apply calibration
            flow_meter.calibrate(known_volume)
            flow_meter.save_calibration("calibration_example.json")
            print("  Calibration saved!")
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