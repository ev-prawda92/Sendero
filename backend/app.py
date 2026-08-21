"""
Sendero Portfolio — backend
============================
Minimal, real (non-mocked) Flask API around the Sendero classification
engine. This is the first real slice of the product: upload a CSV of
per-investment or per-portfolio-company performance data, run Sendero's
build-vs-training diagnostic on it, and get back a real, computed worklist.

Run locally:
    cd backend
    pip install -r requirements.txt
    python app.py
    # -> http://localhost:5000

No AI assistant, no cross-model verification, no Box sync, no auth yet —
those are deliberately out of scope for this first slice. See
../docs/mvp_roadmap.md for what's next and why this is the right place to
start.
"""
import csv
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request, g
from flask_cors import CORS

from sendero_engine.classify import classify

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "sendero.db")

app = Flask(__name__)
CORS(app)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clusters (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            metric TEXT NOT NULL,
            baseline REAL,
            higher_is_worse INTEGER NOT NULL,
            capability_cols TEXT,
            config_cols TEXT,
            n_rows INTEGER,
            capital_exposed REAL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _recoverable_value(result, capital_exposed):
    """
    Recoverable dollar value = severity x capital exposed x confidence.
    Severity is read off how far the classification sits from a clean 0
    (pure training, nothing wrong) toward either pole, scaled by the
    outlier tail share / body elevation already computed by Sendero.
    This is intentionally simple for v1 -- see docs/mvp_roadmap.md.
    """
    if capital_exposed is None:
        return None
    severity = max(result.get("build_score", 0), result.get("training_score", 0))
    severity = (severity - 0.5) * 2  # rescale 0.5..1.0 -> 0..1
    severity = max(0.0, min(1.0, severity))
    confidence = result.get("confidence_pct", 50) / 100.0
    return round(capital_exposed * severity * confidence, 2)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


@app.route("/api/classify", methods=["POST"])
def classify_upload():
    """
    Accepts a CSV file upload plus form fields:
        name             - human label for this cluster (e.g. "Digital health portfolio")
        metric           - column name to classify on (e.g. "growth_gap_pts")
        baseline         - optional numeric target/baseline
        higher_is_worse  - "true" or "false" (default true)
        capability_cols  - comma-separated column names
        config_cols      - comma-separated column names
        capital_exposed  - optional numeric $ at risk, for the recoverable-value calc

    Runs Sendero's classify() engine for real on the uploaded rows, stores
    the result, and returns it. Nothing here is mocked.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded — expected multipart field 'file'."}), 400

    f = request.files["file"]
    name = request.form.get("name", f.filename or "Untitled cluster")
    metric = request.form.get("metric")
    if not metric:
        return jsonify({"error": "Missing required field 'metric' (the CSV column to classify on)."}), 400

    baseline = request.form.get("baseline")
    baseline = float(baseline) if baseline not in (None, "") else None
    higher_is_worse = request.form.get("higher_is_worse", "true").lower() != "false"
    capability_cols = [c.strip() for c in request.form.get("capability_cols", "").split(",") if c.strip()]
    config_cols = [c.strip() for c in request.form.get("config_cols", "").split(",") if c.strip()]
    capital_exposed = request.form.get("capital_exposed")
    capital_exposed = float(capital_exposed) if capital_exposed not in (None, "") else None

    try:
        text = f.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"error": "Could not read file as UTF-8 CSV."}), 400

    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return jsonify({"error": "CSV has no data rows."}), 400
    if metric not in reader.fieldnames:
        return jsonify({"error": f"Column '{metric}' not found. Columns are: {reader.fieldnames}"}), 400

    result = classify(
        rows,
        metric=metric,
        baseline=baseline,
        higher_is_worse=higher_is_worse,
        capability_cols=capability_cols,
        config_cols=config_cols,
    )
    if "error" in result:
        return jsonify(result), 400

    result["recoverable_value"] = _recoverable_value(result, capital_exposed)
    result["capital_exposed"] = capital_exposed
    result["name"] = name

    cluster_id = str(uuid.uuid4())
    db = get_db()
    db.execute(
        """INSERT INTO clusters
           (id, name, metric, baseline, higher_is_worse, capability_cols, config_cols,
            n_rows, capital_exposed, result_json, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            cluster_id, name, metric, baseline, int(higher_is_worse),
            ",".join(capability_cols), ",".join(config_cols),
            len(rows), capital_exposed, json.dumps(result),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()

    result["id"] = cluster_id
    return jsonify(result), 201


@app.route("/api/worklist", methods=["GET"])
def worklist():
    """
    Real ranked worklist: every classified cluster stored so far, ranked by
    recoverable value descending -- the same "ranked worklist" concept from
    the product mockups, but computed from actually-uploaded data.
    """
    db = get_db()
    rows = db.execute("SELECT * FROM clusters ORDER BY created_at DESC").fetchall()
    items = []
    for r in rows:
        result = json.loads(r["result_json"])
        items.append({
            "id": r["id"],
            "name": r["name"],
            "metric": r["metric"],
            "n_rows": r["n_rows"],
            "capital_exposed": r["capital_exposed"],
            "classification": result.get("classification"),
            "confidence_pct": result.get("confidence_pct"),
            "recoverable_value": result.get("recoverable_value"),
            "created_at": r["created_at"],
        })
    items.sort(key=lambda x: (x["recoverable_value"] or 0), reverse=True)
    return jsonify({"count": len(items), "items": items})


@app.route("/api/clusters/<cluster_id>", methods=["GET"])
def cluster_detail(cluster_id):
    db = get_db()
    row = db.execute("SELECT * FROM clusters WHERE id = ?", (cluster_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Not found"}), 404
    result = json.loads(row["result_json"])
    result["id"] = row["id"]
    result["name"] = row["name"]
    result["created_at"] = row["created_at"]
    return jsonify(result)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
