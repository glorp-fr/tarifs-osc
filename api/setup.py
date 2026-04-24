"""
Script d'initialisation — à lancer une seule fois pour configurer l'admin.
Usage : python3 setup.py
"""

import json
import os
import secrets
from getpass import getpass
from pathlib import Path

try:
    import bcrypt
except ImportError:
    raise SystemExit("Lancer : pip3 install bcrypt")

CONFIG_F = Path(__file__).parent.parent / "data" / "config.json"

def main():
    print("=== Configuration initiale Outscale Estimateur ===\n")

    with open(CONFIG_F, encoding="utf-8") as f:
        cfg = json.load(f)

    password = getpass("Mot de passe admin : ")
    confirm  = getpass("Confirmer          : ")
    if password != confirm:
        raise SystemExit("Les mots de passe ne correspondent pas.")
    if len(password) < 8:
        raise SystemExit("Mot de passe trop court (min 8 caractères).")

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cfg["admin_password_hash"] = hashed
    cfg["jwt_secret"]          = secrets.token_hex(32)

    tmp = CONFIG_F.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    tmp.replace(CONFIG_F)

    print("\nConfiguration sauvegardée dans data/config.json")
    print("Lancer ensuite : python3 api/server.py")

if __name__ == "__main__":
    main()
