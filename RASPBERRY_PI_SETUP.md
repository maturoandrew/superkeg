# Flow Meter Setup Guide for Raspberry Pi

This guide will help you deploy and test the flow meter system on your Raspberry Pi 2.

## Prerequisites

1. **Raspberry Pi 2** with Raspberry Pi OS installed
2. **Flow meter** (YF-S201 recommended) connected to GPIO 4
3. **Existing superkeg application** running and working

## Hardware Setup

### Flow Meter Wiring
Based on your test code, you're using GPIO 4. Here's the standard wiring:

```
Flow Meter -> Raspberry Pi 2
Red (VCC)   -> Pin 2 (5V) or Pin 4 (5V)
Black (GND) -> Pin 6 (GND) or any other GND pin
Yellow (SIG) -> Pin 7 (GPIO 4)
```

### GPIO Pin Reference for Pi 2
```
Pin 2:  5V Power
Pin 4:  5V Power  
Pin 6:  Ground
Pin 7:  GPIO 4 (your flow meter signal)
```

## Software Installation

### 1. Install Dependencies

```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install Python GPIO library (if not already installed)
sudo apt install python3-rpi.gpio

# Install other Python dependencies
pip3 install --user requests
```

### 2. Deploy Code

```bash
# Navigate to your superkeg directory
cd /home/pi/superkeg

# Make scripts executable
chmod +x start_flow_monitoring.py
chmod +x setup_flow_meter.py
```

### 3. Test Flow Meter Connection

```bash
# Test your flow meter is working
python3 setup_flow_meter.py
```

This will:
- Test GPIO 4 connection
- Help you calibrate the flow meter
- Save calibration settings

### 4. Test Integration

```bash
# Test the full integration (without service)
python3 start_flow_monitoring.py
```

This should:
- Detect any tapped kegs
- Start monitoring flow meters
- Log pour events to your database

## Running as a Service (Optional)

To have flow monitoring start automatically on boot:

### 1. Install Service

```bash
# Copy service file
sudo cp flow-meter.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable flow-meter.service
```

### 2. Service Management

```bash
# Start the service
sudo systemctl start flow-meter.service

# Check service status
sudo systemctl status flow-meter.service

# View logs
sudo journalctl -u flow-meter.service -f

# Stop the service
sudo systemctl stop flow-meter.service

# Disable auto-start
sudo systemctl disable flow-meter.service
```

## Configuration

### GPIO Pin Mapping

If you need different GPIO pins, edit `start_flow_monitoring.py`:

```python
# Default GPIO pin mapping for 4 taps
gpio_pins = {
    1: 4,   # Tap 1 -> GPIO 4 (your current setup)
    2: 17,  # Tap 2 -> GPIO 17
    3: 27,  # Tap 3 -> GPIO 27  
    4: 22   # Tap 4 -> GPIO 22
}
```

### Flow Meter Calibration

Each flow meter type has different pulse rates:
- **YF-S201**: ~450 pulses/L (default)
- **YF-S401**: ~5880 pulses/L
- **YF-B1**: ~1800 pulses/L

Use the calibration tool to get exact values:

```bash
python3 setup_flow_meter.py
# Choose option 3: Calibrate flow meter
```

## Testing Process

### 1. Basic GPIO Test
```bash
# Run your original test to confirm GPIO 4 works
python3 your_test_fixed.py
```

### 2. Flow Meter Module Test
```bash
# Test the flow meter module
python3 -c "
from flow_meter import FlowMeter
meter = FlowMeter(gpio_pin=4)
meter.start_monitoring()
import time
time.sleep(10)
print(f'Pulses: {meter.pulse_count}')
meter.stop_monitoring()
meter.cleanup()
"
```

### 3. Full Integration Test

1. **Make sure Flask app is running:**
   ```bash
   python3 app.py
   ```

2. **Tap a keg in the web interface** (http://your-pi-ip:5000/manage)

3. **Start flow monitoring:**
   ```bash
   python3 start_flow_monitoring.py
   ```

4. **Pour beer and check:**
   - Watch console logs for pour detection
   - Check web interface for volume updates
   - Check pour history page

## Troubleshooting

### No Pulses Detected
```bash
# Check GPIO permissions
sudo usermod -a -G gpio pi

# Test with your original script
python3 your_test_fixed.py
```

### Permission Errors
```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER
# Log out and back in
```

### Service Won't Start
```bash
# Check service logs
sudo journalctl -u flow-meter.service -n 50

# Check file permissions
ls -la /home/pi/superkeg/start_flow_monitoring.py
```

### Database Errors
```bash
# Check database permissions
ls -la kegs.db

# Make sure Flask app creates the database first
python3 app.py
```

## Monitoring and Logs

### View Flow Meter Logs
```bash
# Real-time logs
tail -f flow_meter.log

# Service logs
sudo journalctl -u flow-meter.service -f
```

### Check System Status
```bash
# GPIO status
gpio readall

# Python processes
ps aux | grep python

# Disk space (for logs)
df -h
```

## File Structure

After setup, your directory should look like:
```
/home/pi/superkeg/
├── app.py                          # Your Flask app
├── keg_app.py                      # Database models
├── flow_meter.py                   # Flow meter module
├── flow_meter_integration.py       # Integration system
├── start_flow_monitoring.py        # Startup script
├── setup_flow_meter.py            # Setup tool
├── flow-meter.service              # Systemd service
├── kegs.db                         # SQLite database
├── flow_meter.log                  # Flow meter logs
└── *_config.json                   # Calibration files
```

## Next Steps

1. Test with your existing GPIO 4 setup
2. Calibrate for accurate measurements
3. Run integration tests with tapped kegs
4. Set up as service for auto-start
5. Monitor logs and adjust as needed

Good luck with testing! Let me know how it goes on your Pi.