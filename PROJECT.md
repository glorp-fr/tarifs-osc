# OUTSCALE Cloud Estimateur — Document projet complet

**Auteur :** Jaouen Trillot  
**Version :** 2.4  
**Date :** Avril 2026  
**Objet :** Toutes les informations nécessaires pour recréer le projet de zéro.

---

## Table des matières

1. [Contexte et objectifs](#1-contexte-et-objectifs)
2. [Architecture technique](#2-architecture-technique)
3. [Structure des fichiers](#3-structure-des-fichiers)
4. [Installation et déploiement](#4-installation-et-déploiement)
5. [Données — formats JSON](#5-données--formats-json)
6. [Backend Flask — API](#6-backend-flask--api)
7. [Frontend estimateur](#7-frontend-estimateur)
8. [Interface d'administration](#8-interface-dadministration)
9. [Moteur de calcul](#9-moteur-de-calcul)
10. [Design system CSS](#10-design-system-css)
11. [Authentification et rôles](#11-authentification-et-rôles)
12. [Sécurité](#12-sécurité)
13. [Catalogue de tarifs complet](#13-catalogue-de-tarifs-complet)
14. [Évolutions prévues](#14-évolutions-prévues)

---

## 1. Contexte et objectifs

L'estimateur OUTSCALE est une application web permettant à des **prospects** et à des **commerciaux Outscale** de construire des devis cloud interactifs : sélection de ressources (VM, GPU, stockage, réseau, licences), calcul instantané du coût mensuel / annuel / 3 ans, export et sauvegarde des simulations.

### Objectifs

| # | Objectif |
|---|----------|
| 1 | **Estimateur libre-service** — un prospect s'inscrit, configure son infrastructure cible, sauvegarde ses simulations. |
| 2 | **Outil commercial** — les utilisateurs Outscale créent des simulations pour leurs clients, les partagent et gèrent les comptes. |
| 3 | **Administration centralisée** — un administrateur gère le catalogue de tarifs, les régions, les engagements RI et les utilisateurs. |

---

## 2. Architecture technique

| Couche | Technologie | Version | Raison du choix |
|--------|-------------|---------|-----------------|
| Backend | Python + Flask | 3.x / Flask >= 3.0 | Léger, disponible sur le serveur |
| Auth | JWT HS256 — PyJWT | >= 2.8 | Stateless, pas de session serveur |
| Hash MDP | bcrypt | >= 4.1 | Standard sécurisé |
| CORS | flask-cors | >= 4.0 | Proxifié par nginx, CORS sur `/api/*` |
| Persistance | Fichiers JSON | — | Pas de BDD, snapshots lisibles/versionables |
| Frontend | React 18 via CDN | 18.2.0 | Pas de build step |
| Transpilation | Babel standalone | 7.23.5 | JSX dans le navigateur |
| CSS utilitaire | Tailwind via CDN | — | Chargé dans le `<head>` |
| Fonts | Google Fonts | — | Montserrat 600/700, Open Sans 400/500/600/700, DM Mono 400/500 |
| Reverse proxy | nginx | — | Sert les fichiers statiques + proxy `/api/` vers Flask :5000 |
| Process manager | systemd | — | Redémarrage automatique du backend |

### Flux de données

```
Navigateur
  GET /              -> nginx -> public/index.html (SPA estimateur)
  GET /admin/        -> nginx -> public/admin/index.html (SPA admin)
  GET /assets/*      -> nginx -> public/assets/
  /api/*             -> nginx -> proxy -> Flask :5000
                                -> data/catalog.json
                                -> data/formulas.json
                                -> data/regions.json
                                -> data/config.json
                                -> data/users.json
                                -> data/simulations/{user_id}.json
                                -> data/history/{ts}_{kind}.json
```

---

## 3. Structure des fichiers

```
tarifs-osc/
├── api/
│   ├── server.py                  # Backend Flask — toutes les routes
│   ├── setup.py                   # Script init admin (mot de passe + jwt_secret)
│   └── requirements.txt           # flask>=3.0 flask-cors>=4.0 pyjwt>=2.8 bcrypt>=4.1
├── data/
│   ├── catalog.json               # Tarifs actifs (voir §13)
│   ├── formulas.json              # Engagements RI (remises)
│   ├── regions.json               # Régions Outscale
│   ├── config.json                # Config app + hash admin (NE PAS COMMITTER)
│   ├── users.json                 # Utilisateurs (hors admin legacy)
│   ├── simulations/               # {user_id}.json — simulations par utilisateur
│   └── history/                   # {YYYYMMDDTHHMMSSZ}_{kind}.json — snapshots auto
├── public/
│   ├── index.html                 # SPA estimateur (React inliné)
│   ├── admin/
│   │   └── index.html             # SPA administration (React inliné)
│   └── assets/
│       ├── style.css              # Design system complet
│       ├── favicon.png
│       ├── logo-icon-192.png
│       ├── logo-outscale-blanc.svg
│       ├── logo-outscale-couleur.svg
│       └── js/
│           ├── calc.js            # Moteur de calcul (pur JS, sans UI)
│           └── api.js             # Client API + auth helpers + fallbacks
├── nginx.conf.example
├── tarifs-osc.service.example
├── .gitignore
├── cahierdescharges.md
├── TODO.md
└── PROJECT.md                     # Ce fichier
```

### .gitignore recommandé

```
data/config.json
data/history/
data/users.json
data/simulations/
.venv/
__pycache__/
*.pyc
.env
```

---

## 4. Installation et déploiement

### Prérequis

- Python 3.10+, nginx, accès sudo

### Étape 1 — Déposer les fichiers

```bash
sudo chown -R www-data:www-data /var/www/html/tarifs-osc
```

### Étape 2 — Environnement Python

```bash
cd /var/www/html/tarifs-osc
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt
```

### Étape 3 — Initialiser le mot de passe admin

```bash
python3 api/setup.py
# Saisir le mot de passe admin (min 8 caractères)
# Écrit admin_password_hash et jwt_secret dans data/config.json
```

Le script génère :
- `admin_password_hash` — bcrypt cost 12
- `jwt_secret` — `secrets.token_hex(32)` (64 caractères hex)

### Étape 4 — Configurer nginx

```bash
sudo cp nginx.conf.example /etc/nginx/sites-available/tarifs-osc
# Adapter server_name dans le fichier
sudo ln -s /etc/nginx/sites-available/tarifs-osc /etc/nginx/sites-enabled/
sudo nginx -t && sudo nginx -s reload
```

**Configuration nginx complète :**

```nginx
server {
    listen 80;
    server_name tarifs.example.com;
    root /var/www/html/tarifs-osc/public;
    index index.html;
    gzip on;
    gzip_types text/html text/css application/javascript application/json;
    location / { try_files $uri $uri/ /index.html; }
    location /admin { try_files $uri $uri/ /admin/index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 30s;
    }
    location ~* \.(js|css|woff2|png|svg|ico)$ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

### Étape 5 — Configurer systemd

```bash
sudo cp tarifs-osc.service.example /etc/systemd/system/tarifs-osc.service
sudo systemctl daemon-reload
sudo systemctl enable --now tarifs-osc
```

**Contenu de l'unité systemd :**

```ini
[Unit]
Description=Outscale Cloud Estimateur — Backend API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/html/tarifs-osc
ExecStart=/var/www/html/tarifs-osc/.venv/bin/python3 api/server.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

### Étape 6 — Vérification

```bash
curl http://localhost:5000/api/health
# {"status": "ok", "ts": "2026-04-27T..."}
```

### Mise à jour du code

```bash
sudo systemctl restart tarifs-osc
```

### HTTPS (recommandé)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tarifs.example.com
```

---

## 5. Données — formats JSON

### 5.1 `data/config.json`

```json
{
  "_meta": { "comment": "Ne pas committer ce fichier" },
  "admin_password_hash": "$2b$12$...",
  "jwt_secret": "<64 chars hex>",
  "session_ttl_hours": 8,
  "history_max_snapshots": 100,
  "app_title": "OUTSCALE — Estimateur budgétaire cloud"
}
```

| Clé | Défaut | Description |
|-----|--------|-------------|
| `admin_password_hash` | — | Généré par `setup.py` (bcrypt) |
| `jwt_secret` | — | Généré par `setup.py` (`secrets.token_hex(32)`) |
| `session_ttl_hours` | 8 | Durée de vie du token JWT |
| `history_max_snapshots` | 100 | Nombre max de snapshots conservés |

### 5.2 `data/users.json`

```json
{
  "users": [
    {
      "id": "a3f8c1d2",
      "username": "jdupont",
      "password_hash": "$2b$12$...",
      "role": "prospect",
      "company": "Acme Corp",
      "created_at": "2026-04-24T10:00:00Z",
      "created_by": "commercial.dupont"
    }
  ]
}
```

| Champ | Contraintes |
|-------|-------------|
| `id` | `secrets.token_hex(8)`, unique |
| `username` | Unique, min 3 caractères, insensible à la casse |
| `password_hash` | bcrypt cost 12 |
| `role` | `prospect` ou `outscale` ou `admin` |
| `company` | Optionnel |
| `created_by` | Username du créateur (absent si auto-inscription) |

### 5.3 `data/simulations/{user_id}.json`

Tableau JSON de simulations par utilisateur :

```json
[
  {
    "id": "b7e2f4a1",
    "name": "Projet A — Q2 2026",
    "lines": [],
    "activeRegions": ["eu-west-2"],
    "monthly": 4820.5,
    "savedAt": "2026-04-24T14:30:00Z",
    "owner_id": "a3f8c1d2",
    "owner_username": "jdupont",
    "shared_with": ["x9k3m2p1"]
  }
]
```

Structure commune de chaque ligne :

```json
{
  "id": "<random 8 chars>",
  "type": "compute|dedicated-access|gpu|oks|bsu|oos|net|lic",
  "desc": "Description libre",
  "region_id": "eu-west-2",
  "engagement": "on-demand"
}
```

Champs spécifiques par type :

| Type | Champs |
|------|--------|
| `compute` | `qty`, `cpu_gen` (v1..v7), `vcore`, `ram`, `perf` (medium/high/highest), `dedicated` (bool), `usage` (0-1), `storage_type`, `storage_gb`, `iops` |
| `dedicated-access` | `qty`, `usage` |
| `gpu` | `gpu_qty`, `gpu_type`, `usage` |
| `oks` | `qty`, `cp` (type control plane), `usage` |
| `bsu` | `qty`, `storage_type`, `storage_gb`, `iops` |
| `oos` | `storage_gb`, `oos_type` (optionnel, défaut : `Standard`) |
| `net` | `net_type`, `net_qty` |
| `lic` | `lic_type`, `lic_qty` |

### 5.4 `data/catalog.json` — clé `_availability`

La clé `_availability` contrôle la disponibilité de chaque service par région. Absente = service disponible partout.

```json
{
  "_availability": {
    "gpu.Nvidia A10":        [true, true, false, false, false],
    "oks.cp.3.masters.large":[true, true, false, false, false],
    "oos.Archive":           [false, false, false, false, false],
    "hdl_1gbps":             [true, true, false, false, false],
    "lic.Oracle Linux OS (par VM)": [true, true, false, false, false],
    "vcore.v1":              [true, true, true, true, true]
  }
}
```

**Format de clé :**

| Préfixe clé | Service |
|-------------|---------|
| `gpu.<modèle>` | GPU par modèle |
| `oks.<type>` | Control plane OKS |
| `oos.<tier>` | Tier OOS (Standard, Archive, etc.) |
| `storage.<type>` | Volume BSU |
| `lic.<nom>` | Licence |
| `vcore.<gen>` | Génération vCore (v1..v7) |
| `hdl_1gbps` / `hdl_10gbps` / `hdl_setup` | Hosted DirectLink |

**Règle :** un index `false` (ou `0`) désactive le service pour cette région dans les listes déroulantes de l'estimateur. L'admin peut basculer chaque région ON/OFF par un bouton dans l'onglet Catalogue.

### 5.5 `data/history/{ts}_{kind}.json`

```json
{
  "snapshot_at": "20260423T152053Z",
  "snapshot_kind": "catalog",
  "author": "admin",
  "comment": "tarif Avril 2026",
  "data": {}
}
```

Nommage : `{YYYYMMDDTHHMMSSZ}_{catalog|formulas|regions}.json`

### 5.6 `data/regions.json`

```json
{
  "_meta": { "version": 1, "updated_at": "...", "updated_by": "init", "comment": "..." },
  "regions": [
    { "id": "eu-west-2",           "flag": "FR", "short": "EU-W2",  "name": "Europe Ouest (France)",    "active": true },
    { "id": "cloudgouv-eu-west-1", "flag": "FR", "short": "GOUV",   "name": "Cloud Souverain (France)", "active": true },
    { "id": "us-west-1",           "flag": "US", "short": "US-W1",  "name": "US Ouest",                 "active": true },
    { "id": "us-east-2",           "flag": "US", "short": "US-E2",  "name": "US Est",                   "active": true },
    { "id": "ap-northeast-1",      "flag": "JP", "short": "AP-NE1", "name": "Asie (Japon)",             "active": true }
  ]
}
```

**L'ordre des régions est critique** : il correspond aux index dans tous les tableaux de prix du catalogue.

### 5.7 `data/formulas.json`

```json
{
  "_meta": { "version": 4, "updated_at": "...", "updated_by": "admin", "comment": "..." },
  "engagements": [
    { "id": "on-demand",       "label": "A la demande",               "discount": 0,    "active": true,  "applies_to": ["cpu","ram"] },
    { "id": "ri-1m-upfront",   "label": "RI 1 mois upfront (-30%)",   "discount": 0.30, "active": true,  "applies_to": ["cpu","ram"] },
    { "id": "ri-1y-upfront",   "label": "RI 1 an upfront (-40%)",     "discount": 0.40, "active": true,  "applies_to": ["cpu","ram"] },
    { "id": "ri-2y-upfront",   "label": "RI 2 ans upfront (-50%)",    "discount": 0.50, "active": false, "applies_to": ["cpu","ram"] },
    { "id": "ri-3y-upfront",   "label": "RI 3 ans upfront (-60%)",    "discount": 0.60, "active": false, "applies_to": ["cpu","ram"] },
    { "id": "ri-1y-quarterly", "label": "RI 1 an trimestriel (-37%)", "discount": 0.37, "active": true,  "applies_to": ["cpu","ram"] },
    { "id": "ri-2y-quarterly", "label": "RI 2 ans trimestriel (-45%)","discount": 0.45, "active": false, "applies_to": ["cpu","ram"] },
    { "id": "ri-3y-quarterly", "label": "RI 3 ans trimestriel (-53%)","discount": 0.53, "active": false, "applies_to": ["cpu","ram"] },
    { "id": "ri-2y-yearly",    "label": "RI 2 ans annuel (-48%)",     "discount": 0.48, "active": false, "applies_to": ["cpu","ram"] },
    { "id": "ri-3y-yearly",    "label": "RI 3 ans annuel (-56%)",     "discount": 0.56, "active": false, "applies_to": ["cpu","ram"] },
    { "id": "ri-gpu",          "label": "RI GPU 30%",                 "discount": 0.30, "active": true,  "applies_to": ["gpu"] }
  ]
}
```

**Champ `applies_to`** : tableau des types de ressources auxquels s'applique la remise. Valeurs possibles : `"cpu"`, `"ram"`, `"gpu"`. Sans ce champ, le moteur utilise le fallback `["cpu","ram","gpu"]`. L'interface filtre les listes déroulantes d'engagement en fonction du type de ligne (CPU/RAM vs GPU). L'onglet Formules de l'admin édite ce champ.

---

## 6. Backend Flask — API

### 6.1 Lancer

```bash
source .venv/bin/activate
python3 api/server.py
# Écoute sur 127.0.0.1:5000
```

### 6.2 Chemins de données (server.py)

```python
BASE     = Path(__file__).parent.parent   # /var/www/html/tarifs-osc
DATA     = BASE / "data"
HIST     = DATA / "history"
SIMS_DIR = DATA / "simulations"
LOGS_DIR = BASE / "logs"
```

Les répertoires `HIST`, `SIMS_DIR` et `LOGS_DIR` sont créés au démarrage si absents (`mkdir(parents=True, exist_ok=True)`).

### 6.2b Journal des actions (logging applicatif)

`logs/actions.log` — `RotatingFileHandler`, 10 Mo max, 5 sauvegardes, timestamps UTC.

**Format d'une ligne :**
```
2026-04-27T14:05:00Z | 1.2.3.4 | alice(a1b2c3d4) | LOGIN_OK | role=outscale
```
Champs : horodatage ISO 8601 | IP source | `username(user_id)` | action | détail

**IP source :** `X-Real-IP` → `X-Forwarded-For` → `remote_addr` (gère le proxy nginx).

**Actions tracées :**

| Action | Route déclenchante | Détail enregistré |
|--------|-------------------|-------------------|
| `LOGIN_OK` | POST `/api/auth/login` | `role=<role>` |
| `LOGIN_FAIL` | POST `/api/auth/login` | `username=<username>` |
| `REGISTER` | POST `/api/auth/register` | `company=<company>` |
| `USER_CREATE` | POST `/api/users` | `new=<username> role=<role> company=<company>` |
| `USER_UPDATE` | PATCH `/api/users/:id` | champs modifiés (role=, company=updated, password=reset) |
| `USER_DELETE` | DELETE `/api/users/:id` | `target=<username>(<id>)` |
| `SIM_CREATE` | POST `/api/simulations` | `sim_id=<id> name=<name>` |
| `SIM_UPDATE` | PUT `/api/simulations/:id` | `sim_id=<id> name=<name>` |
| `SIM_SHARE` | PUT `/api/simulations/:id/share` | `sim_id=<id> shared_with=[...]` |
| `SIM_DELETE` | DELETE `/api/simulations/:id` | `sim_id=<id>` |
| `CATALOG_UPDATE` | PUT `/api/catalog` | `v=<version> comment=<comment>` |
| `FORMULAS_UPDATE` | PUT `/api/formulas` | `v=<version> comment=<comment>` |
| `REGIONS_UPDATE` | PUT `/api/regions` | `v=<version> comment=<comment>` |
| `SNAPSHOT_RESTORE` | POST `/api/history/:id/restore` | `snapshot=<id> kind=<kind>` |
| `SNAPSHOT_DELETE` | DELETE `/api/history/:id` | `snapshot=<id>` |
| `LOGS_VIEW` | GET `/api/logs` | `lines=<n>` |
| `LOGS_DOWNLOAD` | GET `/api/logs/download` | — |

### 6.3 Écriture atomique

```python
def write_json(path, data):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)   # atomique sur Linux
```

### 6.4 JWT

- Algorithme : HS256
- Payload : `{sub: user_id, username, role, company, exp}`
- TTL : `session_ttl_hours` depuis `config.json`
- Décorateurs : `@require_auth` (tout JWT valide), `@require_admin` (role=admin)

### 6.5 Routes complètes

#### Auth

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/api/auth/login` | — | Body `{username, password}` ou `{password}` (legacy). Retourne `{token, ttl_hours, user: {id, username, role, company}}` |
| POST | `/api/auth/register` | — | Body `{username, password, company?}`. Retourne `{token, user: {id, username, role, company}}` 201 |
| GET | `/api/auth/me` | JWT | Retourne `{id, username, role, company}` |

#### Simulations

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET | `/api/simulations` | JWT | Propres + partagées (champ `_owned: true/false`) |
| POST | `/api/simulations` | JWT | Créer |
| PUT | `/api/simulations/:id` | JWT | Mettre à jour (propriétaire) |
| DELETE | `/api/simulations/:id` | JWT | Supprimer (propriétaire) |
| PUT | `/api/simulations/:id/share` | JWT outscale/admin | Body `{shared_with: [user_id, ...]}` |

#### Utilisateurs

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET | `/api/users` | Admin | Liste complète (sans `password_hash`) |
| GET | `/api/users/directory` | JWT | Liste légère `{id, username, role}` |
| POST | `/api/users` | JWT outscale/admin | Créer |
| PATCH | `/api/users/:id` | Admin | Modifier `role`, `company`, `password` |
| DELETE | `/api/users/:id` | Admin | Supprimer + simulations associées |

#### Catalogue, formules, régions

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET | `/api/catalog` | — | Catalogue |
| PUT | `/api/catalog` | Admin | Mettre à jour + snapshot auto |
| GET | `/api/formulas` | — | Engagements RI |
| PUT | `/api/formulas` | Admin | Mettre à jour + snapshot auto |
| GET | `/api/regions` | — | Régions |
| PUT | `/api/regions` | Admin | Mettre à jour + snapshot auto |

Les PUT acceptent `_comment` et `_author` retirés avant écriture.

#### Historique

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET | `/api/history` | Admin | Liste (`?kind=catalog\|formulas\|regions`) |
| GET | `/api/history/:id` | Admin | Contenu complet |
| POST | `/api/history/:id/restore` | Admin | Restaurer (snapshot auto avant) |
| DELETE | `/api/history/:id` | Admin | Supprimer |

#### Logs (admin)

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET | `/api/logs` | Admin | Dernières N lignes du journal. `?lines=500` (max 5000). Retourne `{lines: [...], total: N}` |
| GET | `/api/logs/download` | Admin | Télécharge `actions.log` en pièce jointe (`text/plain`) |

Chaque appel à `/api/logs` génère lui-même une entrée `LOGS_VIEW` dans le journal.

#### Santé

```
GET /api/health  ->  {"status": "ok", "ts": "..."}
```

#### Codes d'erreur — tous retournent `{"error": "message"}` en JSON

| Code | Situation |
|------|-----------|
| 400 | Paramètre invalide |
| 401 | Non authentifié / token expiré |
| 403 | Rôle insuffisant |
| 404 | Ressource introuvable |
| 409 | Conflit (identifiant déjà utilisé) |
| 500 | Erreur serveur |
| 503 | Backend non configuré (jwt_secret manquant) |

### 6.6 Snapshot automatique

```python
def make_snapshot(kind, data, author, comment=""):
    ts   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{ts}_{kind}.json"
    payload = {"snapshot_at": ts, "snapshot_kind": kind,
               "author": author, "comment": comment, "data": data}
    write_json(HIST / name, payload)
    _prune_history()
```

### 6.7 Chargement simulations partagées

```python
def load_all_sims_with_shares(user_id):
    owned  = [{**s, "_owned": True}  for s in load_user_sims(user_id)]
    shared = []
    for f in SIMS_DIR.glob("*.json"):
        if f.stem == user_id: continue
        for s in read_json(f):
            if user_id in s.get("shared_with", []):
                shared.append({**s, "_owned": False})
    return owned + shared
```

---

## 7. Frontend estimateur

### 7.1 Dépendances CDN (ordre dans `<head>`)

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.5/babel.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Open+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
<script src="/assets/js/calc.js?v=4"></script>
<script src="/assets/js/api.js?v=4"></script>
```

Code React inline dans `<script type="text/babel" data-presets="react">`.

> **Cache-busting obligatoire** : nginx sert les `.js` avec `Cache-Control: public, immutable` (7 jours). À chaque modification de `calc.js` ou `api.js`, incrémenter le suffixe (`?v=5`, `?v=6`…) dans `index.html` pour forcer le rechargement chez tous les navigateurs. Version courante : `?v=4`.

### 7.2 Hiérarchie des composants

```
AuthGate
├── LoginPage (mode login / register)
└── UserCtx.Provider
    └── AppCtx.Provider (regions, engagements, catalog, activeRegions)
        └── App
            ├── Header  (logo uniquement — sticky, fond --os-blue-dark)
            ├── Div flex-row
            │   ├── Sidebar  (barre latérale gauche — fond --os-blue-dark, border-right orange)
            │   │   ├── Bloc utilisateur connecté / bouton Se connecter
            │   │   ├── Mes simulations → ProfilesModal
            │   │   ├── Créer un compte → CreateAccountModal (outscale/admin)
            │   │   ├── Importer / Exporter (côte à côte)
            │   │   ├── Admin (lien /admin/ — admin seulement)
            │   │   ├── Séparateur + section "Affichage"
            │   │   ├── Boutons Côté à côté / Saisie / Synthèse (sb-tabs)
            │   │   └── Aide (bas de sidebar, marginTop:auto)
            │   └── Zone contenu principale
            │       ├── Bandeau avertissement API
            │       ├── HelpPage (onglet Aide)
            │       ├── Cadre hypothèses (split/input)
            │       │   ├── Filtres type + région
            │       │   ├── Liste LineEditor (accordion)
            │       │   └── AddMenu
            │       └── Cadre synthèse (split/view)
            │           ├── PivotTable (région × groupe)
            │           └── EngBreakdown (par engagement)
            ├── ProfilesModal
            ├── ShareModal
            ├── CreateAccountModal
            └── LoginPage (modal)
```

**`AuthGate`** parse le JWT stocké dans `localStorage["osc:token"]` et en extrait `{id, username, role, company}`. Le champ `company` est affiché dans le bloc utilisateur de la sidebar.

**Layout général :**

```
┌──────────────────────── Header (56px, sticky) ───────────────────────────┐
│ Logo                                                                       │
├──────────┬──────────────────────────────────────────────────────────────┤
│ Sidebar  │  Zone contenu                                                  │
│ 220px    │  flex:1 — padding 16px 20px                                   │
│ sticky   │                                                                │
│ h=100vh  │                                                                │
│ -56px    │                                                                │
└──────────┴──────────────────────────────────────────────────────────────┘
```

### 7.3 Contextes

```javascript
const AppCtx  = createContext({ regions: [], engagements: [], catalog: null, activeRegions: [] });
const UserCtx = createContext(null);
```

### 7.4 localStorage

| Clé | Contenu |
|-----|---------|
| `osc:token` | JWT (partagé avec l'admin) |
| `osc:lines` | Lignes de ressources (auto-save) |
| `osc:catalog` / `osc:regions` / `osc:formulas` | Caches API |

### 7.5 Chargement initial

1. `OSApi.loadAll()` — API puis fallback localStorage puis défauts embarqués
2. Catalog absent → bandeau "API indisponible"
3. Regions chargées → toutes actives par défaut
4. Lignes depuis `localStorage['osc:lines']` ou données DEMO

### 7.6 Filtres

- **Type** : `""` = tout, sinon `compute|gpu|oks|bsu|oos|net|lic` (compute inclut dedicated-access)
- **Région** : visible si plusieurs régions. Cliquer à nouveau désélectionne.

### 7.7 Filtrage par disponibilité région

Dans `LineEditor`, les listes déroulantes de chaque ligne sont filtrées dynamiquement selon `C._availability` et la région sélectionnée :

```javascript
const ri      = regions.findIndex(r => r.id === regionId);
const isAvail = (key) => { const a = C._availability?.[key]; return !a || a[ri] !== false; };
const GPU_OPTS  = Object.keys(C.gpu||{}).filter(n => isAvail(`gpu.${n}`));
const OKS_OPTS  = Object.keys(C.oks||{}).filter(n => isAvail(`oks.${n}`));
const STOR_OPTS = Object.keys(C.storage||{}).filter(n => isAvail(`storage.${n}`));
const LIC_OPTS  = Object.keys(C.lic||{}).filter(n => isAvail(`lic.${n}`));
const CPU_GENS  = OSCalc.CPUGENS.filter(gen => isAvail(`vcore.${gen}`));
const NET_OPTS  = OSCalc.NET_OPTS.filter(opt => { /* filtre hdl_* */ });
```

Les services désactivés dans la région cible n'apparaissent pas dans les sélecteurs. Si la valeur courante de la ligne n'est plus disponible, la liste revient au premier item disponible.

### 7.8 Partage (outscale/admin)

1. Bouton dans ProfilesModal → ShareModal
2. GET `/api/users/directory` → liste des utilisateurs
3. Cases pré-cochées selon `shared_with`
4. PUT `/api/simulations/:id/share`

---

## 8. Interface d'administration

URL : `/admin/` — rôle `admin` uniquement. 401/403 → déconnexion + rechargement.

### 8.1 Onglets

| Onglet | Description |
|--------|-------------|
| Dashboard | Résumé 4 blocs + derniers snapshots + dernières actions |
| Catalogue | Édition de tous les tarifs par région |
| Formules RI | Engagements (id, libellé, remise, actif) |
| Régions | Drag-and-drop (ordre = index dans les prix) |
| Utilisateurs | CRUD complet |
| Historique | Snapshots, diff visuel, restauration |
| **Logs** | **Visualisateur et export du journal des actions** |

### 8.2 CatalogTab — clés de mapping éditeur

| Préfixe | Champ catalogue |
|---------|----------------|
| `ram` | `catalog.ram[i]` |
| `ded_fee` | `catalog.ded_fee[i]` |
| `vcore__gen__perf` | `catalog.vcore[gen][perf][i]` |
| `gpu__name` | `catalog.gpu[name][i]` |
| `oks__name` | `catalog.oks[name][i]` |
| `stor_gb__name` | `catalog.storage[name].gb[i]` |
| `stor_iops__name` | `catalog.storage[name].iops[i]` |
| `oos__name` | `catalog.oos[name][i]` (ex: `oos__Standard`, `oos__Archive`) |
| `vpn` / `nat` / `lbu` / `eip` | réseau horaire |
| `dl_setup` / `dl_1g` / `dl_10g` | DirectLink |
| `hdl_setup` / `hdl_1g` / `hdl_10g` | Hosted DirectLink |
| `lic__name` | `catalog.lic[name].price[i]` |
| `const_hpm__0` | `catalog.hours_per_month` |
| `const_ded__0` | `catalog.dedicated_surcharge` |
| `const_gricap__0` | `catalog.gpu_ri_cap` |

### 8.3 CatalogTab — disponibilité et gestion dynamique des services

#### Boutons ON/OFF par région

Chaque cellule de prix dans l'onglet Catalogue comporte un bouton vert/gris activant ou désactivant le service pour la région correspondante. Un service désactivé a son champ de prix en lecture seule et grisé. Les états sont stockés dans `catalog._availability` (sauvegardés au même `PUT /api/catalog` que les prix).

#### Ajout de services

Un bouton `+ Ajouter` en bas de chaque section permet d'ajouter un nouveau service inline :

| Section | Composant | Champs |
|---------|-----------|--------|
| GPU | `AddServiceRow` | Nom + prix par région |
| OKS | `AddServiceRow` | Nom + prix par région |
| BSU | `AddServiceRow (withIops)` | Nom + prix GiB + prix IOPS par région |
| Licences | `AddServiceRow` | Nom + prix par région |
| OOS | `AddServiceRow` | Nom du tier + prix par région |
| vCore | `AddVcoreRow` | Nom génération + 3 lignes perf (medium/high/highest) × prix par région |

`AddVcoreRow` affiche une ligne d'en-tête (nom de génération + bouton Ajouter) et 3 sous-lignes de saisie de prix pour medium, high, highest.

#### Suppression de services

Un bouton `×` apparaît à droite du libellé pour les services supprimables. Confirmation requise. La suppression retire l'entrée de `catalog`, de `_availability` et de l'état local `edits`. Protections :
- `OOS Standard` : non supprimable
- Génération vCore : le `×` est affiché sur la première ligne de perf uniquement et supprime toutes les performances de la génération

### 8.4 Restauration d'un snapshot

1. Snapshot auto de la version courante
2. Écrit le contenu dans le fichier cible
3. Incrémente `_meta.version`

### 8.5 LogsTab — visualisateur de journal

Route API : `GET /api/logs?lines=<n>` (admin uniquement).

**Fonctionnalités :**

| Fonctionnalité | Description |
|----------------|-------------|
| Tableau paginé | Colonnes : horodatage, IP, utilisateur, action (badge coloré), détail |
| Filtrage texte | Recherche client-side sur toutes les colonnes simultanément |
| Filtre par action | Dropdown peuplé dynamiquement avec les actions présentes dans la fenêtre chargée |
| Sélection du volume | 200 / 500 / 1 000 / 5 000 dernières lignes |
| Auto-refresh | Rafraîchissement automatique toutes les 10 secondes (toggle ▶/⏸) |
| Détail d'une ligne | Clic → affiche la ligne brute complète sous la ligne |
| Export CSV | `logs.csv` — vue filtrée courante, colonnes : timestamp, ip, user, action, detail |
| Téléchargement brut | `actions.log` complet via `GET /api/logs/download` (fetch + Blob URL) |

**Codes couleur des badges action :**

| Couleur | Actions |
|---------|---------|
| Vert | `LOGIN_OK`, `SIM_CREATE`, `SIM_UPDATE` |
| Rouge | `LOGIN_FAIL`, `USER_DELETE`, `SNAPSHOT_DELETE` |
| Bleu | `REGISTER`, `USER_CREATE`, `SIM_SHARE` |
| Jaune/ambre | `USER_UPDATE`, `SIM_DELETE`, `SNAPSHOT_RESTORE` |
| Violet | `CATALOG_UPDATE`, `FORMULAS_UPDATE`, `REGIONS_UPDATE` |
| Gris | `LOGS_VIEW`, `LOGS_DOWNLOAD` |

**Parsing d'une ligne brute :**
```javascript
const parts = raw.split(' | ');
// parts[0] = timestamp, [1] = ip, [2] = user(id), [3] = action, [4] = detail
```

---

## 9. Moteur de calcul

Fichier : `public/assets/js/calc.js` — exposé via `window.OSCalc`.

### 9.1 Fonction principale

```javascript
calcLine(line, C, regionId, regions, engagements)
// -> { group, monthly, yearly, three_year, setup, detail }
// yearly     = monthly × 12 + setup
// three_year = (monthly × 12 + setup) × 3 - setup × 2
```

### 9.2 Formules par type

**compute**
```
(vcore × prix_vcore × (1-cpuDisc) + ram × prix_ram × (1-ramDisc)) × qty × 730 × usage × dedicated_factor + stockage
```
`dedicated_factor` = 1.10 si `dedicated: true`.

**dedicated-access**
```
ded_fee[ri] × 730 × qty × usage × (1-cpuDisc)
```

**gpu** — remise uniquement si `eng.applies_to` contient `"gpu"`, plafonnée à `gpu_ri_cap` (30 %)
```
gDisc = applies_to.includes("gpu") ? min(disc, gpu_ri_cap) : 0
gpu_price[ri] × gpu_qty × 730 × usage × (1 - gDisc)
```
→ Les engagements RI CPU/RAM (`applies_to: ["cpu","ram"]`) ne s'appliquent pas aux GPU.  
→ Utiliser l'engagement `ri-gpu` dédié (`applies_to: ["gpu"]`).

**oks** — aucune remise RI (jamais)
```
oks_price[ri] × 730 × qty × usage
```

**bsu**
```
(storage.gb[ri] × storage_gb + storage.iops[ri] × iops) × qty
```

**oos**
```
oos[oos_type || "Standard"][ri] × storage_gb
```
`oos_type` sélectionnable dans l'estimateur si plusieurs tiers existent et sont disponibles dans la région (ex : Standard, Archive).

**net**
```
VPN/LBU/EIP/NAT : tarif[ri] × qty × 730
DirectLink mensuel : tarif[ri] × qty
DirectLink setup  : setup = tarif[ri] × qty  (monthly = 0)
```

**lic**
```
price[ri] × facteur × qty
# facteur : h=730, m=1, y=1/12
```

### 9.3 Constantes exportées

```javascript
window.OSCalc = {
  GROUPS, BLABELS, BCLS,
  FLAG,         // {FR, US, JP}
  HPM,          // 730
  UID,          // () -> string 8 chars
  fE,           // (v, d=0) -> "X EUR"
  fp,           // (v, d=4) -> float
  CPUGENS,      // ["v1".."v7"]
  PERF_OPTS,    // medium/high/highest
  NET_OPTS,     // 10 services réseau
  DEMO,         // 17 lignes de démo
  calcLine,
};
```

---

## 10. Design system CSS

### 10.1 Variables de couleur

```css
:root {
  --os-blue:        #5165F5;   /* liens, boutons actifs, focus */
  --os-blue-dark:   #19233e;   /* header, titres, fond KPI principal */
  --os-blue-mid:    #3d51e0;
  --os-blue-pale:   #eef0fe;
  --os-blue-pale2:  #f5f6ff;
  --os-orange:      #2596be;   /* accent CTA, bordure header */
  --os-orange-dark: #1a7093;
  --os-orange-pale: #e5f4fb;
  --bg:             #f2f5f9;
  --panel:          #ffffff;
  --panel-2:        #f7f9fb;
  --border:         #dce4ec;
  --border-2:       #c4d0db;
  --text:           #19233e;
  --text-dim:       #4d5875;
  --text-muted:     #8090b0;
  --ok:             #0f7a3c;  --ok-bg:  #e6f5ec;
  --warn:           #b45309;  --warn-bg:#fffbeb;
  --err:            #b91c1c;  --err-bg: #fef2f2;
}
```

Note : `--os-orange` est nommé ainsi historiquement mais vaut `#2596be` (bleu Outscale).

### 10.2 Classes principales

| Classe | Description |
|--------|-------------|
| `.hdr` | Header sticky |
| `.card` | Carte blanche border-radius 12px |
| `.btn` | Bouton base |
| `.btn.orange` | CTA (`#2596be`) |
| `.btn.blue` | Secondaire (`#5165F5`) |
| `.btn.red` | Destructif (`#e5534b`) |
| `.btn.ghost` / `.btn.danger` | Transparent / rouge au hover |
| `.btn.sm` / `.btn.xs` | Tailles réduites |
| `.inp` / `.sel` | Input/select |
| `.mono` | DM Mono |
| `.lbl` | Label uppercase 11px |
| `.bdg` | Badge pill |
| `.b-comp`, `.b-ded` | Compute (bleu clair) |
| `.b-gpu` | GPU (violet clair) |
| `.b-oks` | OKS (cyan clair) |
| `.b-bsu`, `.b-oos` | BSU/OOS (bleu ciel) |
| `.b-net` | Réseau (vert) |
| `.b-lic` | Licences (rose) |
| `.acc` / `.acc-hd` / `.acc-bd` | Accordion |
| `.kpi-bar` / `.kpi` / `.kpi-v` | KPI |
| `.pvt` | Tableau pivot |
| `.warn-banner` / `.info-banner` / `.err-banner` / `.ok-banner` | Bandeaux colorés |
| `.prog` / `.prog-b` | Barre de progression |

### 10.3 Barre latérale — classes spécifiques

| Classe | Description |
|--------|-------------|
| `.sidebar` | Conteneur sidebar — `background: var(--os-blue-dark)`, `border-right: 3px solid var(--os-orange)`, `width: 220px`, sticky sous le header (`top: 56px`, `height: calc(100vh - 56px)`) |
| `.sb-btn` | Bouton sidebar sur fond sombre — border `rgba(255,255,255,.12)`, fond `rgba(255,255,255,.06)`, texte `rgba(255,255,255,.82)` |
| `.sb-btn.primary` | CTA "Se connecter" — fond `var(--os-orange)`, blanc |
| `.sb-btn.half` | Variante demi-largeur (Importer/Exporter côte à côte via `display:flex;gap:5px`) |
| `.sb-group` | `flex-direction:column; gap:4px` — regroupe visuellement Mes simulations + actions |
| `.sb-sep` | Séparateur `1px solid rgba(255,255,255,.12)`, `margin: 8px 0` |
| `.sb-section-title` | Titre de section : 10px, uppercase, `rgba(255,255,255,.4)`, letter-spacing `.1em` |
| `.sb-tabs` | Conteneur `display:flex; gap:5px` pour les 3 boutons d'affichage |
| `.sb-tab` | Bouton onglet affichage sur fond sombre (Côté à côté / Saisie / Synthèse) |
| `.sb-tab.on` | Actif : `background:#fff; color:var(--os-blue-dark); font-weight:600` |
| `.sb-user` | Encart utilisateur connecté — fond `rgba(255,255,255,.07)`, border `rgba(255,255,255,.14)`, border-radius 9px |
| `.sb-user-name` | Nom d'utilisateur : 13px, gras, blanc |
| `.sb-user-meta` | Société : 11px, `rgba(255,255,255,.45)` |

---

## 11. Authentification et rôles

### 11.1 Permissions

| Rôle | Estimateur | Admin | Créer comptes | Partager simulations |
|------|-----------|-------|---------------|----------------------|
| `prospect` | Oui (inscription libre) | Non | Non | Non |
| `outscale` | Oui | Non | Prospect seulement | Oui |
| `admin` | Oui | Oui | Tous rôles | Oui |

### 11.2 Admin legacy

`/api/auth/login` accepte `{password}` sans `username`. Vérifié contre `config.json > admin_password_hash`. Token : `uid="admin"`, `role="admin"`.

### 11.3 Flux de connexion

```
POST /api/auth/login {username, password}
  -> cherche dans users.json (insensible à la casse)
  -> si trouvé : vérifie bcrypt -> JWT
  -> sinon     : admin legacy via config.json
  -> token dans localStorage["osc:token"]
```

### 11.4 Gestion erreurs côté client

`api.js` : `if (r.status === 401) { clearToken(); return null; }`

`admin/index.html` : `if (r.status === 401 || r.status === 403) { localStorage.removeItem(TOKEN_KEY); window.location.reload(); }`

---

## 12. Sécurité

### En place

| Mesure | Détail |
|--------|--------|
| Hachage MDP | bcrypt cost 12 |
| JWT | HS256, expiration configurable |
| Décorateurs Flask | `@require_auth` et `@require_admin` sur toutes les routes sensibles |
| Isolation simulations | Accès uniquement aux fichiers propres + partagés explicitement |
| Erreurs JSON | Pas de fuite via pages HTML d'erreur |
| Écriture atomique | `.tmp` → rename |
| HTTPS | Let's Encrypt, TLS 1.2 + 1.3, ciphers ECDHE/DHE uniquement |
| HSTS | `max-age=63072000; includeSubDomains; preload` |
| X-Frame-Options | `SAMEORIGIN` |
| X-Content-Type-Options | `nosniff` |
| Content-Security-Policy | `default-src 'self'`; scripts : `cdnjs.cloudflare.com`, `cdn.tailwindcss.com`, **`'unsafe-inline'`** (Babel injecte un `<script>` inline), `'unsafe-eval'` ; styles : `'unsafe-inline'`, `fonts.googleapis.com` ; fontes : `fonts.gstatic.com` ; connect-src : `cdnjs.cloudflare.com` (source maps Babel) |
| Rate limiting login | nginx : 5 req/min, burst 3, sur `/api/auth/login` — zone `auth_limit:10m` dans `/etc/nginx/conf.d/rate-limit.conf` |
| `.gitignore` complet | `data/config.json`, `data/users.json`, `data/simulations/`, `logs/`, `.venv/`, `__pycache__/`, `*.pyc`, `.env` |
| Journal des actions | `logs/actions.log` — toutes les actions sensibles tracées avec IP + identité (voir §6.2b) |

### Fichiers de configuration nginx

| Fichier | Rôle |
|---------|------|
| `/etc/nginx/sites-enabled/tarifs.osc-tests.fr.conf` | Virtual host HTTPS — headers sécurité, rate limit login, proxy API |
| `/etc/nginx/conf.d/rate-limit.conf` | `limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;` |

---

## 13. Catalogue de tarifs complet

Valeurs en vigueur en **avril 2026**.  
Ordre des 5 valeurs : `eu-west-2` · `cloudgouv-eu-west-1` · `us-west-1` · `us-east-2` · `ap-northeast-1`

### RAM (EUR/GiB/h)
`[0.005, 0.006, 0.004, 0.004, 0.004]`

### Accès FCU Dedicated (EUR/h)
`[2, 2.4, 2.1, 1.8, 2.22]`

### vCore par génération et performance (EUR/h)

| Génération | medium | high | highest |
|-----------|--------|------|---------|
| v1 | [0.011, 0.013, 0.013, 0.011, 0.014] | [0.016, 0.019, 0.018, 0.015, 0.019] | [0.02, 0.024, 0.022, 0.018, 0.024] |
| v2 | [0.016, 0.019, 0.02, 0.015, 0.021] | [0.022, 0.026, 0.026, 0.021, 0.028] | [0.028, 0.034, 0.031, 0.026, 0.034] |
| v3 | [0.02, 0.024, 0.024, 0.019, 0.026] | [0.039, 0.047, 0.042, 0.033, 0.048] | [0.041, 0.049, 0.043, 0.037, 0.051] |
| v4 | [0.033, 0.04, 0.033, 0.027, 0.043] | [0.039, 0.047, 0.042, 0.033, 0.048] | [0.046, 0.055, 0.053, 0.041, 0.054] |
| v5 | [0.031, 0.037, 0.034, 0.028, 0.043] | [0.035, 0.042, 0.039, 0.031, 0.045] | [0.04, 0.048, 0.045, 0.034, 0.054] |
| v6 | [0.031, 0.037, 0.034, 0.028, 0.043] | [0.035, 0.042, 0.039, 0.031, 0.045] | [0.04, 0.048, 0.045, 0.034, 0.054] |
| v7 | [0.034, 0.041, 0.037, 0.032, 0.048] | [0.038, 0.046, 0.042, 0.034, 0.051] | [0.043, 0.052, 0.048, 0.037, 0.054] |

### GPU (EUR/h)

| Modèle | Prix par région |
|--------|----------------|
| Nvidia K2 | [0.55, 0.66, 0.58, 0.5, 0.611] |
| Nvidia P6 | [1.0, 1.2, 1.26, 1.08, 1.332] |
| Nvidia P100 | [1.2, 1.44, 1.1, 0.95, 1.17] |
| Nvidia A10 | [1.5, 1.8, 0, 0, 0] |
| Nvidia V100 | [1.8, 0, 1.89, 1.62, 1.98] |
| Nvidia A100-40 | [2.0, 2.4, 2.6, 2.6, 2.6] |
| Nvidia L40 | [2.0, 2.4, 2.2, 2.2, 2.64] |
| Nvidia A100-80 | [3.6, 4.32, 0, 0, 0] |
| Nvidia H100 | [4.0, 4.8, 4.4, 4.4, 4.51] |
| Nvidia H200 | [5.2, 6.24, 5.2, 5.2, 5.5] |

### OKS Control Plane (EUR/h) — EU-W2 et GOUV uniquement

| Type | Prix |
|------|------|
| cp.mono.master | [0.04, 0.048, 0, 0, 0] |
| cp.3.masters.small | [0.13, 0.156, 0, 0, 0] |
| cp.3.masters.medium | [0.26, 0.312, 0, 0, 0] |
| cp.3.masters.large | [0.39, 0.468, 0, 0, 0] |

### Stockage BSU (EUR/GiB/mois)

| Type | GiB | IOPS |
|------|-----|------|
| BSU Magnetic (standard) | [0.039, 0.047, 0.058, 0.058, 0.039] | [0, 0, 0, 0, 0] |
| BSU Performance (gp2) | [0.11, 0.132, 0.11, 0.11, 0.11] | [0, 0, 0, 0, 0] |
| BSU Enterprise (io1) | [0.13, 0.156, 0.13, 0.13, 0.13] | [0.01, 0.012, 0.01, 0.01, 0.01] |
| Snapshots | [0.055, 0.066, 0.055, 0.055, 0.055] | [0, 0, 0, 0, 0] |

### Stockage objet OOS (EUR/GiB/mois)

| Tier | Prix par région |
|------|----------------|
| Standard | [0.025, 0.03, 0.025, 0.025, 0.025] |
| Archive | [0, 0, 0, 0, 0] *(désactivé — toutes régions OFF)* |

Le catalogue stocke `"oos": {"Standard": [...], "Archive": [...]}`. Des tiers supplémentaires peuvent être ajoutés depuis l'onglet Catalogue de l'admin. Chaque tier dispose de ses propres boutons ON/OFF par région dans `_availability` (clé : `oos.<NomTier>`).

### Réseau

| Service | Tarif | Prix |
|---------|-------|------|
| VPN IPsec | EUR/h | [0.03, 0.036, 0.031, 0.027, 0.033] |
| NAT Gateway | EUR/h | [0.05, 0.06, 0.052, 0.045, 0.056] |
| LBU | EUR/h | [0.03, 0.036, 0.032, 0.027, 0.033] |
| EIP | EUR/h | [0.005, 0.006, 0.005, 0.005, 0.006] |
| DirectLink setup | EUR one-shot | [1000, 1200, 1050, 900, 1500] |
| DirectLink 1 Gbps | EUR/mois | [400, 480, 420, 360, 600] |
| DirectLink 10 Gbps | EUR/mois | [2800, 3360, 2940, 2520, 4200] |
| Hosted DL setup | EUR one-shot | [4200, 4200, 0, 0, 0] |
| Hosted DL 1 Gbps | EUR/mois | [2950, 2950, 0, 0, 0] |
| Hosted DL 10 Gbps | EUR/mois | [4950, 4950, 0, 0, 0] |

### Licences (EUR/h)

| Licence | Prix |
|---------|------|
| Windows Server 2019/2022 (pack 2 cœurs, jusqu'à 2 VMs) | 0.121 |
| Windows 10 E3 VDA (par VM) | 0.060 |
| Red Hat Enterprise Linux OS (par VM) | 0.200 (EU-W2/GOUV), 0 ailleurs |
| Red Hat Enterprise Linux (1 licence par vCore) | 0.019 |
| Oracle Linux OS (par VM) | 0.200 (EU-W2/GOUV), 0 ailleurs |
| Microsoft SQL Server 2019 - Web Edition (pack 2 cœurs) | 0.036 |
| Microsoft SQL Server 2019 - Standard (pack 2 cœurs) | 0.566 |
| Microsoft SQL Server 2019 - Enterprise (pack 2 cœurs) | 2.168 |

### Constantes

| Constante | Valeur | Description |
|-----------|--------|-------------|
| `hours_per_month` | 730 | Heures par mois |
| `dedicated_surcharge` | 0.10 | Surcharge VM dédiée |
| `gpu_ri_cap` | 0.30 | Plafond remise RI GPU |

---

## 14. Évolutions prévues

| Priorité | Évolution |
|----------|-----------|
| Haute | Export PDF du devis |
| Haute | Export CSV / JSON du catalogue depuis l'admin |
| Moyenne | Rotation automatique des logs par date (en complément du RotatingFileHandler) |
| Moyenne | Statistiques d'usage dans le Dashboard (simulations créées/semaine, logins/jour) |
| Basse | Alertes email sur `LOGIN_FAIL` répétés (brute-force) |
| Moyenne | Email de confirmation à l'inscription |
| Moyenne | Partage de simulation par lien public |
| Basse | Comparateur multi-régions côte à côte |
| Basse | Graphiques d'évolution sur 3 ans |
| Basse | Tests API automatisés (`api/test_api.sh`) |

---

## 15. Journal des modifications

| Version | Date | Changements |
|---------|------|-------------|
| 1.0 | 2026-04 | Version monolithique HTML unique |
| 2.0 | 2026-04 | Refonte multi-fichiers Flask+React, auth JWT, interface admin complète |
| 2.1 | 2026-04 | Partage de simulations, création de comptes par outscale, champ société, filtres région, couleur accent #2596be |
| 2.2 | 2026-04-28 | Correction CSP nginx (`'unsafe-inline'` requis par Babel standalone qui injecte un `<script>`) ; cache-busting `?v=2` sur calc.js/api.js ; champ `applies_to` dans formulas.json (engagements différenciés CPU/RAM vs GPU) ; OKS sans remise RI |
| 2.3 | 2026-04-28 | Système de disponibilité par région (`_availability` dans catalog.json) ; boutons ON/OFF par région dans l'admin CatalogTab ; ajout/suppression dynamique de services (GPU, OKS, BSU, Licences, OOS, vCore) ; OOS refactorisé en dict nommé `{Standard, Archive, ...}` ; sélecteur `oos_type` dans l'estimateur ; filtrage des listes déroulantes par région dans `LineEditor` ; champ `company` dans le payload JWT et affiché dans le header (`username · Société`) ; cache-busting `?v=4` |
| 2.4 | 2026-04-29 | Barre latérale gauche : tous les boutons de navigation et d'action déplacés depuis le header vers une sidebar (fond `--os-blue-dark`, bordure droite orange 3px) ; header simplifié au logo seul ; "Historique" renommé "Mes simulations" ; boutons Côté à côté / Saisie / Synthèse regroupés sous section "Affichage" séparée ; bouton "Se connecter" en premier / bloc utilisateur avec nom + société + déconnexion ; bouton "Aide" ancré en bas de sidebar (`marginTop:auto`) ; nouvelles classes CSS `.sidebar`, `.sb-btn`, `.sb-btn.primary`, `.sb-btn.half`, `.sb-group`, `.sb-sep`, `.sb-section-title`, `.sb-tabs`, `.sb-tab`, `.sb-tab.on`, `.sb-user`, `.sb-user-name`, `.sb-user-meta` |
