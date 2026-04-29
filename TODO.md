# Refonte Outscale Cloud Estimateur — TODO

## Architecture cible

```
tarifs-osc/
├── api/
│   ├── server.py           ✅ Backend Flask (routes CRUD + auth JWT)
│   ├── setup.py            ✅ Script init mot de passe admin
│   └── requirements.txt    ✅ Dépendances Python
├── data/
│   ├── catalog.json        ✅ Tarifs actifs (extrait du HTML d'origine)
│   ├── formulas.json       ✅ Engagements / remises RI
│   ├── regions.json        ✅ Régions Outscale
│   ├── config.json         ✅ Config app + hash mot de passe admin
│   └── history/            ✅ Snapshots horodatés automatiques
├── public/
│   ├── index.html          ⬜ Estimateur (SPA React — à migrer)
│   ├── admin/
│   │   └── index.html      ⬜ Interface admin (à créer)
│   └── assets/
│       ├── style.css       ⬜ CSS extrait du HTML monolithique
│       └── js/
│           ├── calc.js     ⬜ Moteur de calcul (pur, sans UI)
│           ├── api.js      ⬜ Client API (fetch catalog/formulas/regions)
│           └── app.js      ⬜ Composants React estimateur
├── nginx.conf.example      ✅ Config nginx (static + reverse proxy /api/)
├── tarifs-osc.service.ex.. ✅ Unité systemd pour démarrage auto
└── TODO.md                 ✅ Ce fichier
```

---

## Phase 1 — Infrastructure serveur

- [ ] **Installer les dépendances Python**
  ```bash
  pip3 install flask flask-cors pyjwt bcrypt
  # ou dans un venv :
  python3 -m venv .venv && source .venv/bin/activate
  pip3 install -r api/requirements.txt
  ```

- [ ] **Initialiser le mot de passe admin**
  ```bash
  python3 api/setup.py
  ```

- [ ] **Tester le backend localement**
  ```bash
  python3 api/server.py
  curl http://localhost:5000/api/health
  curl http://localhost:5000/api/catalog
  ```

- [ ] **Configurer nginx**
  - Copier `nginx.conf.example` vers `/etc/nginx/sites-available/tarifs-osc`
  - Adapter `server_name` et `root`
  - `sudo nginx -t && sudo nginx -s reload`

- [ ] **Configurer systemd**
  ```bash
  sudo cp tarifs-osc.service.example /etc/systemd/system/tarifs-osc.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now tarifs-osc
  ```

- [ ] **HTTPS** — Installer certbot + certificat Let's Encrypt
  ```bash
  sudo apt install certbot python3-certbot-nginx
  sudo certbot --nginx -d tarifs.example.com
  ```

---

## Phase 2 — Refactoring Frontend Estimateur

- [x] **Extraire le CSS** → `public/assets/style.css`
- [x] **Extraire le moteur de calcul** → `public/assets/js/calc.js`
  - `calcLine(line, C, regionId, regions, engagements)` — pur, sans DOM
  - Constantes : GROUPS, FLAG, HPM, UID, fE, fp, DEMO, NET_OPTS, PERF_OPTS, CPUGENS
- [x] **Créer `public/assets/js/api.js`** — `OSApi.loadAll()` avec fallback localStorage → défauts
- [x] **Migrer vers `public/index.html`**
  - React Context `AppCtx` pour regions et engagements (évite le prop drilling)
  - Catalog + régions + engagements chargés depuis l'API au démarrage
  - localStorage remplace window.storage (Claude artifact API supprimé)
  - Onglet "Tarifs" supprimé (déplacé dans l'admin)
  - Lien "Admin" ajouté dans le header
  - Bandeau d'avertissement si l'API est indisponible

- [ ] **Tester l'estimateur** avec données issues de l'API

- [ ] **Gestion des licences**
  - Calcul du coût des licences (Windows, SQL Server, etc.) depuis le catalog
  - Affectation d'une ou plusieurs licences à une VM dans l'estimateur
  - Affichage du coût licence dans le détail de ligne et dans le total

---

## Phase 3 — Interface Admin

### Page login (`public/admin/index.html`) ✅
- [x] Formulaire mot de passe → POST `/api/auth/login`
- [x] JWT stocké dans `localStorage` (`osc:admin_token`)
- [x] Redirection vers le dashboard après login
- [x] 401 → déconnexion auto et rechargement

### Dashboard ✅
- [x] Résumé catalog / formulas / regions (version, date, commentaire)
- [x] 5 derniers snapshots
- [x] Bouton Déconnexion

### Onglet — Catalogue des tarifs ✅
- [x] Toutes les sections : RAM, Dedicated, vCore, GPU, OKS, BSU, OOS, Réseau, Licences
- [x] Constantes éditables : heures/mois, surcharge dédiée %, plafond RI GPU %
- [x] Indicateur dirty (orange) / saved (vert)
- [x] Commentaire obligatoire avant sauvegarde
- [x] PUT `/api/catalog` + snapshot auto

### Onglet — Formules RI ✅
- [x] Liste éditable : id, libellé, remise, actif/inactif
- [x] Ajouter / supprimer un engagement
- [x] PUT `/api/formulas` + snapshot auto

### Onglet — Régions ✅
- [x] Liste éditable : flag, id, nom, actif/inactif
- [x] Drag-and-drop pour réordonner (l'ordre = index dans les tableaux de prix)
- [x] Ajouter / supprimer une région
- [x] Bandeau d'avertissement : modification des régions ≠ mise à jour automatique du catalog
- [x] PUT `/api/regions` + snapshot auto

### Onglet — Historique ✅
- [x] Liste des snapshots (date, type, auteur, commentaire)
- [x] Filtre par type (catalog / formulas / regions / tous)
- [x] Bouton "Comparer" → diff visuel clé par clé vs version courante
- [x] Bouton "Restaurer" → POST `/api/history/:id/restore` + confirmation
- [x] Bouton "Supprimer" snapshot

---

## Phase 5 — Intégration API Outscale

- [ ] **Récupération des tarifs via API Outscale**
  - Identifier les endpoints Outscale exposant les tarifs (prix à la demande, RI, stockage, réseau)
  - Créer une route backend `/api/sync` déclenchant la mise à jour du catalog depuis l'API Outscale
  - Planifier une synchronisation automatique périodique (cron ou systemd timer)
  - Snapshot automatique avant chaque mise à jour
  - Bouton "Synchroniser" dans l'interface admin

---

/
## Phase 4 — Qualité / Déploiement

- [ ] **Sécurité**
  - Rate limiting sur `/api/auth/login` (max 5 tentatives / 5 min)
  - Headers HTTP sécurisés dans nginx (CSP, HSTS, X-Frame-Options)
  - `.gitignore` : exclure `data/config.json` et `data/history/`

- [ ] **Export**
  - Bouton "Exporter CSV" depuis l'admin (catalog complet)
  - Bouton "Télécharger JSON" (backup manuel du catalog)

- [ ] **README.md**
  - Prérequis (Python 3.10+, nginx)
  - Installation pas à pas
  - Description des routes API
  - Procédure de restauration d'un snapshot

- [ ] **Tests API** — fichier `api/test_api.sh`
  ```bash
  # Login, CRUD catalog, snapshot, restore
  ```

---

## Notes techniques

| Sujet | Choix | Raison |
|---|---|---|
| Backend | Python 3 / Flask | Déjà disponible sur le serveur |
| Auth | JWT HS256 (PyJWT) | Stateless, simple, pas de BDD |
| Persistance | JSON files | Pas de BDD, snapshots lisibles |
| Frontend | React 18 CDN + Babel standalone | Pas de build step, simple |
| Reverse proxy | nginx `/api/` → Flask :5000 | Déjà en place |
| Historique | Fichiers horodatés `YYYYMMDDTHHMMSSZ_kind.json` | Lisibles sans outil |
