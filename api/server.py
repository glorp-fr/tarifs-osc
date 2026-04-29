"""
Outscale Cloud Estimator — Backend API
Stack : Python 3 + Flask + PyJWT + bcrypt
Port  : 5000 (proxifié par nginx sur /api/)
"""

import json
import logging
import logging.handlers
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify, abort, send_file
from flask_cors import CORS

try:
    import jwt
    import bcrypt
except ImportError:
    raise SystemExit("Dépendances manquantes. Lancer : pip3 install flask flask-cors pyjwt bcrypt")

# ── Chemins ────────────────────────────────────────────────────────────────────
BASE     = Path(__file__).parent.parent
DATA     = BASE / "data"
HIST     = DATA / "history"
SIMS_DIR = DATA / "simulations"
LOGS_DIR = BASE / "logs"
HIST.mkdir(parents=True, exist_ok=True)
SIMS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

CATALOG_F  = DATA / "catalog.json"
FORMULAS_F = DATA / "formulas.json"
REGIONS_F  = DATA / "regions.json"
CONFIG_F   = DATA / "config.json"
USERS_F    = DATA / "users.json"

# ── Logger applicatif ──────────────────────────────────────────────────────────
_handler = logging.handlers.RotatingFileHandler(
    LOGS_DIR / "actions.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"))
_handler.formatter.converter = __import__("time").gmtime

action_log = logging.getLogger("osc.actions")
action_log.setLevel(logging.INFO)
action_log.addHandler(_handler)
action_log.propagate = False

def _ip() -> str:
    return (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.remote_addr
        or "-"
    )

def log_action(action: str, uid: str = "-", username: str = "-", detail: str = "") -> None:
    msg = f"{_ip()} | {username}({uid}) | {action}"
    if detail:
        msg += f" | {detail}"
    action_log.info(msg)

# ── App ────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ── Error handlers JSON ────────────────────────────────────────────────────────
@app.errorhandler(400)
def err_400(e): return jsonify({"error": str(e.description)}), 400

@app.errorhandler(401)
def err_401(e): return jsonify({"error": "Non authentifié"}), 401

@app.errorhandler(403)
def err_403(e): return jsonify({"error": "Accès refusé"}), 403

@app.errorhandler(404)
def err_404(e): return jsonify({"error": "Route introuvable"}), 404

@app.errorhandler(409)
def err_409(e): return jsonify({"error": str(e.description)}), 409

@app.errorhandler(500)
def err_500(e): return jsonify({"error": "Erreur serveur"}), 500


# ── Helpers JSON ───────────────────────────────────────────────────────────────
def read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

def load_config() -> dict:
    return read_json(CONFIG_F)

# ── Users ──────────────────────────────────────────────────────────────────────
def load_users() -> dict:
    if not USERS_F.exists():
        return {"users": []}
    return read_json(USERS_F)

def save_users(data: dict) -> None:
    write_json(USERS_F, data)

def find_user_by_username(username: str):
    if not username:
        return None
    lname = username.lower()
    for u in load_users()["users"]:
        if u["username"].lower() == lname:
            return u
    return None

def user_public(u: dict) -> dict:
    return {k: v for k, v in u.items() if k != "password_hash"}

def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_pw(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ── Simulations ────────────────────────────────────────────────────────────────
def load_user_sims(user_id: str) -> list:
    f = SIMS_DIR / f"{user_id}.json"
    if not f.exists():
        return []
    return read_json(f)

def save_user_sims(user_id: str, sims: list) -> None:
    write_json(SIMS_DIR / f"{user_id}.json", sims)

def load_all_sims_with_shares(user_id: str) -> list:
    owned = [{**s, "_owned": True} for s in load_user_sims(user_id)]
    shared = []
    for f in SIMS_DIR.glob("*.json"):
        if f.stem == user_id:
            continue
        try:
            sims = read_json(f)
            if not isinstance(sims, list):
                continue
            for s in sims:
                if user_id in s.get("shared_with", []):
                    shared.append({**s, "_owned": False})
        except Exception:
            pass
    return owned + shared

# ── Snapshot ───────────────────────────────────────────────────────────────────
def make_snapshot(kind: str, data: dict, author: str, comment: str = "") -> str:
    ts      = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name    = f"{ts}_{kind}.json"
    payload = {"snapshot_at": ts, "snapshot_kind": kind,
               "author": author, "comment": comment, "data": data}
    write_json(HIST / name, payload)
    _prune_history()
    return name

def _prune_history() -> None:
    cfg   = load_config()
    limit = int(cfg.get("history_max_snapshots", 100))
    for f in sorted(HIST.glob("*.json"))[:-limit]:
        f.unlink(missing_ok=True)

# ── JWT ────────────────────────────────────────────────────────────────────────
def _jwt_secret() -> str:
    secret = load_config().get("jwt_secret", "")
    if not secret:
        abort(500)
    return secret

def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        abort(401)
    except jwt.InvalidTokenError:
        abort(401)

def _make_token(uid: str, username: str, role: str, company: str = "", ttl_hours: int = 8) -> str:
    return jwt.encode(
        {"sub": uid, "username": username, "role": role, "company": company,
         "exp": datetime.now(timezone.utc) + timedelta(hours=ttl_hours)},
        _jwt_secret(), algorithm="HS256"
    )

# ── Décorateurs ────────────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            abort(401)
        request.current_user = _decode_token(header[7:])
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            abort(401)
        payload = _decode_token(header[7:])
        if payload.get("role") != "admin":
            abort(403)
        request.current_user = payload
        return f(*args, **kwargs)
    return decorated

# ── Auth : login ───────────────────────────────────────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def login():
    body     = request.get_json(force=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password", "")
    cfg      = load_config()

    if not cfg.get("jwt_secret"):
        return jsonify({"error": "Backend non configuré. Lancer setup.py d'abord."}), 503

    user = find_user_by_username(username) if username else None

    if user:
        if not check_pw(password, user["password_hash"]):
            log_action("LOGIN_FAIL", detail=f"username={username}")
            return jsonify({"error": "Identifiants incorrects"}), 401
        uid, uname, role = user["id"], user["username"], user["role"]
        company = user.get("company", "")
    else:
        # Fallback legacy admin (mot de passe seul, compatibilité panel admin)
        stored = cfg.get("admin_password_hash", "")
        if not stored or not check_pw(password, stored):
            log_action("LOGIN_FAIL", detail=f"username={username or '<vide>'}")
            return jsonify({"error": "Identifiants incorrects"}), 401
        uid, uname, role, company = "admin", (username or "admin"), "admin", ""

    ttl   = int(cfg.get("session_ttl_hours", 8))
    token = _make_token(uid, uname, role, company, ttl)
    log_action("LOGIN_OK", uid=uid, username=uname, detail=f"role={role}")
    return jsonify({"token": token, "ttl_hours": ttl,
                    "user": {"id": uid, "username": uname, "role": role, "company": company}})

# ── Auth : register ────────────────────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
def register():
    body     = request.get_json(force=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password", "")

    if len(username) < 3:
        return jsonify({"error": "Identifiant trop court (min 3 caractères)"}), 400
    if len(password) < 6:
        return jsonify({"error": "Mot de passe trop court (min 6 caractères)"}), 400
    if find_user_by_username(username):
        return jsonify({"error": "Cet identifiant est déjà utilisé"}), 409

    cfg = load_config()
    if not cfg.get("jwt_secret"):
        return jsonify({"error": "Backend non configuré"}), 503

    company    = (body.get("company") or "").strip()
    users_data = load_users()
    new_user   = {
        "id":            secrets.token_hex(8),
        "username":      username,
        "password_hash": hash_pw(password),
        "role":          "prospect",
        "company":       company,
        "created_at":    datetime.now(timezone.utc).isoformat(),
    }
    users_data["users"].append(new_user)
    save_users(users_data)

    ttl   = int(cfg.get("session_ttl_hours", 8))
    token = _make_token(new_user["id"], username, "prospect", company, ttl)
    log_action("REGISTER", uid=new_user["id"], username=username, detail=f"company={company or '-'}")
    return jsonify({"token": token,
                    "user": {"id": new_user["id"], "username": username, "role": "prospect", "company": company}}), 201

# ── Auth : me ──────────────────────────────────────────────────────────────────
@app.route("/api/auth/me", methods=["GET"])
@require_auth
def me():
    u = request.current_user
    return jsonify({"id": u.get("sub"), "username": u.get("username"), "role": u.get("role")})

# ── Users (admin) ──────────────────────────────────────────────────────────────
@app.route("/api/users", methods=["GET"])
@require_admin
def list_users():
    return jsonify([user_public(u) for u in load_users()["users"]])

@app.route("/api/users", methods=["POST"])
@require_auth
def create_user():
    caller      = request.current_user
    caller_role = caller.get("role")
    if caller_role not in ("outscale", "admin"):
        abort(403)

    body     = request.get_json(force=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password", "")
    role     = body.get("role", "prospect")

    if caller_role == "outscale" and role != "prospect":
        return jsonify({"error": "Les utilisateurs Outscale ne peuvent créer que des comptes prospect"}), 403
    if role not in ("prospect", "outscale", "admin"):
        return jsonify({"error": "Rôle invalide (prospect|outscale|admin)"}), 400
    if len(username) < 3:
        return jsonify({"error": "Identifiant trop court (min 3 caractères)"}), 400
    if len(password) < 6:
        return jsonify({"error": "Mot de passe trop court (min 6 caractères)"}), 400
    if find_user_by_username(username):
        return jsonify({"error": "Identifiant déjà utilisé"}), 409

    company    = (body.get("company") or "").strip()
    users_data = load_users()
    new_user   = {
        "id":            secrets.token_hex(8),
        "username":      username,
        "password_hash": hash_pw(password),
        "role":          role,
        "company":       company,
        "created_at":    datetime.now(timezone.utc).isoformat(),
        "created_by":    caller.get("username", ""),
    }
    users_data["users"].append(new_user)
    save_users(users_data)
    cu = caller.get("username", "-")
    log_action("USER_CREATE", uid=caller.get("sub","-"), username=cu,
               detail=f"new={username} role={role} company={company or '-'}")
    return jsonify(user_public(new_user)), 201

@app.route("/api/users/<user_id>", methods=["PATCH"])
@require_admin
def update_user(user_id):
    body       = request.get_json(force=True) or {}
    users_data = load_users()
    for u in users_data["users"]:
        if u["id"] == user_id:
            changes = []
            if "role" in body and body["role"] in ("prospect", "outscale", "admin"):
                changes.append(f"role={body['role']}")
                u["role"] = body["role"]
            if "company" in body:
                u["company"] = (body["company"] or "").strip()
                changes.append("company=updated")
            if body.get("password"):
                u["password_hash"] = hash_pw(body["password"])
                changes.append("password=reset")
            save_users(users_data)
            cu = request.current_user
            log_action("USER_UPDATE", uid=cu.get("sub","-"), username=cu.get("username","-"),
                       detail=f"target={u['username']}({user_id}) " + " ".join(changes))
            return jsonify({"ok": True})
    abort(404)

@app.route("/api/users/<user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id):
    users_data = load_users()
    orig       = len(users_data["users"])
    target     = next((u for u in users_data["users"] if u["id"] == user_id), None)
    users_data["users"] = [u for u in users_data["users"] if u["id"] != user_id]
    if len(users_data["users"]) == orig:
        abort(404)
    save_users(users_data)
    (SIMS_DIR / f"{user_id}.json").unlink(missing_ok=True)
    cu = request.current_user
    log_action("USER_DELETE", uid=cu.get("sub","-"), username=cu.get("username","-"),
               detail=f"target={target['username'] if target else '?'}({user_id})")
    return jsonify({"ok": True})

# ── Simulations (utilisateurs authentifiés) ────────────────────────────────────
@app.route("/api/users/directory", methods=["GET"])
@require_auth
def users_directory():
    caller_role = request.current_user.get("role")
    caller_id   = request.current_user.get("sub")
    users_list  = load_users()["users"]

    if caller_role == "prospect":
        visible = [u for u in users_list if u["role"] == "outscale"]
    elif caller_role == "outscale":
        visible = [u for u in users_list if u["role"] in ("prospect", "outscale") and u["id"] != caller_id]
    else:  # admin
        visible = [u for u in users_list if u["id"] != caller_id]

    return jsonify([{"id": u["id"], "username": u["username"], "role": u["role"]}
                    for u in visible])

@app.route("/api/simulations", methods=["GET"])
@require_auth
def get_simulations():
    return jsonify(load_all_sims_with_shares(request.current_user["sub"]))

@app.route("/api/simulations", methods=["POST"])
@require_auth
def create_simulation():
    body = request.get_json(force=True) or {}
    uid  = request.current_user["sub"]
    sims = load_user_sims(uid)
    sim  = {
        "id":             secrets.token_hex(8),
        "name":           body.get("name", f"Simulation {datetime.now().strftime('%d/%m/%Y')}"),
        "lines":          body.get("lines", []),
        "activeRegions":  body.get("activeRegions", ["eu-west-2"]),
        "monthly":        body.get("monthly", 0),
        "savedAt":        datetime.now(timezone.utc).isoformat(),
        "owner_id":       uid,
        "owner_username": request.current_user.get("username", ""),
        "shared_with":    [],
    }
    sims.insert(0, sim)
    save_user_sims(uid, sims)
    log_action("SIM_CREATE", uid=uid, username=request.current_user.get("username", "-"),
               detail=f"sim_id={sim['id']} name={sim['name']!r}")
    return jsonify(sim), 201

@app.route("/api/simulations/<sim_id>", methods=["PUT"])
@require_auth
def update_simulation(sim_id):
    body = request.get_json(force=True) or {}
    uid  = request.current_user["sub"]
    sims = load_user_sims(uid)
    for i, s in enumerate(sims):
        if s["id"] == sim_id:
            sims[i] = {**s, **{k: v for k, v in body.items() if k != "id"},
                       "savedAt": datetime.now(timezone.utc).isoformat()}
            save_user_sims(uid, sims)
            log_action("SIM_UPDATE", uid=uid, username=request.current_user.get("username", "-"),
                       detail=f"sim_id={sim_id} name={sims[i].get('name','')!r}")
            return jsonify(sims[i])
    abort(404)

@app.route("/api/simulations/<sim_id>/share", methods=["PUT"])
@require_auth
def share_simulation(sim_id):
    caller = request.current_user
    if caller.get("role") not in ("outscale", "admin"):
        abort(403)
    body     = request.get_json(force=True) or {}
    user_ids = body.get("shared_with", [])
    uid      = caller["sub"]
    sims     = load_user_sims(uid)
    for i, s in enumerate(sims):
        if s["id"] == sim_id:
            sims[i] = {**s, "shared_with": user_ids}
            save_user_sims(uid, sims)
            log_action("SIM_SHARE", uid=uid, username=caller.get("username", "-"),
                       detail=f"sim_id={sim_id} shared_with={user_ids}")
            return jsonify(sims[i])
    abort(404)

@app.route("/api/simulations/<sim_id>", methods=["DELETE"])
@require_auth
def delete_simulation(sim_id):
    uid  = request.current_user["sub"]
    sims = load_user_sims(uid)
    new  = [s for s in sims if s["id"] != sim_id]
    if len(new) == len(sims):
        abort(404)
    save_user_sims(uid, new)
    log_action("SIM_DELETE", uid=uid, username=request.current_user.get("username", "-"),
               detail=f"sim_id={sim_id}")
    return jsonify({"ok": True})

# ── Catalogue ──────────────────────────────────────────────────────────────────
@app.route("/api/catalog", methods=["GET"])
def get_catalog():
    return jsonify(read_json(CATALOG_F))

@app.route("/api/catalog", methods=["PUT"])
@require_admin
def put_catalog():
    body    = request.get_json(force=True) or {}
    comment = body.pop("_comment", "")
    author  = body.pop("_author", request.current_user.get("username", "admin"))
    current = read_json(CATALOG_F)
    make_snapshot("catalog", current, author, comment)
    body["_meta"] = {
        "version":    current.get("_meta", {}).get("version", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": author,
        "comment":    comment,
    }
    write_json(CATALOG_F, body)
    log_action("CATALOG_UPDATE", uid=request.current_user.get("sub", "-"), username=author,
               detail=f"v={body['_meta']['version']} comment={comment!r}")
    return jsonify({"ok": True})

# ── Formules ───────────────────────────────────────────────────────────────────
@app.route("/api/formulas", methods=["GET"])
def get_formulas():
    return jsonify(read_json(FORMULAS_F))

@app.route("/api/formulas", methods=["PUT"])
@require_admin
def put_formulas():
    body    = request.get_json(force=True) or {}
    comment = body.pop("_comment", "")
    author  = body.pop("_author", request.current_user.get("username", "admin"))
    current = read_json(FORMULAS_F)
    make_snapshot("formulas", current, author, comment)
    body["_meta"] = {
        "version":    current.get("_meta", {}).get("version", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": author,
        "comment":    comment,
    }
    write_json(FORMULAS_F, body)
    log_action("FORMULAS_UPDATE", uid=request.current_user.get("sub", "-"), username=author,
               detail=f"v={body['_meta']['version']} comment={comment!r}")
    return jsonify({"ok": True})

# ── Régions ────────────────────────────────────────────────────────────────────
@app.route("/api/regions", methods=["GET"])
def get_regions():
    return jsonify(read_json(REGIONS_F))

@app.route("/api/regions", methods=["PUT"])
@require_admin
def put_regions():
    body    = request.get_json(force=True) or {}
    comment = body.pop("_comment", "")
    author  = body.pop("_author", request.current_user.get("username", "admin"))
    current = read_json(REGIONS_F)
    make_snapshot("regions", current, author, comment)
    body["_meta"] = {
        "version":    current.get("_meta", {}).get("version", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": author,
        "comment":    comment,
    }
    write_json(REGIONS_F, body)
    log_action("REGIONS_UPDATE", uid=request.current_user.get("sub", "-"), username=author,
               detail=f"v={body['_meta']['version']} comment={comment!r}")
    return jsonify({"ok": True})

# ── Historique ─────────────────────────────────────────────────────────────────
@app.route("/api/history", methods=["GET"])
@require_admin
def list_history():
    kind   = request.args.get("kind")
    result = []
    for f in sorted(HIST.glob("*.json"), reverse=True):
        if kind and f"_{kind}." not in f.name:
            continue
        try:
            meta = read_json(f)
            result.append({
                "id": f.stem, "filename": f.name,
                "at": meta.get("snapshot_at"), "kind": meta.get("snapshot_kind"),
                "author": meta.get("author"), "comment": meta.get("comment"),
            })
        except Exception:
            pass
    return jsonify(result)

@app.route("/api/history/<snapshot_id>", methods=["GET"])
@require_admin
def get_snapshot(snapshot_id):
    f = HIST / f"{snapshot_id}.json"
    if not f.exists():
        abort(404)
    return jsonify(read_json(f))

@app.route("/api/history/<snapshot_id>/restore", methods=["POST"])
@require_admin
def restore_snapshot(snapshot_id):
    f = HIST / f"{snapshot_id}.json"
    if not f.exists():
        abort(404)
    snap    = read_json(f)
    kind    = snap.get("snapshot_kind")
    data    = snap.get("data", {})
    targets = {"catalog": CATALOG_F, "formulas": FORMULAS_F, "regions": REGIONS_F}
    target  = targets.get(kind)
    if not target:
        abort(400)
    body    = request.get_json(force=True) or {}
    author  = body.get("author", request.current_user.get("username", "admin"))
    current = read_json(target)
    make_snapshot(kind, current, author, f"Sauvegarde avant restauration de {snapshot_id}")
    data["_meta"] = {
        "version":    current.get("_meta", {}).get("version", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": author,
        "comment":    f"Restauré depuis {snapshot_id}",
    }
    write_json(target, data)
    log_action("SNAPSHOT_RESTORE", uid=request.current_user.get("sub", "-"), username=author,
               detail=f"snapshot={snapshot_id} kind={kind}")
    return jsonify({"ok": True, "restored_kind": kind})

@app.route("/api/history/<snapshot_id>", methods=["DELETE"])
@require_admin
def delete_snapshot(snapshot_id):
    f = HIST / f"{snapshot_id}.json"
    if not f.exists():
        abort(404)
    f.unlink()
    cu = request.current_user
    log_action("SNAPSHOT_DELETE", uid=cu.get("sub", "-"), username=cu.get("username", "-"),
               detail=f"snapshot={snapshot_id}")
    return jsonify({"ok": True})

# ── Logs (admin) ───────────────────────────────────────────────────────────────
@app.route("/api/logs", methods=["GET"])
@require_admin
def get_logs():
    n = min(int(request.args.get("lines", 500)), 5000)
    log_file = LOGS_DIR / "actions.log"
    if not log_file.exists():
        return jsonify({"lines": [], "total": 0})
    with open(log_file, encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    total = len(all_lines)
    lines = [l.rstrip("\n") for l in all_lines[-n:]]
    cu = request.current_user
    log_action("LOGS_VIEW", uid=cu.get("sub", "-"), username=cu.get("username", "-"),
               detail=f"lines={n}")
    return jsonify({"lines": lines, "total": total})

@app.route("/api/logs/download", methods=["GET"])
@require_admin
def download_logs():
    log_file = LOGS_DIR / "actions.log"
    if not log_file.exists():
        abort(404)
    cu = request.current_user
    log_action("LOGS_DOWNLOAD", uid=cu.get("sub", "-"), username=cu.get("username", "-"))
    return send_file(str(log_file), mimetype="text/plain", as_attachment=True,
                     download_name="actions.log")

# ── Health ─────────────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "ts": datetime.now(timezone.utc).isoformat()})

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
