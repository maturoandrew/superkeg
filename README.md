# superkeg

## Overview
Superkeg is a Python application for managing and monitoring beer kegs, designed to run on a Raspberry Pi with a tablet interface. It uses a local SQLite database for storage and provides a web-based UI for easy access and control.

## Current Capabilities
- **Web UI (Flask):**
  - View all kegs and their details (name, style, ABV, volume, status, dates)
  - Add a new keg to the database
  - Tap a new keg, tap a previously tapped keg, or take a keg off tap
  - Tablet-friendly display page (`/display`) showing all currently tapped kegs, auto-refreshing every 10 seconds
  - Button to view the full catalog from the display page
- **Database:**
  - Uses SQLite for local storage (file: `kegs.db`)
  - Keg model includes: name, style, ABV, volume remaining, date created, date last tapped, date finished, and status
- **API:**
  - `/api/flow/<keg_id>` (POST): Accepts JSON `{ "volume_dispensed": float }` to subtract volume from a tapped keg (for flow meter integration)

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Run the app: `python app.py`
3. Access the web UI at `http://<raspberry-pi-ip>:5000/`
4. Access the display page at `http://<raspberry-pi-ip>:5000/display`

## TODO
- Integrate flow meter math for accurate volume dispensed calculation
- Add authentication for admin actions (optional)
- Improve UI for mobile/tablet (dark mode, larger buttons, etc.)
- Add error handling and user feedback for all actions
- Add keg deletion and editing capabilities

## Future Tasks / Ideas
- User management and access control
- Keg history and usage logs (track every pour)
- Notifications/alerts for low volume or empty kegs
- Export data (CSV, JSON)
- Support for multiple taps/flow meters
- Remote monitoring and control

## Database
This app uses SQLite for local storage by default (file: `kegs.db`). No PostgreSQL server is required. The database file will be created automatically.
