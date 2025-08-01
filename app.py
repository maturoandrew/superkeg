# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, send_file, Response
import csv
import os
from keg_app import SessionLocal, input_new_keg, tap_new_keg, tap_previous_keg, take_keg_off_tap, Keg, KegStatus, subtract_volume, log_pour_event, PourEvent
import random
from datetime import datetime

app = Flask(__name__)

# Add dark mode CSS and toggle to all templates
DARK_MODE_HEAD = '''
<style id="dark-mode-style">
:root[data-theme='dark'] {
  --bs-body-bg: #181a1b;
  --bs-body-color: #f8f9fa;
  --bs-card-bg: #23272b;
  --bs-card-color: #f8f9fa;
  --bs-border-color: #444;
}
[data-theme='dark'] body { background: var(--bs-body-bg) !important; color: var(--bs-body-color) !important; }
[data-theme='dark'] .card { background: var(--bs-card-bg) !important; color: var(--bs-card-color) !important; border-color: var(--bs-border-color) !important; }
[data-theme='dark'] .table { color: var(--bs-body-color) !important; }
[data-theme='dark'] .btn { color: #fff !important; }
</style>
<script>
function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}
function toggleTheme() {
  const theme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  setTheme(theme);
  document.getElementById('theme-toggle').innerText = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
}
window.onload = function() {
  let theme = localStorage.getItem('theme') || 'light';
  setTheme(theme);
  if (document.getElementById('theme-toggle')) {
    document.getElementById('theme-toggle').innerText = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
  }
}
</script>
'''

template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Keg Manager</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        .keg-row { display: flex; flex-wrap: nowrap; justify-content: center; }
        .keg-card { flex: 1 1 0; max-width: 25%; min-width: 220px; margin: 0 1rem; }
        .low-volume { border: 3px solid #dc3545 !important; box-shadow: 0 0 10px #dc3545; }
        .tap-label { font-weight: bold; font-size: 1.2rem; color: #0d6efd; text-align: center; margin-bottom: 0.5rem; }
        .notification { position: fixed; top: 20px; right: 20px; z-index: 9999; }
        @media (max-width: 900px) {
            .keg-row { flex-wrap: wrap; }
            .keg-card { max-width: 100%; margin: 1rem 0; }
        }
    </style>
</head>
<body class="container py-4">
    <button id="theme-toggle" class="btn btn-outline-secondary float-end mb-2" onclick="toggleTheme()">Dark Mode</button>
    <h1>Currently Tapped Kegs</h1>
    <a href="/manage" class="btn btn-primary mb-4">Keg Management</a>
    <div class="keg-row">
    {% for keg in kegs %}
        <div class="card keg-card {% if keg.volume_remaining < 0.1 * (keg.original_volume or keg.volume_remaining) %}low-volume{% endif %}">
            <div class="tap-label">Tap {{ keg.tap_position }}</div>
            <div class="card-body">
                <h2 class="card-title">{{ keg.name }} {% if keg.volume_remaining < 0.1 * (keg.original_volume or keg.volume_remaining) %}<span title="Low Volume" style="color:#dc3545;">!</span>{% endif %}</h2>
                <p class="card-text"><strong>Brewer:</strong> {{ keg.brewer }}</p>
                <p class="card-text"><strong>Style:</strong> {{ keg.style }}</p>
                <p class="card-text"><strong>ABV:</strong> {{ keg.abv }}%</p>
                <p class="card-text"><strong>Volume Remaining:</strong> {{ "%.2f"|format(keg.volume_remaining) }} L</p>
                <p class="card-text"><strong>Last Tapped:</strong> {{ keg.date_last_tapped or 'N/A' }}</p>
            </div>
        </div>
    {% else %}
        <p>No kegs are currently tapped.</p>
    {% endfor %}
    </div>
    
    <!-- Notification container -->
    <div id="notification-container"></div>
    
    <script>
    // Function to show pour notification
    function showPourNotification(kegName, volumeLiters, volumeOz) {
        const container = document.getElementById('notification-container');
        const notification = document.createElement('div');
        notification.className = 'alert alert-success notification';
        notification.innerHTML = `
            <strong>[BEER] Beer Poured!</strong><br>
            <strong>${kegName}</strong><br>
            ${volumeLiters.toFixed(2)}L (${volumeOz.toFixed(1)}oz)
        `;
        
        container.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
    
    // Check for new pours every 2 seconds
    setInterval(() => {
        fetch('/api/recent-pours')
            .then(response => response.json())
            .then(data => {
                if (data.pours && data.pours.length > 0) {
                    data.pours.forEach(pour => {
                        showPourNotification(pour.keg_name, pour.volume_liters, pour.volume_oz);
                    });
                }
            })
            .catch(error => console.log('No recent pours'));
    }, 2000);
    </script>
</body>
</html>
'''

management_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Keg Management</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <script>
    function confirmDelete(kegId) {
        if (confirm('Are you sure you want to permanently delete this keg?')) {
            document.getElementById('delete-form-' + kegId).submit();
        }
    }
    function confirmFinish(kegId) {
        if (confirm('Mark this keg as finished?')) {
            document.getElementById('finish-form-' + kegId).submit();
        }
    }
    </script>
</head>
<body class="container py-4">
    <button id="theme-toggle" class="btn btn-outline-secondary float-end mb-2" onclick="toggleTheme()">Dark Mode</button>
    <h1>Keg Management</h1>
    <a href="/" class="btn btn-secondary mb-4">Back to Tapped Kegs</a>
    <a href="/download_db" class="btn btn-outline-primary mb-4 ms-2">Download DB</a>
    <a href="/export_csv" class="btn btn-outline-success mb-4 ms-2">Export CSV</a>
    <a href="/export_pour_history" class="btn btn-outline-warning mb-4 ms-2">Export Pour History</a>
    <a href="/download_full_pour_history" class="btn btn-outline-danger mb-4 ms-2">Download Full Pour History</a>
    
    <h2>Add New Keg</h2>
    <form method="post" action="/add">
        <div class="mb-2"><input class="form-control" name="name" placeholder="Name" required></div>
        <div class="mb-2"><input class="form-control" name="style" placeholder="Style" required></div>
        <div class="mb-2"><input class="form-control" name="brewer" placeholder="Brewer" required></div>
        <div class="mb-2"><input class="form-control" name="abv" placeholder="ABV (%)" type="number" step="0.1" required></div>
        <div class="mb-2"><input class="form-control" name="volume_remaining" placeholder="Volume (L)" type="number" step="0.1" required></div>
        <button class="btn btn-primary" type="submit">Add Keg</button>
    </form>
    
    <h2 class="mt-4">All Kegs</h2>
    <table class="table table-bordered">
        <thead><tr><th>ID</th><th>Name</th><th>Style</th><th>Brewer</th><th>ABV</th><th>Volume</th><th>Tap</th><th>Status</th><th>Last Tapped</th><th>Finished</th><th>Actions</th></tr></thead>
        <tbody>
        {% for keg in kegs %}
        <tr>
            <td>{{ keg.id }}</td>
            <td>{{ keg.name }}</td>
            <td>{{ keg.style }}</td>
            <td>{{ keg.brewer }}</td>
            <td>{{ keg.abv }}</td>
            <td>{{ "%.2f"|format(keg.volume_remaining) }}</td>
            <td>{{ keg.tap_position or '' }}</td>
            <td>{{ keg.status.value }}</td>
            <td>{{ keg.date_last_tapped or '' }}</td>
            <td>{{ keg.date_finished or '' }}</td>
            <td>
                {% if keg.status == keg_status.UNTAPPED %}
                    <a href="/edit/{{ keg.id }}" class="btn btn-info btn-sm">Edit</a>
                    <a href="/tap_new/{{ keg.id }}" class="btn btn-success btn-sm">Tap New</a>
                {% elif keg.status == keg_status.OFF_TAP %}
                    <a href="/edit/{{ keg.id }}" class="btn btn-info btn-sm">Edit</a>
                    <a href="/tap_previous/{{ keg.id }}" class="btn btn-warning btn-sm">Tap Again</a>
                {% elif keg.status == keg_status.TAPPED %}
                    <a href="/edit/{{ keg.id }}" class="btn btn-info btn-sm">Edit</a>
                    <a href="/off_tap/{{ keg.id }}" class="btn btn-danger btn-sm">Take Off Tap</a>
                    <form id="finish-form-{{ keg.id }}" method="post" action="/finish/{{ keg.id }}" style="display:inline;">
                        <button type="button" class="btn btn-secondary btn-sm" onclick="confirmFinish({{ keg.id }})">Finish</button>
                    </form>
                {% endif %}
                <form id="delete-form-{{ keg.id }}" method="post" action="/delete/{{ keg.id }}" style="display:inline;">
                    <button type="button" class="btn btn-outline-danger btn-sm" onclick="confirmDelete({{ keg.id }})">Delete</button>
                </form>
            </td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
</body>
</html>
'''

display_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Currently Tapped Kegs</title>
    <meta http-equiv="refresh" content="10">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        body { font-size: 1.5rem; }
        .keg-row { display: flex; flex-wrap: nowrap; justify-content: center; }
        .keg-card { flex: 1 1 0; max-width: 25%; min-width: 220px; margin: 0 1rem; }
        .low-volume { border: 3px solid #dc3545 !important; box-shadow: 0 0 10px #dc3545; }
        .tap-label { font-weight: bold; font-size: 1.2rem; color: #0d6efd; text-align: center; margin-bottom: 0.5rem; }
        @media (max-width: 900px) {
            .keg-row { flex-wrap: wrap; }
            .keg-card { max-width: 100%; margin: 1rem 0; }
        }
    </style>
</head>
<body class="container py-4">
    <button id="theme-toggle" class="btn btn-outline-secondary float-end mb-2" onclick="toggleTheme()">Dark Mode</button>
    <h1>Currently Tapped Kegs</h1>
    <a href="/manage" class="btn btn-secondary mb-4">Keg Management</a>
    <div class="keg-row">
    {% for keg in kegs %}
        <div class="card keg-card {% if keg.volume_remaining < 0.1 * (keg.original_volume or keg.volume_remaining) %}low-volume{% endif %}">
            <div class="tap-label">Tap {{ keg.tap_position }}</div>
            <div class="card-body">
                <h2 class="card-title">{{ keg.name }} {% if keg.volume_remaining < 0.1 * (keg.original_volume or keg.volume_remaining) %}<span title="Low Volume" style="color:#dc3545;">!</span>{% endif %}</h2>
                <p class="card-text"><strong>Brewer:</strong> {{ keg.brewer }}</p>
                <p class="card-text"><strong>Style:</strong> {{ keg.style }}</p>
                <p class="card-text"><strong>ABV:</strong> {{ keg.abv }}%</p>
                <p class="card-text"><strong>Volume Remaining:</strong> {{ "%.2f"|format(keg.volume_remaining) }} L</p>
                <p class="card-text"><strong>Last Tapped:</strong> {{ keg.date_last_tapped or 'N/A' }}</p>
            </div>
        </div>
    {% else %}
        <p>No kegs are currently tapped.</p>
    {% endfor %}
    </div>
</body>
</html>
'''

edit_keg_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Edit Keg</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head>
<body class="container py-4">
    <button id="theme-toggle" class="btn btn-outline-secondary float-end mb-2" onclick="toggleTheme()">Dark Mode</button>
    <h1>Edit Keg</h1>
    <a href="/manage" class="btn btn-secondary mb-4">Back to Management</a>
    <form method="post">
        <div class="mb-2"><input class="form-control" name="name" placeholder="Name" value="{{ keg.name }}" required></div>
        <div class="mb-2"><input class="form-control" name="style" placeholder="Style" value="{{ keg.style }}" required></div>
        <div class="mb-2"><input class="form-control" name="brewer" placeholder="Brewer" value="{{ keg.brewer }}" required></div>
        <div class="mb-2"><input class="form-control" name="abv" placeholder="ABV (%)" type="number" step="0.1" value="{{ keg.abv }}" required></div>
        <div class="mb-2"><input class="form-control" name="volume_remaining" placeholder="Volume (L)" type="number" step="0.1" value="{{ keg.volume_remaining }}" required></div>
        <div class="mb-2"><input class="form-control" name="original_volume" placeholder="Original Volume (L)" type="number" step="0.1" value="{{ keg.original_volume or keg.volume_remaining }}" required></div>
        <button class="btn btn-primary" type="submit">Save Changes</button>
    </form>
</body>
</html>
'''

history_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Pour History</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head>
<body class="container py-4">
    <button id="theme-toggle" class="btn btn-outline-secondary float-end mb-2" onclick="toggleTheme()">Dark Mode</button>
    <h1>Pour History</h1>
    <a href="/manage" class="btn btn-secondary mb-4">Back to Management</a>
    <table class="table table-bordered">
        <thead><tr><th>Time</th><th>Keg</th><th>Volume (L)</th></tr></thead>
        <tbody>
        {% for event in events %}
        <tr>
            <td>{{ event.timestamp }}</td>
            <td>{{ keg_map.get(event.keg_id, 'Unknown') }}</td>
            <td>{{ '%.2f'|format(event.volume_dispensed) }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
</body>
</html>
'''

def get_cheers_message():
    cheers_messages = [
        "Cheers!",
        "Prost!",
        "Salud!",
        "Skal!",
        "Cheers mate!",
        "Here's to you!",
        "Bottoms up!",
        "Cheers to that!",
        "Here's looking at you!",
        "Slainte!"
    ]
    return random.choice(cheers_messages)

def get_pour_comment(volume_oz):
    if volume_oz < 5:
        sample_messages = [
            "Oh, just a sample?",
            "Tasting flight size!",
            "Just a little sip?",
            "Keeping it light!",
            "Sample size pour!"
        ]
        return random.choice(sample_messages)
    elif volume_oz > 12:
        generous_messages = [
            "Now that's a generous pour!",
            "Going big!",
            "That's a proper pint!",
            "Living large!",
            "Now we're talking!"
        ]
        return random.choice(generous_messages)
    else:
        return ""

def is_low_volume(keg):
    orig = getattr(keg, 'original_volume', None)
    if orig is None or orig == 0:
        orig = keg.volume_remaining
    return orig > 0 and keg.volume_remaining < 0.1 * orig

@app.route("/")
def index():
    session = SessionLocal()
    kegs = session.query(Keg).filter(Keg.status == KegStatus.TAPPED).order_by(Keg.tap_position).all()
    session.close()
    return render_template_string(template, kegs=kegs, keg_status=KegStatus)

@app.route("/manage")
def manage():
    session = SessionLocal()
    kegs = session.query(Keg).all()
    session.close()
    return render_template_string(management_template, kegs=kegs, keg_status=KegStatus)

@app.route("/add", methods=["POST"])
def add_keg():
    session = SessionLocal()
    input_new_keg(
        session,
        name=request.form["name"],
        style=request.form["style"],
        brewer=request.form["brewer"],
        abv=float(request.form["abv"]),
        volume_remaining=float(request.form["volume_remaining"])
    )
    session.close()
    return redirect(url_for("manage"))

@app.route("/tap_new/<int:keg_id>")
def tap_new(keg_id):
    session = SessionLocal()
    tap_new_keg(session, keg_id)
    session.close()
    return redirect(url_for("manage"))

@app.route("/tap_previous/<int:keg_id>")
def tap_previous(keg_id):
    session = SessionLocal()
    tap_previous_keg(session, keg_id)
    session.close()
    return redirect(url_for("manage"))

@app.route("/off_tap/<int:keg_id>")
def off_tap(keg_id):
    session = SessionLocal()
    take_keg_off_tap(session, keg_id)
    session.close()
    return redirect(url_for("manage"))

@app.route("/display")
def display():
    session = SessionLocal()
    kegs = session.query(Keg).filter(Keg.status == KegStatus.TAPPED).order_by(Keg.tap_position).all()
    session.close()
    return render_template_string(display_template, kegs=kegs)

@app.route("/history")
def pour_history():
    session = SessionLocal()
    events = session.query(PourEvent).order_by(PourEvent.timestamp.desc()).limit(100).all()
    kegs = session.query(Keg).all()
    keg_map = {k.id: k.name + " (" + k.brewer + ")" for k in kegs}
    session.close()
    return render_template_string(history_template, events=events, keg_map=keg_map)

@app.route('/api/flow/<int:keg_id>', methods=['POST'])
def flow_update(keg_id):
    data = request.get_json()
    if not data or 'volume_dispensed' not in data:
        return jsonify({'success': False, 'error': 'Missing volume_dispensed'}), 400
    try:
        volume_dispensed = float(data['volume_dispensed'])
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid volume_dispensed'}), 400
    
    session = SessionLocal()
    try:
        # Get the keg first
        keg = session.query(Keg).filter(Keg.id == keg_id, Keg.status == KegStatus.TAPPED).first()
        if keg:
            # Update the volume
            keg.volume_remaining = max(0, keg.volume_remaining - volume_dispensed)
            
            # Log the pour event
            from datetime import datetime
            event = PourEvent(keg_id=keg_id, volume_dispensed=volume_dispensed, timestamp=datetime.utcnow())
            session.add(event)
            
            session.commit()
            
            # Get final volume before closing
            final_volume = keg.volume_remaining
            
            # Convert to ounces for message logic (assuming volume_dispensed is in liters)
            volume_oz = volume_dispensed * 33.814  # Convert liters to ounces
            
            cheers_msg = get_cheers_message()
            pour_comment = get_pour_comment(volume_oz)
            
            response = {
                'success': True, 
                'keg_id': keg.id, 
                'volume_remaining': final_volume,
                'message': cheers_msg,
                'pour_comment': pour_comment
            }
            session.close()
            return jsonify(response), 200
        else:
            session.close()
            return jsonify({'success': False, 'error': 'Keg not found or not tapped'}), 404
    except Exception as e:
        session.close()
        return jsonify({'success': False, 'error': 'Database error: %s' % str(e)}), 500

@app.route('/api/recent-pours')
def recent_pours():
    """Get recent pour events for notifications."""
    try:
        session = SessionLocal()
        # Get pour events from the last 10 seconds
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(seconds=10)
        
        recent_events = session.query(PourEvent).filter(
            PourEvent.timestamp >= cutoff_time
        ).order_by(PourEvent.timestamp.desc()).all()
        
        # Get keg names for the events
        keg_ids = [event.keg_id for event in recent_events]
        kegs = session.query(Keg).filter(Keg.id.in_(keg_ids)).all()
        keg_map = {keg.id: keg.name for keg in kegs}
        
        pours = []
        for event in recent_events:
            keg_name = keg_map.get(event.keg_id, 'Unknown Keg')
            volume_oz = event.volume_dispensed * 33.814  # Convert liters to ounces
            pours.append({
                'keg_name': keg_name,
                'volume_liters': event.volume_dispensed,
                'volume_oz': volume_oz,
                'timestamp': event.timestamp.isoformat()
            })
        
        session.close()
        return jsonify({'pours': pours})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/delete/<int:keg_id>", methods=["POST"])
def delete_keg(keg_id):
    session = SessionLocal()
    keg = session.query(Keg).filter(Keg.id == keg_id).first()
    if keg:
        session.delete(keg)
        session.commit()
    session.close()
    return redirect(url_for("manage"))

@app.route("/finish/<int:keg_id>", methods=["POST"])
def finish_keg(keg_id):
    session = SessionLocal()
    keg = session.query(Keg).filter(Keg.id == keg_id).first()
    if keg and keg.status == KegStatus.TAPPED:
        keg.status = KegStatus.OFF_TAP
        keg.date_finished = datetime.utcnow()
        session.commit()
    session.close()
    return redirect(url_for("manage"))

@app.route("/edit/<int:keg_id>", methods=["GET", "POST"])
def edit_keg(keg_id):
    session = SessionLocal()
    keg = session.query(Keg).filter(Keg.id == keg_id).first()
    if not keg:
        session.close()
        return redirect(url_for("manage"))
    if request.method == "POST":
        keg.name = request.form["name"]
        keg.style = request.form["style"]
        keg.brewer = request.form["brewer"]
        keg.abv = float(request.form["abv"])
        keg.volume_remaining = float(request.form["volume_remaining"])
        keg.original_volume = float(request.form["original_volume"])
        session.commit()
        session.close()
        return redirect(url_for("manage"))
    session.close()
    return render_template_string(edit_keg_template, keg=keg)

@app.route("/download_db")
def download_db():
    db_path = os.path.abspath("kegs.db")
    return send_file(db_path, as_attachment=True)

@app.route("/export_csv")
def export_csv():
    session = SessionLocal()
    kegs = session.query(Keg).all()
    session.close()
    def generate():
        data = [
            ["id", "name", "style", "brewer", "abv", "volume_remaining", "original_volume", "date_created", "date_last_tapped", "date_finished", "status"]
        ]
        for k in kegs:
            data.append([
                k.id, k.name, k.style, k.brewer, k.abv, k.volume_remaining, k.original_volume, k.date_created, k.date_last_tapped, k.date_finished, k.status.value
            ])
        output = []
        writer = csv.writer(output)
        for row in data:
            writer.writerow(row)
        return '\n'.join([','.join(map(str, row)) for row in data])
    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=kegs.csv"})

@app.route("/export_pour_history")
def export_pour_history():
    session = SessionLocal()
    events = session.query(PourEvent).order_by(PourEvent.timestamp.desc()).limit(1000).all()
    kegs = session.query(Keg).all()
    keg_map = {k.id: (k.name, k.brewer) for k in kegs}
    session.close()
    def generate():
        data = [["timestamp", "keg_id", "keg_name", "brewer", "volume_dispensed"]]
        for e in events:
            name, brewer = keg_map.get(e.keg_id, ("Unknown", ""))
            data.append([e.timestamp, e.keg_id, name, brewer, e.volume_dispensed])
        return '\n'.join([','.join(map(str, row)) for row in data])
    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=pour_history.csv"})

@app.route("/download_full_pour_history")
def download_full_pour_history():
    session = SessionLocal()
    events = session.query(PourEvent).order_by(PourEvent.timestamp.desc()).all()
    kegs = session.query(Keg).all()
    keg_map = {k.id: (k.name, k.brewer) for k in kegs}
    session.close()
    def generate():
        data = [["timestamp", "keg_id", "keg_name", "brewer", "volume_dispensed"]]
        for e in events:
            name, brewer = keg_map.get(e.keg_id, ("Unknown", ""))
            data.append([e.timestamp, e.keg_id, name, brewer, e.volume_dispensed])
        return '\n'.join([','.join(map(str, row)) for row in data])
    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=full_pour_history.csv"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True) 