#!/usr/bin/env python
"""
Flow Meter Tracking Module for Raspberry Pi
Tracks flow meter pulses and calculates volume dispensed for keg monitoring system.

Supports common flow meters like:
- YF-S201 (Hall effect sensor)
- YF-S401 (Hall effect sensor) 
- Any pulse-based flow meter

Hardware Setup:
- Flow meter VCC -> 5V (or 3.3V depending on sensor)
- Flow meter GND -> GND
- Flow meter Signal -> GPIO pin (default GPIO 4)
- Pull-up resistor may be needed (10k ohm between signal and VCC)
"""

import time
import threading
import json
from datetime import datetime
import logging

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("Warning: RPi.GPIO not available. Running in simulation mode.")
    GPIO_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FlowMeter(object):
    """
    Flow meter class that tracks pulses and calculates volume.
    
    Attributes:
        gpio_pin (int): GPIO pin number for flow meter signal
        pulses_per_liter (float): Number of pulses per liter (calibration factor)
        pulse_count (int): Total pulse count since start
        volume_total (float): Total volume dispensed in liters
        flow_rate (float): Current flow rate in L/min
        last_pulse_time (float): Timestamp of last pulse
        is_monitoring (bool): Whether monitoring is active
    """
    
    def __init__(self, gpio_pin=4, pulses_per_liter=450.0):
        """
        Initialize flow meter.
        
        Args:
            gpio_pin: GPIO pin number for flow meter signal (default: 4)
            pulses_per_liter: Calibration factor (pulses per liter)
                             Common values:
                             - YF-S201: ~450 pulses/L
                             - YF-S401: ~5880 pulses/L
        """
        self.gpio_pin = gpio_pin
        self.pulses_per_liter = pulses_per_liter
        self.pulse_count = 0
        self.volume_total = 0.0
        self.flow_rate = 0.0
        self.last_pulse_time = 0.0
        self.is_monitoring = False
        self.start_time = 0.0
        
        # Flow rate calculation
        self.pulse_times = []
        self.flow_rate_window = 10  # seconds
        
        # Callbacks
        self.on_pulse_callback = None
        self.on_volume_callback = None
        self.on_flow_rate_callback = None
        
        # Threading
        self.monitor_thread = None
        self.stop_monitoring = threading.Event()
        
        # Setup GPIO if available
        if GPIO_AVAILABLE:
            self._setup_gpio()
    
    def _setup_gpio(self):
        """Setup GPIO pin for flow meter."""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info("GPIO pin %d configured for flow meter" % self.gpio_pin)
        except Exception as e:
            logger.error("Failed to setup GPIO: %s" % str(e))
            raise
    
    def _pulse_detected(self, channel):
        """
        GPIO interrupt callback for pulse detection.
        Called on rising edge of flow meter signal.
        """
        current_time = time.time()
        
        # Debounce - ignore pulses too close together (< 1ms)
        if current_time - self.last_pulse_time < 0.001:
            return
        
        self.pulse_count += 1
        self.last_pulse_time = current_time
        
        # Add to pulse times for flow rate calculation
        self.pulse_times.append(current_time)
        
        # Remove old pulse times outside the window
        cutoff_time = current_time - self.flow_rate_window
        self.pulse_times = [t for t in self.pulse_times if t > cutoff_time]
        
        # Calculate volume
        self.volume_total = self.pulse_count / self.pulses_per_liter
        
        # Calculate flow rate (L/min)
        if len(self.pulse_times) > 1:
            time_span = self.pulse_times[-1] - self.pulse_times[0]
            if time_span > 0:
                pulses_per_second = (len(self.pulse_times) - 1) / time_span
                self.flow_rate = (pulses_per_second / self.pulses_per_liter) * 60
        
        # Call callbacks
        if self.on_pulse_callback:
            self.on_pulse_callback()
        
        if self.on_volume_callback:
            self.on_volume_callback(self.volume_total)
        
        if self.on_flow_rate_callback:
            self.on_flow_rate_callback(self.flow_rate)
    
    def start_monitoring(self):
        """Start monitoring flow meter pulses."""
        if self.is_monitoring:
            logger.warning("Flow meter monitoring already started")
            return
        
        self.is_monitoring = True
        self.start_time = time.time()
        self.stop_monitoring.clear()
        
        if GPIO_AVAILABLE:
            # Add interrupt for rising edge
            GPIO.add_event_detect(
                self.gpio_pin, 
                GPIO.RISING, 
                callback=self._pulse_detected,
                bouncetime=1  # 1ms debounce
            )
            logger.info("Started monitoring flow meter on GPIO %d" % self.gpio_pin)
        else:
            # Simulation mode - start a thread that simulates pulses
            self.monitor_thread = threading.Thread(target=self._simulate_flow)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            logger.info("Started flow meter simulation mode")
    
    def stop_monitoring(self):
        """Stop monitoring flow meter pulses."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self.stop_monitoring.set()
        
        if GPIO_AVAILABLE:
            GPIO.remove_event_detect(self.gpio_pin)
            logger.info("Stopped monitoring flow meter")
        else:
            if self.monitor_thread:
                self.monitor_thread.join(timeout=1.0)
            logger.info("Stopped flow meter simulation")
    
    def _simulate_flow(self):
        """Simulate flow meter pulses for testing without GPIO."""
        logger.info("Running flow meter simulation (for testing)")
        pulse_interval = 0.1  # 10 Hz simulation
        
        while not self.stop_monitoring.is_set():
            # Simulate a pulse every 100ms when "flowing"
            if time.time() % 5 < 2:  # "Flow" for 2 seconds every 5 seconds
                self._pulse_detected(self.gpio_pin)
            time.sleep(pulse_interval)
    
    def reset(self):
        """Reset pulse count and volume total."""
        self.pulse_count = 0
        self.volume_total = 0.0
        self.flow_rate = 0.0
        self.pulse_times = []
        logger.info("Flow meter reset")
    
    def calibrate(self, known_volume_liters):
        """
        Calibrate the flow meter using a known volume.
        
        Args:
            known_volume_liters: The actual volume that passed through in liters
        """
        if self.pulse_count > 0:
            self.pulses_per_liter = self.pulse_count / known_volume_liters
            self.volume_total = known_volume_liters
            logger.info("Calibrated: %.2f pulses/L" % self.pulses_per_liter)
        else:
            logger.warning("No pulses detected for calibration")
    
    def get_status(self):
        """Get current flow meter status."""
        uptime = time.time() - self.start_time if self.is_monitoring else 0
        return {
            'gpio_pin': self.gpio_pin,
            'pulses_per_liter': self.pulses_per_liter,
            'pulse_count': self.pulse_count,
            'volume_total_liters': self.volume_total,
            'volume_total_ml': self.volume_total * 1000,
            'flow_rate_l_per_min': self.flow_rate,
            'flow_rate_ml_per_min': self.flow_rate * 1000,
            'is_monitoring': self.is_monitoring,
            'uptime_seconds': uptime
        }
    
    def save_calibration(self, filename='flow_meter_config.json'):
        """Save calibration data to file."""
        config = {
            'gpio_pin': self.gpio_pin,
            'pulses_per_liter': self.pulses_per_liter,
            'calibration_date': datetime.now().isoformat()
        }
        with open(filename, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Calibration saved to %s" % filename)
    
    def load_calibration(self, filename='flow_meter_config.json'):
        """Load calibration data from file."""
        try:
            with open(filename, 'r') as f:
                config = json.load(f)
            self.pulses_per_liter = config.get('pulses_per_liter', self.pulses_per_liter)
            logger.info("Calibration loaded from %s: %s pulses/L" % (filename, self.pulses_per_liter))
        except IOError:
            logger.warning("Calibration file %s not found" % filename)
        except Exception as e:
            logger.error("Error loading calibration: %s" % str(e))
    
    def cleanup(self):
        """Clean up GPIO resources."""
        self.stop_monitoring()
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup(self.gpio_pin)
                logger.info("GPIO cleanup completed")
            except Exception as e:
                logger.warning("GPIO cleanup error: %s" % str(e))


class KegFlowTracker(object):
    """
    Integrates flow meter with keg tracking system.
    Automatically updates keg volumes and logs pour events.
    """
    
    def __init__(self, flow_meter, keg_id, pour_threshold_ml=50.0):
        """
        Initialize keg flow tracker.
        
        Args:
            flow_meter: FlowMeter instance
            keg_id: ID of the keg being tracked
            pour_threshold_ml: Minimum volume to log as a pour event
        """
        self.flow_meter = flow_meter
        self.keg_id = keg_id
        self.pour_threshold_ml = pour_threshold_ml
        
        # Pour tracking
        self.last_logged_volume = 0.0
        self.pour_start_time = None
        self.is_pouring = False
        self.pour_timeout = 5.0  # seconds without flow to end pour
        
        # Callbacks for keg system integration
        self.update_keg_callback = None
        self.log_pour_callback = None
        
        # Setup flow meter callbacks
        self.flow_meter.on_volume_callback = self._on_volume_change
        self.flow_meter.on_flow_rate_callback = self._on_flow_rate_change
        
        # Threading for pour detection
        self.monitor_thread = threading.Thread(target=self._monitor_pour_events)
        self.monitor_thread.daemon = True
        self.stop_monitoring = threading.Event()
    
    def _on_volume_change(self, total_volume_liters):
        """Called when flow meter detects volume change."""
        current_time = time.time()
        
        if not self.is_pouring:
            self.is_pouring = True
            self.pour_start_time = current_time
            logger.info("Pour started for keg %d" % self.keg_id)
        
        # Reset pour timeout
        self.last_flow_time = current_time
        
        # Track active pour progress
        volume_since_last = total_volume_liters - self.last_logged_volume
        if volume_since_last > 0:
            # Call active pour callback if available
            if hasattr(self, 'active_pour_callback') and self.active_pour_callback:
                self.active_pour_callback(self.keg_id, volume_since_last)
    
    def _on_flow_rate_change(self, flow_rate_l_per_min):
        """Called when flow rate changes."""
        # This can be used for real-time monitoring or alerts
        pass
    
    def _monitor_pour_events(self):
        """Monitor for pour events and log them."""
        while not self.stop_monitoring.is_set():
            if self.is_pouring:
                current_time = time.time()
                
                # Check if pour has stopped (no flow for timeout period)
                if (current_time - self.last_flow_time) > self.pour_timeout:
                    volume_poured = self.flow_meter.volume_total - self.last_logged_volume
                    volume_poured_ml = volume_poured * 1000
                    
                    if volume_poured_ml >= self.pour_threshold_ml:
                        # Call finish callback for active pour tracking
                        if hasattr(self, 'finish_pour_callback') and self.finish_pour_callback:
                            self.finish_pour_callback(self.keg_id, volume_poured)
                        
                        # Log the pour event to database
                        if self.log_pour_callback:
                            self.log_pour_callback(self.keg_id, volume_poured)
                        
                        # Update keg volume in database
                        if self.update_keg_callback:
                            self.update_keg_callback(self.keg_id, volume_poured)
                        
                        logger.info("Pour finished and logged: %.1fml for keg %d" % (volume_poured_ml, self.keg_id))
                    
                    # Reset pour tracking
                    self.is_pouring = False
                    self.last_logged_volume = self.flow_meter.volume_total
            
            time.sleep(0.1)  # Check every 100ms
    
    def start_tracking(self):
        """Start tracking flow for this keg."""
        self.flow_meter.start_monitoring()
        self.stop_monitoring.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_pour_events)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.last_flow_time = time.time()
        logger.info("Started tracking flow for keg %d" % self.keg_id)
    
    def stop_tracking(self):
        """Stop tracking flow for this keg."""
        self.stop_monitoring.set()
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
        logger.info("Stopped tracking flow for keg %d" % self.keg_id)
    
    def get_pour_stats(self):
        """Get current pour statistics."""
        return {
            'keg_id': self.keg_id,
            'total_volume_dispensed_liters': self.flow_meter.volume_total,
            'total_volume_dispensed_ml': self.flow_meter.volume_total * 1000,
            'is_currently_pouring': self.is_pouring,
            'current_flow_rate_ml_per_min': self.flow_meter.flow_rate * 1000,
            'pour_threshold_ml': self.pour_threshold_ml,
            'flow_meter_status': self.flow_meter.get_status()
        }


# Example usage and testing functions
def test_flow_meter():
    """Test flow meter functionality."""
    print("Testing Flow Meter...")
    
    # Create flow meter instance
    flow_meter = FlowMeter(gpio_pin=4, pulses_per_liter=450.0)
    
    # Add callbacks for testing
    def on_pulse():
        print("Pulse detected! Total: %d" % flow_meter.pulse_count)
    
    def on_volume(volume):
        print("Volume: %.1fml, Flow rate: %.1fml/min" % (volume*1000, flow_meter.flow_rate*1000))
    
    flow_meter.on_pulse_callback = on_pulse
    flow_meter.on_volume_callback = on_volume
    
    try:
        # Start monitoring
        flow_meter.start_monitoring()
        print("Flow meter started. Waiting for flow...")
        
        # Monitor for 30 seconds
        time.sleep(30)
        
    except KeyboardInterrupt:
        print("Test interrupted by user")
    finally:
        flow_meter.stop_monitoring()
        flow_meter.cleanup()
        print("Flow meter test completed")


if __name__ == "__main__":
    test_flow_meter()