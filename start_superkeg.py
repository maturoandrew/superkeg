#!/usr/bin/env python
"""
Superkeg Combined Startup Script
Starts both the Flask web application and flow meter monitoring system.
"""

import sys
import os
import time
import signal
import logging
import subprocess
import threading
from datetime import datetime

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('superkeg.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SuperkegManager(object):
    """Manages both Flask app and flow meter monitoring."""
    
    def __init__(self):
        self.flask_process = None
        self.flow_monitor_process = None
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Received signal %d, shutting down..." % signum)
        self.stop_all()
        sys.exit(0)
    
    def start_flask_app(self):
        """Start the Flask web application."""
        try:
            logger.info("Starting Flask web application...")
            
            # Start Flask app as subprocess
            self.flask_process = subprocess.Popen(
                [sys.executable, 'app.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Monitor Flask output in a separate thread
            flask_monitor = threading.Thread(
                target=self._monitor_flask_output
            )
            flask_monitor.daemon = True
            flask_monitor.start()
            
            # Give Flask time to start
            time.sleep(3)
            
            if self.flask_process.poll() is None:
                logger.info("✓ Flask app started successfully")
                return True
            else:
                logger.error("✗ Flask app failed to start")
                return False
                
        except Exception as e:
            logger.error("Error starting Flask app: %s" % str(e))
            return False
    
    def _monitor_flask_output(self):
        """Monitor Flask application output."""
        if not self.flask_process:
            return
        
        try:
            for line in iter(self.flask_process.stdout.readline, ''):
                if line.strip():
                    logger.info("Flask: %s" % line.strip())
                if not self.running:
                    break
        except Exception as e:
            logger.error("Error monitoring Flask output: %s" % str(e))
    
    def start_flow_monitoring(self):
        """Start flow meter monitoring."""
        try:
            # Check if we should start flow monitoring
            try:
                import RPi.GPIO as GPIO
                logger.info("RPi.GPIO detected - starting flow meter monitoring")
            except ImportError:
                logger.warning("RPi.GPIO not available - flow monitoring will run in simulation mode")
            
            # Wait for Flask app to be ready
            logger.info("Waiting for Flask app to be ready...")
            time.sleep(5)
            
            logger.info("Starting flow meter monitoring...")
            
            # Import and start flow monitoring
            from flow_meter_integration import MultiTapFlowSystem
            from keg_app import SessionLocal, Keg, KegStatus
            
            # Get current tap configuration
            tap_configs = self._get_tap_config()
            
            # Create flow system
            self.flow_system = MultiTapFlowSystem(tap_configs)
            
            # Start monitoring in a separate thread
            flow_thread = threading.Thread(
                target=self._run_flow_monitoring
            )
            flow_thread.daemon = True
            flow_thread.start()
            
            logger.info("✓ Flow meter monitoring started")
            return True
            
        except Exception as e:
            logger.error("Error starting flow monitoring: %s" % str(e))
            return False
    
    def _get_tap_config(self):
        """Get current tap configuration."""
        try:
            from keg_app import SessionLocal, Keg, KegStatus
            
            session = SessionLocal()
            tapped_kegs = session.query(Keg).filter(Keg.status == KegStatus.TAPPED).all()
            session.close()
            
            # GPIO pin mapping
            gpio_pins = {1: 4, 2: 17, 3: 27, 4: 22}
            
            tap_configs = []
            for keg in tapped_kegs:
                if keg.tap_position and keg.tap_position in gpio_pins:
                    tap_configs.append({
                        "tap_number": keg.tap_position,
                        "gpio_pin": gpio_pins[keg.tap_position],
                        "pulses_per_liter": 450.0
                    })
                    logger.info("Found tapped keg: %s at tap %d" % (keg.name, keg.tap_position))
            
            return tap_configs
        except Exception as e:
            logger.error("Error getting tap configuration: %s" % str(e))
            return []
    
    def _run_flow_monitoring(self):
        """Run flow monitoring in thread."""
        try:
            self.flow_system.start_all()
            
            # Monitor flow system
            while self.running:
                time.sleep(30)  # Status update every 30 seconds
                
                if hasattr(self, 'flow_system'):
                    status = self.flow_system.get_system_status()
                    if status['active_taps'] > 0:
                        logger.info("Flow monitoring: %d active taps" % status['active_taps'])
                        
                        for tap_num, tap_status in status['taps'].items():
                            volume_ml = tap_status['total_volume_dispensed_ml']
                            flow_rate = tap_status['current_flow_rate_ml_per_min']
                            if volume_ml > 0 or flow_rate > 0:
                                logger.info("  Tap %d: %.1fml total, %.1fml/min" % (tap_num, volume_ml, flow_rate))
        
        except Exception as e:
            logger.error("Error in flow monitoring: %s" % str(e))
    
    def check_prerequisites(self):
        """Check if all required files and dependencies are available."""
        logger.info("Checking prerequisites...")
        
        required_files = ['app.py', 'keg_app.py', 'flow_meter.py', 'flow_meter_integration.py']
        missing_files = []
        
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
        
        if missing_files:
            logger.error("Missing required files: %s" % missing_files)
            return False
        
        # Check Python modules
        try:
            import flask
            import sqlalchemy
            logger.info("✓ Required Python modules available")
        except ImportError as e:
            logger.error("Missing Python module: %s" % str(e))
            return False
        
        logger.info("✓ All prerequisites met")
        return True
    
    def wait_for_flask_ready(self, timeout=30):
        """Wait for Flask app to be ready."""
        try:
            import requests
        except ImportError:
            logger.warning("requests module not available, skipping Flask readiness check")
            return True
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get('http://localhost:5000/', timeout=2)
                if response.status_code == 200:
                    logger.info("✓ Flask app is ready and responding")
                    return True
            except:
                pass
            time.sleep(1)
        
        logger.warning("Flask app may not be fully ready")
        return False
    
    def start_all(self):
        """Start both Flask app and flow monitoring."""
        logger.info("=== Starting Superkeg System ===")
        
        # Check prerequisites
        if not self.check_prerequisites():
            logger.error("Prerequisites not met. Please install missing dependencies.")
            return False
        
        # Start Flask app
        if not self.start_flask_app():
            logger.error("Failed to start Flask app")
            return False
        
        # Wait for Flask to be ready
        self.wait_for_flask_ready()
        
        # Start flow monitoring
        if not self.start_flow_monitoring():
            logger.error("Failed to start flow monitoring")
            # Flask app can still work without flow monitoring
        
        logger.info("=== Superkeg System Started Successfully ===")
        logger.info("Web interface: http://localhost:5000")
        logger.info("Display page: http://localhost:5000/display")
        logger.info("Management: http://localhost:5000/manage")
        logger.info("Press Ctrl+C to stop")
        
        return True
    
    def stop_all(self):
        """Stop both services."""
        logger.info("Stopping Superkeg system...")
        self.running = False
        
        # Stop flow monitoring
        if hasattr(self, 'flow_system'):
            try:
                self.flow_system.stop_all()
                logger.info("✓ Flow monitoring stopped")
            except:
                pass
        
        # Stop Flask app
        if self.flask_process and self.flask_process.poll() is None:
            try:
                self.flask_process.terminate()
                self.flask_process.wait()
                logger.info("✓ Flask app stopped")
            except:
                try:
                    self.flask_process.kill()
                    logger.info("✓ Flask app force stopped")
                except:
                    pass
        
        logger.info("Superkeg system shutdown complete")
    
    def status(self):
        """Get system status."""
        flask_running = self.flask_process and self.flask_process.poll() is None
        flow_monitoring = hasattr(self, 'flow_system') and getattr(self.flow_system, 'running', False)
        
        status = {
            'flask_running': flask_running,
            'flow_monitoring': flow_monitoring
        }
        
        logger.info("System Status:")
        logger.info("  Flask App: %s" % ('Running' if status['flask_running'] else 'Stopped'))
        logger.info("  Flow Monitoring: %s" % ('Running' if status['flow_monitoring'] else 'Stopped'))
        
        return status

def main():
    """Main function."""
    manager = SuperkegManager()
    
    try:
        if manager.start_all():
            # Main loop
            while manager.running:
                time.sleep(60)  # Status check every minute
                manager.status()
        else:
            logger.error("Failed to start Superkeg system")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error("Unexpected error: %s" % str(e))
        import traceback
        logger.error(traceback.format_exc())
    finally:
        manager.stop_all()

if __name__ == "__main__":
    main()