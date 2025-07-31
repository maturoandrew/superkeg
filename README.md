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

## Future Tasks / Ideas
- User management and access control
- Keg history and usage logs (track every pour)
- Notifications/alerts for low volume or empty kegs
- Export data (CSV, JSON)
- Support for multiple taps/flow meters
- Remote monitoring and control

## Database
This app uses SQLite for local storage by default (file: `kegs.db`). No PostgreSQL server is required. The database file will be created automatically.
