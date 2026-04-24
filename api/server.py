"""
Outscale Cloud Estimator — Backend API
Stack : Python 3 + Flask + PyJWT + bcrypt
Port  : 5000 (proxifié par nginx sur /api/)
"""

import json
import os
import hashlib
import secrets
import shutil
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify, abort
from flask_cors import CORS

try:
    import jwt
    import bcrypt
except ImportError:
    raise SystemExit("Dépendances manquantes. Lancer : pip3 install flask flask-cors pyjwt bcrypt")

# ── Chemins ────────────────────────────────────────────────────────────────────
BASE   = Path(__file__).parent.parent
DATA   = BASE / "data"
HIST   = DATA / "history"
HIST.mkdir(parents=True, exist_ok=True)

CATALOG_F  = DATA / "catalog.json"
FORMULAS_F = DATA / "formulas.json"
REGIONS_F  = DATA / "regions.json"
CONFIG_F   = DATA / "config.json"

# ── App ────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ── Helpers JSON ───────────────────────────────────────────────────────────────
def read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

def load_config() -> dict:
    return read_json(CONFIG_F)

# ── Snapshot ───────────────────────────────────────────────────────────────────
def make_snapshot(kind: str, data: dict, author: str, comment: str = "") -> str:
    ts   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{ts}_{kind}.json"
    payload = {
        "snapshot_at":  ts,
        "snapshot_kind": kind,
        "author":        author,
        "comment":       comment,
        "data":          data,
    }
    write_json(HIST / name, payload)
    _prune_history()
    return name

def _prune_history() -> None:
    cfg   = load_config()
    limit = int(cfg.get("history_max_snapshots", 100))
    files = sorted(HIST.glob("*.json"))
    for f in files[:-limit]:
        f.unlink(missing_ok=True)

# ── Auth JWT ───────────────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            abort(401)
        token = header[7:]
        cfg   = load_config()
        secret = cfg.get("jwt_secret", "")
        if not secret:
            abort(500)
        try:
            jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            abort(401)
        except jwt.InvalidTokenError:
            abort(401)
        return f(*args, **kwargs)
    return decorated

# ── Route : login ──────────────────────────────────────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def login():
    body     = request.get_json(force=True) or {}
    password = body.get("password", "")
    cfg      = load_config()
    stored   = cfg.get("admin_password_hash", "")
    secret   = cfg.get("jwt_secret", "")

    if not stored or not secret:
        return jsonify({"error": "Admin non configuré. Lancer setup.py d'abord."}), 503

    ok = bcrypt.checkpw(password.encode(), stored.encode())
    if not ok:
        return jsonify({"error": "Mot de passe incorrect"}), 401

    ttl   = int(cfg.get("session_ttl_hours", 8))
    token = jwt.encode(
        {"sub": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=ttl)},
        secret, algorithm="HS256"
    )
    return jsonify({"token": token, "ttl_hours": ttl})

# ── Route : catalogue ──────────────────────────────────────────────────────────
@app.route("/api/catalog", methods=["GET"])
def get_catalog():
    return jsonify(read_json(CATALOG_F))

@app.route("/api/catalog", methods=["PUT"])
@require_auth
def put_catalog():
    body    = request.get_json(force=True) or {}
    comment = body.pop("_comment", "")
    author  = body.pop("_author", "admin")
    current = read_json(CATALOG_F)
    make_snapshot("catalog", current, author, comment)
    body["_meta"] = {
        "version":    current.get("_meta", {}).get("version", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": author,
        "comment":    comment,
    }
    write_json(CATALOG_F, body)
    return jsonify({"ok": True})

# ── Route : formules ───────────────────────────────────────────────────────────
@app.route("/api/formulas", methods=["GET"])
def get_formulas():
    return jsonify(read_json(FORMULAS_F))

@app.route("/api/formulas", methods=["PUT"])
@require_auth
def put_formulas():
    body    = request.get_json(force=True) or {}
    comment = body.pop("_comment", "")
    author  = body.pop("_author", "admin")
    current = read_json(FORMULAS_F)
    make_snapshot("formulas", current, author, comment)
    body["_meta"] = {
        "version":    current.get("_meta", {}).get("version", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": author,
        "comment":    comment,
    }
    write_json(FORMULAS_F, body)
    return jsonify({"ok": True})

# ── Route : régions ────────────────────────────────────────────────────────────
@app.route("/api/regions", methods=["GET"])
def get_regions():
    return jsonify(read_json(REGIONS_F))

@app.route("/api/regions", methods=["PUT"])
@require_auth
def put_regions():
    body    = request.get_json(force=True) or {}
    comment = body.pop("_comment", "")
    author  = body.pop("_author", "admin")
    current = read_json(REGIONS_F)
    make_snapshot("regions", current, author, comment)
    body["_meta"] = {
        "version":    current.get("_meta", {}).get("version", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": author,
        "comment":    comment,
    }
    write_json(REGIONS_F, body)
    return jsonify({"ok": True})

# ── Route : historique ─────────────────────────────────────────────────────────
@app.route("/api/history", methods=["GET"])
@require_auth
def list_history():
    kind = request.args.get("kind")  # optionnel : catalog | formulas | regions
    files = sorted(HIST.glob("*.json"), reverse=True)
    result = []
    for f in files:
        if kind and f"_{kind}." not in f.name:
            continue
        try:
            meta = read_json(f)
            result.append({
                "id":       f.stem,
                "filename": f.name,
                "at":       meta.get("snapshot_at"),
                "kind":     meta.get("snapshot_kind"),
                "author":   meta.get("author"),
                "comment":  meta.get("comment"),
            })
        except Exception:
            pass
    return jsonify(result)

@app.route("/api/history/<snapshot_id>", methods=["GET"])
@require_auth
def get_snapshot(snapshot_id):
    f = HIST / f"{snapshot_id}.json"
    if not f.exists():
        abort(404)
    return jsonify(read_json(f))

@app.route("/api/history/<snapshot_id>/restore", methods=["POST"])
@require_auth
def restore_snapshot(snapshot_id):
    f = HIST / f"{snapshot_id}.json"
    if not f.exists():
        abort(404)
    snap = read_json(f)
    kind = snap.get("snapshot_kind")
    data = snap.get("data", {})
    targets = {"catalog": CATALOG_F, "formulas": FORMULAS_F, "regions": REGIONS_F}
    target  = targets.get(kind)
    if not target:
        abort(400)
    body    = request.get_json(force=True) or {}
    author  = body.get("author", "admin")
    current = read_json(target)
    make_snapshot(kind, current, author, f"Sauvegarde avant restauration de {snapshot_id}")
    data["_meta"] = {
        "version":    current.get("_meta", {}).get("version", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": author,
        "comment":    f"Restauré depuis {snapshot_id}",
    }
    write_json(target, data)
    return jsonify({"ok": True, "restored_kind": kind})

@app.route("/api/history/<snapshot_id>", methods=["DELETE"])
@require_auth
def delete_snapshot(snapshot_id):
    f = HIST / f"{snapshot_id}.json"
    if not f.exists():
        abort(404)
    f.unlink()
    return jsonify({"ok": True})

# ── Health ─────────────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "ts": datetime.now(timezone.utc).isoformat()})

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
