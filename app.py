from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from keg_app import SessionLocal, input_new_keg, tap_new_keg, tap_previous_keg, take_keg_off_tap, Keg, KegStatus, subtract_volume

app = Flask(__name__)

template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Keg Manager</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head>
<body class="container py-4">
    <h1>Keg Manager</h1>
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
        <thead><tr><th>ID</th><th>Name</th><th>Style</th><th>Brewer</th><th>ABV</th><th>Volume</th><th>Status</th><th>Last Tapped</th><th>Finished</th><th>Actions</th></tr></thead>
        <tbody>
        {% for keg in kegs %}
        <tr>
            <td>{{ keg.id }}</td>
            <td>{{ keg.name }}</td>
            <td>{{ keg.style }}</td>
            <td>{{ keg.brewer }}</td>
            <td>{{ keg.abv }}</td>
            <td>{{ keg.volume_remaining }}</td>
            <td>{{ keg.status.value }}</td>
            <td>{{ keg.date_last_tapped or '' }}</td>
            <td>{{ keg.date_finished or '' }}</td>
            <td>
                {% if keg.status == keg_status.UNTAPPED %}
                    <a href="/tap_new/{{ keg.id }}" class="btn btn-success btn-sm">Tap New</a>
                {% elif keg.status == keg_status.OFF_TAP %}
                    <a href="/tap_previous/{{ keg.id }}" class="btn btn-warning btn-sm">Tap Again</a>
                {% elif keg.status == keg_status.TAPPED %}
                    <a href="/off_tap/{{ keg.id }}" class="btn btn-danger btn-sm">Take Off Tap</a>
                {% endif %}
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
        .keg-card { margin-bottom: 2rem; }
    </style>
</head>
<body class="container py-4">
    <h1>Currently Tapped Kegs</h1>
    <a href="/" class="btn btn-secondary mb-4">View Full Catalog</a>
    <div class="row">
    {% for keg in kegs %}
        <div class="col-md-6 keg-card">
            <div class="card">
                <div class="card-body">
                    <h2 class="card-title">{{ keg.name }}</h2>
                    <p class="card-text"><strong>Brewer:</strong> {{ keg.brewer }}</p>
                    <p class="card-text"><strong>Style:</strong> {{ keg.style }}</p>
                    <p class="card-text"><strong>ABV:</strong> {{ keg.abv }}%</p>
                    <p class="card-text"><strong>Volume Remaining:</strong> {{ keg.volume_remaining }} L</p>
                    <p class="card-text"><strong>Last Tapped:</strong> {{ keg.date_last_tapped or 'N/A' }}</p>
                </div>
            </div>
        </div>
    {% else %}
        <p>No kegs are currently tapped.</p>
    {% endfor %}
    </div>
</body>
</html>
'''

@app.route("/")
def index():
    session = SessionLocal()
    kegs = session.query(Keg).all()
    session.close()
    return render_template_string(template, kegs=kegs, keg_status=KegStatus)

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
    return redirect(url_for("index"))

@app.route("/tap_new/<int:keg_id>")
def tap_new(keg_id):
    session = SessionLocal()
    tap_new_keg(session, keg_id)
    session.close()
    return redirect(url_for("index"))

@app.route("/tap_previous/<int:keg_id>")
def tap_previous(keg_id):
    session = SessionLocal()
    tap_previous_keg(session, keg_id)
    session.close()
    return redirect(url_for("index"))

@app.route("/off_tap/<int:keg_id>")
def off_tap(keg_id):
    session = SessionLocal()
    take_keg_off_tap(session, keg_id)
    session.close()
    return redirect(url_for("index"))

@app.route("/display")
def display():
    session = SessionLocal()
    kegs = session.query(Keg).filter(Keg.status == KegStatus.TAPPED).all()
    session.close()
    return render_template_string(display_template, kegs=kegs)

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
    keg = subtract_volume(session, keg_id, volume_dispensed)
    session.close()
    if keg:
        return jsonify({'success': True, 'keg_id': keg.id, 'volume_remaining': keg.volume_remaining}), 200
    else:
        return jsonify({'success': False, 'error': 'Keg not found or not tapped'}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True) 