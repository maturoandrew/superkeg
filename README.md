# superkeg

## Overview
Superkeg is a Python application for managing and monitoring beer kegs, designed to run on a Raspberry Pi with a tablet interface. It uses a local SQLite database for storage and provides a web-based UI for easy access and control.

## Current Capabilities
- **Web UI (Flask):**
  - View currently tapped kegs in a 1x4 row (with tap position labels)
  - Tablet-friendly display page (`/display`) showing all currently tapped kegs, auto-refreshing every 10 seconds
  - Keg management page to add, edit, tap, finish, or delete kegs
  - Edit keg details (name, style, brewer, ABV, volume, original volume)
  - Low volume warning (red border and icon if below 10% of original volume)
  - Dark mode/theme toggle (persists across reloads)
  - Tap position labels (Tap 1, Tap 2, etc.) above each keg card
- **Database:**
  - Uses SQLite for local storage (file: `kegs.db`)
  - Keg model includes: name, style, brewer, ABV, volume remaining, original volume, date created, date last tapped, date finished, and status
  - PourEvent model logs every pour (timestamp, keg, volume)
- **API:**
  - `/api/flow/<keg_id>` (POST): Accepts JSON `{ "volume_dispensed": float }` to subtract volume from a tapped keg and log the pour
- **Pour History:**
  - Pour events are logged automatically
  - Pour history page (`/history`) shows the 100 most recent pours
  - Export pour history as CSV (1000 most recent or full history)
- **Backup/Export:**
  - Download the full database file (`kegs.db`)
  - Export all keg data as CSV
  - Export pour history as CSV (recent or full)

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Run the app: `python app.py`
3. Access the web UI at `http://<raspberry-pi-ip>:5000/`
4. Access the display page at `http://<raspberry-pi-ip>:5000/display`
5. Access keg management at `http://<raspberry-pi-ip>:5000/manage`
6. Access pour history at `http://<raspberry-pi-ip>:5000/history`

## TODO
- (Optional) Add more advanced stats or analytics for pours
- (Optional) Add undo/soft-delete for kegs
- (Optional) Add notifications/alerts for low volume or empty kegs
- (Optional) Add user authentication for admin actions
- (Optional) Set up iPad as dedicated display:
  - Open Safari to http://[pi-ip]:5000/display
  - Enable Guided Access (Settings → Accessibility → Guided Access)
  - Disable auto-lock (Settings → Display & Brightness → Auto-Lock → Never)
  - Keep iPad plugged in permanently
  - Triple-click home button to lock iPad to Safari

## Flow Meter Integration

Superkeg now supports automatic flow meter monitoring for real-time pour tracking on Raspberry Pi.

### Hardware Requirements
- Raspberry Pi 2 (or newer)
- Flow meter(s) - supported models:
  - **YF-S201**: ~450 pulses/L, 1-30 L/min (recommended for beer)
  - **YF-S401**: ~5880 pulses/L, 0.3-6 L/min (high precision)
  - **YF-B1**: ~1800 pulses/L, 1-25 L/min
- Optional: 10kΩ pull-up resistors

### Hardware Setup
```
Flow Meter Wiring (typical 3-wire):
  Red wire (VCC)    → Raspberry Pi 5V (pin 2 or 4)
  Black wire (GND)  → Raspberry Pi GND (pin 6, 9, 14, etc.)
  Yellow wire (SIG) → Raspberry Pi GPIO pin (default: GPIO 18)
```

### Software Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Test flow meter connection:**
   ```bash
   python setup_flow_meter.py
   ```

3. **Calibrate flow meter:**
   - Use the setup script's calibration option
   - Pour a known volume (e.g., 500ml) through the meter
   - Script will calculate pulses per liter

4. **Start the complete system:**
   ```bash
   python start_superkeg.py
   ```
   This starts both the Flask web app and flow meter monitoring in one command!

📋 **For detailed deployment instructions, see [RASPBERRY_PI_SETUP.md](RASPBERRY_PI_SETUP.md)**

### Flow Meter Files
- `flow_meter.py` - Core flow meter tracking module
- `flow_meter_integration.py` - Integration with keg system
- `setup_flow_meter.py` - Setup and calibration tool

### Features
- **Real-time monitoring**: GPIO interrupt-based pulse detection
- **Multi-tap support**: Monitor up to 4 taps simultaneously  
- **Automatic logging**: Pour events logged to database
- **Web API integration**: Updates keg volumes via existing `/api/flow/` endpoint
- **Calibration**: Built-in calibration system for accuracy
- **Simulation mode**: Works without GPIO for testing

### Usage Examples

**Single flow meter:**
```python
from flow_meter import FlowMeter

flow_meter = FlowMeter(gpio_pin=18, pulses_per_liter=450.0)
flow_meter.start_monitoring()
# Monitor flow_meter.volume_total for dispensed volume
```

**Integrated with keg tracking:**
```python
from flow_meter_integration import MultiTapFlowSystem

# Configure taps (GPIO pins and calibration)
tap_configs = [
    {"tap_number": 1, "gpio_pin": 18, "pulses_per_liter": 450.0},
    {"tap_number": 2, "gpio_pin": 19, "pulses_per_liter": 450.0},
]

system = MultiTapFlowSystem(tap_configs)
system.start_all()
```

## Future Tasks / Ideas
- User management and access control
- Notifications/alerts for low volume or empty kegs
- Export data (CSV, JSON)
- Remote monitoring and control
- Flow rate alerts and anomaly detection
- Temperature sensor integration

## Database
This app uses SQLite for local storage by default (file: `kegs.db`). No PostgreSQL server is required. The database file will be created automatically.
