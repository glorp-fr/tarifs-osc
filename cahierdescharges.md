# Cahier des charges — OUTSCALE Cloud Estimateur

**Projet :** Estimateur de coûts cloud OUTSCALE  
**Version :** 2.1  
**Date :** Avril 2026  
**Auteur :** Jaouen Trillot

---

## 1. Contexte et objectifs

L'estimateur OUTSCALE permet à des prospects et à des commerciaux Outscale de construire des devis cloud interactifs : sélection de ressources (VM, GPU, stockage, réseau, licences), calcul instantané du coût mensuel/annuel/3 ans, export et sauvegarde des simulations.

### Objectifs principaux

1. **Estimateur en libre-service** — un prospect peut s'inscrire, configurer son infrastructure cible et sauvegarder ses simulations.
2. **Outil commercial** — les utilisateurs Outscale créent des simulations pour leurs clients, les partagent avec eux et créent leurs comptes.
3. **Administration centralisée** — un administrateur gère le catalogue de tarifs, les régions, les engagements RI et les utilisateurs.

---

## 2. Architecture technique

### Stack

| Couche | Technologie | Raison |
|--------|-------------|--------|
| Backend | Python 3 / Flask | Disponible sur le serveur, léger |
| Auth | JWT HS256 (PyJWT) | Stateless, pas de session serveur |
| Persistance | Fichiers JSON | Pas de BDD, snapshots lisibles |
| Frontend | React 18 CDN + Babel standalone | Pas de build step |
| Reverse proxy | nginx `/api/` → Flask :5000 | Déjà en place |

### Structure des fichiers

```
tarifs-osc/
├── api/
│   ├── server.py           # Backend Flask (routes CRUD + auth JWT)
│   ├── setup.py            # Script init mot de passe admin
│   └── requirements.txt    # Dépendances Python
├── data/
│   ├── catalog.json        # Tarifs actifs
│   ├── formulas.json       # Engagements / remises RI
│   ├── regions.json        # Régions Outscale
│   ├── config.json         # Config app + hash mot de passe admin legacy
│   ├── users.json          # Utilisateurs (hors admin legacy)
│   ├── simulations/        # {user_id}.json — simulations par utilisateur
│   └── history/            # Snapshots horodatés automatiques
├── public/
│   ├── index.html          # Estimateur (SPA React)
│   ├── admin/
│   │   └── index.html      # Interface admin (SPA React)
│   └── assets/
│       ├── style.css       # Design system CSS
│       └── js/
│           ├── calc.js     # Moteur de calcul (pur, sans UI)
│           ├── api.js      # Client API (fetch + auth helpers)
│           └── app.js      # (réservé — actuellement inline dans index.html)
├── nginx.conf.example
├── tarifs-osc.service.example
├── cahierdescharges.md
└── TODO.md
```

---

## 3. Authentification et gestion des utilisateurs

### 3.1 Rôles

| Rôle | Accès | Création de comptes | Partage de simulations |
|------|-------|---------------------|------------------------|
| `prospect` | Estimateur uniquement. Simulations privées. Inscription en libre-service. | Non | Non |
| `outscale` | Idem prospect. Créé par un admin ou un autre Outscale. | Peut créer des comptes `prospect` | Peut partager ses simulations avec d'autres utilisateurs |
| `admin` | Estimateur + interface d'administration complète. | Peut créer tous les rôles | Peut partager ses simulations |

### 3.2 Token JWT

- Algorithme : HS256
- Durée de vie : 8 h (configurable dans `config.json` via `session_ttl_hours`)
- Payload : `{sub: user_id, username, role, exp}`
- Clé partagée entre estimateur et admin via `localStorage['osc:token']`
- Admin legacy (`config.json`) compatible sans username pour rétrocompatibilité

### 3.3 Flux d'authentification

```
[Page estimateur] ──→ LoginPage (username + password)
    ├── Inscription (prospect uniquement) → POST /api/auth/register
    └── Connexion → POST /api/auth/login
         └── JWT → localStorage['osc:token']
              ├── role=admin    → lien "Admin" visible dans le header
              ├── role=outscale → bouton "Créer un compte" visible
              └── tous rôles   → accès à l'estimateur et aux simulations personnelles

[Page admin] ──→ vérifie localStorage['osc:token'] + role=admin
    └── 401/403 → déconnexion auto + rechargement
```

### 3.4 Modèle utilisateur

Fichier `data/users.json` :
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

Champs :
- `id` — token hex 8 octets généré à la création
- `username` — identifiant unique, min 3 caractères (insensible à la casse)
- `password_hash` — bcrypt cost 12
- `role` — `prospect` | `outscale` | `admin`
- `company` — société (optionnel, chaîne vide si absent)
- `created_by` — username du créateur (absent si auto-inscription)

### 3.5 Modèle simulation

Fichier `data/simulations/{user_id}.json` (tableau) :
```json
[
  {
    "id": "b7e2f4a1",
    "name": "Projet A — Q2 2026",
    "lines": [...],
    "activeRegions": ["eu-west-2"],
    "monthly": 4820.5,
    "savedAt": "2026-04-24T14:30:00Z",
    "owner_id": "a3f8c1d2",
    "owner_username": "jdupont",
    "shared_with": ["x9k3m2p1"]
  }
]
```

- `shared_with` — liste des `user_id` avec qui la simulation est partagée (tableau vide par défaut)
- Une simulation partagée apparaît en lecture dans la liste du destinataire (chargement uniquement, pas de modification ni suppression)

---

## 4. Routes API

### Auth

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/api/auth/login` | — | Connexion (username+password ou password seul legacy) |
| POST | `/api/auth/register` | — | Inscription prospect (champ `company` optionnel) |
| GET | `/api/auth/me` | JWT | Infos utilisateur courant |

### Simulations

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET | `/api/simulations` | JWT | Simulations de l'utilisateur **+** simulations partagées avec lui |
| POST | `/api/simulations` | JWT | Créer une simulation (owner_id, owner_username, shared_with: [] auto-remplis) |
| PUT | `/api/simulations/:id` | JWT | Modifier (renommer, mettre à jour les lignes) |
| DELETE | `/api/simulations/:id` | JWT | Supprimer (propriétaire uniquement) |
| PUT | `/api/simulations/:id/share` | JWT outscale/admin | Mettre à jour la liste shared_with |

### Utilisateurs

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET | `/api/users` | Admin | Liste tous les utilisateurs (sans hash de mot de passe) |
| GET | `/api/users/directory` | JWT | Liste légère `{id, username, role}` pour le picker de partage |
| POST | `/api/users` | JWT outscale/admin | Créer un utilisateur — outscale : prospect uniquement ; admin : tous rôles |
| PATCH | `/api/users/:id` | Admin | Modifier rôle, société ou mot de passe |
| DELETE | `/api/users/:id` | Admin | Supprimer + supprime les simulations associées |

### Catalogue et configuration (admin)

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| GET | `/api/catalog` | — | Catalogue des tarifs |
| PUT | `/api/catalog` | Admin | Mettre à jour + snapshot automatique |
| GET | `/api/formulas` | — | Engagements RI |
| PUT | `/api/formulas` | Admin | Mettre à jour + snapshot automatique |
| GET | `/api/regions` | — | Régions actives |
| PUT | `/api/regions` | Admin | Mettre à jour + snapshot automatique |
| GET | `/api/history` | Admin | Liste des snapshots (filtre `?kind=catalog\|formulas\|regions`) |
| GET | `/api/history/:id` | Admin | Contenu d'un snapshot |
| POST | `/api/history/:id/restore` | Admin | Restaurer (sauvegarde auto avant) |
| DELETE | `/api/history/:id` | Admin | Supprimer un snapshot |
| GET | `/api/health` | — | Santé du service |

### Gestion des erreurs

Toutes les routes retournent du JSON y compris en cas d'erreur :

```json
{ "error": "Message lisible" }
```

Codes HTTP utilisés : `200`, `201`, `400`, `401`, `403`, `404`, `409`, `500`, `503`.

---

## 5. Interface estimateur (`public/index.html`)

### 5.1 Composants principaux

```
AuthGate
├── LoginPage                  (si non authentifié — login + inscription prospect)
└── UserCtx.Provider
    └── App
        ├── Header
        │   ├── Logo + navigation (Côté à côté / Saisie / Synthèse / Aide)
        │   ├── Bouton "Historique"      → ProfilesModal
        │   ├── Bouton "Créer un compte" → CreateAccountModal (outscale/admin)
        │   ├── Bouton "Importer" / "Exporter"
        │   ├── Lien "Admin"             (admin uniquement)
        │   └── Badge rôle + username + Déconnexion
        ├── Cadre "Hypothèses de consommation"
        │   ├── Barre de filtres
        │   │   ├── Filtre type : Tout / Compute / GPU / OKS / BSU / OOS / Réseau / Licences
        │   │   ├── Filtre région (si plusieurs régions) : Toutes / EU-W2 / US-W1 / ...
        │   │   ├── Bouton "Démo"   (solid #2596be)
        │   │   └── Bouton "Vider"  (solid rouge)
        │   ├── Liste des ressources (scroll auto vers le bas à l'ajout)
        │   │   └── LineEditor × N (accordion par ressource)
        │   └── AddMenu (menu d'ajout de ressource)
        ├── Cadre "Synthèse"
        │   ├── PivotTable (tableau croisé région × groupe)
        │   └── EngBreakdown (répartition par engagement)
        ├── ProfilesModal      (historique des simulations)
        ├── ShareModal         (partage avec d'autres utilisateurs)
        └── CreateAccountModal (création de compte prospect)
```

### 5.2 Scroll automatique

Lors de l'ajout d'une ressource, la liste défile automatiquement vers le bas :

```jsx
const listRef = useRef(null);
const prevLen = useRef(0);
useEffect(() => {
  if (lines.length > prevLen.current && listRef.current) {
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }
  prevLen.current = lines.length;
}, [lines.length]);
```

### 5.3 Filtres de la barre de ressources

Deux axes de filtrage indépendants, cumulatifs :

| Filtre | État | Comportement |
|--------|------|--------------|
| Type | `filter` (string \| "") | Affiche uniquement le type sélectionné. "Compute" inclut `dedicated-access`. |
| Région | `regionFilter` (string \| null) | Affiche uniquement les ressources de la région sélectionnée. Visible seulement si plusieurs régions existent. |

Les boutons région affichent le compteur de lignes pour chaque région. Cliquer à nouveau sur la région active désélectionne (retour à "Toutes").

### 5.4 Gestion des simulations (ProfilesModal)

Accessible via le bouton **"Historique"** dans le header. Les simulations sont stockées côté serveur, privées par utilisateur.

**Simulations propres :**
- Sauvegarder l'état courant avec un nom
- Charger (remplace les lignes courantes)
- Renommer (double-clic sur le nom)
- Supprimer
- Partager ⇗ (bouton visible pour outscale/admin uniquement)

**Simulations partagées avec moi :**
- Affichées dans une section séparée avec la mention "Partagé par X"
- Chargement uniquement (lecture seule — pas de suppression ni renommage)

### 5.5 Partage de simulations (ShareModal)

Accessible via le bouton ⇗ dans le ProfilesModal, réservé aux utilisateurs `outscale` et `admin`.

- Affiche la liste de tous les comptes (via `GET /api/users/directory`)
- Cases à cocher pré-cochées selon l'état actuel de `shared_with`
- Enregistre via `PUT /api/simulations/:id/share`
- Le badge "Partagé (N)" apparaît sur la simulation dans le ProfilesModal

### 5.6 Création de compte (CreateAccountModal)

Bouton **"Créer un compte"** visible pour les utilisateurs `outscale` et `admin`.

- `outscale` : crée uniquement des comptes `prospect`
- `admin` : peut choisir le rôle (prospect / outscale / admin)
- Champs : identifiant, mot de passe, société (optionnel), rôle (admin seulement)
- Les comptes créés sont immédiatement actifs

### 5.7 Inscription en libre-service (LoginPage)

Accessible depuis la page de connexion, onglet "Créer un compte". Crée un compte `prospect`.

Champs : identifiant (min 3 car.), mot de passe (min 6 car.), confirmation, société (optionnel).

---

## 6. Interface admin (`public/admin/index.html`)

### 6.1 Accès

Réservé au rôle `admin`. Vérification du token JWT côté client au chargement ; 401/403 → déconnexion automatique. Token partagé avec l'estimateur (`osc:token`).

### 6.2 Onglets

| Onglet | Contenu |
|--------|---------|
| Dashboard | Résumé (version catalog/formulas/regions, nb utilisateurs, 5 derniers snapshots) |
| Catalogue | Édition RAM, vCore, GPU, OKS, BSU, OOS, réseau, licences + constantes globales |
| Formules RI | Liste éditable des engagements (id, libellé, remise %, actif) |
| Régions | Liste éditable avec drag-and-drop (ordre = index dans les tableaux de prix) |
| Utilisateurs | CRUD complet : créer (avec société), changer rôle, réinitialiser MDP, supprimer |
| Historique | Liste des snapshots, filtre par type, diff visuel, restauration, suppression |

### 6.3 Onglet Utilisateurs — détail

**Formulaire de création** : identifiant, mot de passe initial, société (optionnel), rôle.

**Tableau** : identifiant, société, rôle (modifiable inline), date de création, créé par, ID technique, actions (reset MDP / supprimer).

### 6.4 Sécurité des modifications

- Indicateur dirty / saved sur chaque onglet éditable
- Commentaire obligatoire avant toute sauvegarde de catalogue/formules/régions
- Snapshot automatique à chaque PUT (horodaté `YYYYMMDDTHHMMSSZ_kind.json`)
- Confirmation modale avant restauration d'un snapshot

---

## 7. Moteur de calcul (`public/assets/js/calc.js`)

Pur JavaScript, sans dépendance UI. Exposé via `window.OSCalc`.

### Fonction principale

```javascript
calcLine(line, C, regionId, regions, engagements)
→ { group, monthly, yearly, three_year, setup, detail }
```

### Types de ressources supportés

| Type | Paramètres |
|------|-----------|
| `compute` | cpu_gen, vcore, ram, perf, qty, engagement, dedicated, usage, storage_type, storage_gb, iops |
| `dedicated-access` | qty, engagement, usage |
| `gpu` | gpu_type, gpu_qty, engagement, usage |
| `oks` | cp (control plane type), qty, engagement, usage |
| `bsu` | storage_type, storage_gb, iops, qty |
| `oos` | storage_gb |
| `net` | net_type, net_qty |
| `lic` | lic_type, lic_qty |

### Remises RI

- Les remises s'appliquent à compute, dedicated-access, gpu, oks
- GPU : remise plafonnée à `gpu_ri_cap` (défaut 30 %)
- BSU, OOS, réseau : pas de remise

---

## 8. Design system (`public/assets/style.css`)

### Palette de couleurs

| Variable | Valeur | Usage |
|----------|--------|-------|
| `--os-blue` | `#5165F5` | Liens, boutons actifs, focus |
| `--os-blue-dark` | `#19233e` | Header, titres, fond KPI principal |
| `--os-blue-mid` | `#3d51e0` | Hover boutons bleus |
| `--os-orange` | `#2596be` | Accent principal — boutons CTA, bordure header |
| `--os-orange-dark` | `#1a7093` | Hover CTA, totaux dans les tableaux |
| `--os-orange-pale` | `#e5f4fb` | Fond bandeaux d'avertissement |

> Le terme "orange" est conservé dans le code CSS pour la cohérence des noms de variables ; la couleur effective est `#2596be` (bleu Outscale).

### Classes de boutons

| Classe | Rendu |
|--------|-------|
| `.btn` | Bouton neutre (fond blanc, bordure gris) |
| `.btn.orange` | Bouton CTA principal (fond `#2596be`, texte blanc) |
| `.btn.blue` | Bouton secondaire (fond `#5165F5`, texte blanc) |
| `.btn.red` | Bouton destructif (fond `#e5534b`, texte blanc) |
| `.btn.ghost` | Bouton transparent (bordure invisible) |
| `.btn.danger` | Bouton ghost avec rouge au hover |
| `.btn.sm` / `.btn.xs` | Tailles réduites |

---

## 9. Déploiement

### Prérequis

- Python 3.10+
- nginx
- Accès sudo sur le serveur

### Installation

```bash
# 1. Dépendances Python
cd /var/www/html/tarifs-osc
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt

# 2. Initialiser le mot de passe admin
python3 api/setup.py

# 3. Configurer nginx
sudo cp nginx.conf.example /etc/nginx/sites-available/tarifs-osc
sudo ln -s /etc/nginx/sites-available/tarifs-osc /etc/nginx/sites-enabled/
# Adapter server_name dans le fichier
sudo nginx -t && sudo nginx -s reload

# 4. Configurer systemd
sudo cp tarifs-osc.service.example /etc/systemd/system/tarifs-osc.service
sudo systemctl daemon-reload
sudo systemctl enable --now tarifs-osc
```

### Après une mise à jour du code

```bash
sudo systemctl restart tarifs-osc
```

Le service Flask doit être redémarré après toute modification de `api/server.py` pour que les nouvelles routes soient actives.

### Vérification

```bash
curl http://localhost:5000/api/health
# → {"status": "ok", "ts": "..."}

curl http://localhost:5000/api/catalog
# → {"vcore": {...}, "ram": [...], ...}
```

---

## 10. Sécurité

### Mesures en place

- Mots de passe hachés avec bcrypt (cost factor 12)
- Tokens JWT avec expiration configurable (défaut 8 h)
- Décorateurs `@require_auth` et `@require_admin` côté serveur sur toutes les routes sensibles
- Isolation des simulations par `user_id` — un utilisateur ne peut accéder qu'à ses propres simulations et à celles explicitement partagées avec lui
- Toutes les erreurs HTTP retournent du JSON (pas de fuite d'informations via les pages d'erreur HTML)

### Mesures recommandées

- Rate limiting sur `/api/auth/login` (max 5 tentatives / 5 min)
- Headers HTTP nginx : CSP, HSTS, X-Frame-Options
- `.gitignore` : exclure `data/config.json`, `data/users.json`, `data/simulations/`, `data/history/`
- HTTPS via Let's Encrypt (certbot)

---

## 11. Évolutions prévues

| Priorité | Évolution |
|----------|-----------|
| Haute | Export PDF du devis depuis l'estimateur |
| Haute | Export CSV / JSON du catalogue depuis l'admin |
| Moyenne | Email de confirmation à l'inscription (prospect) |
| Moyenne | Partage de simulation par lien public |
| Basse | Comparateur multi-régions côte à côte |
| Basse | Graphiques d'évolution de coût sur 3 ans |

---

## 12. Journal des modifications

| Version | Date | Changements |
|---------|------|-------------|
| 1.0 | 2026-04 | Version monolithique HTML unique |
| 2.0 | 2026-04 | Refonte multi-fichiers Flask+React, auth JWT, interface admin complète |
| 2.1 | 2026-04 | Partage de simulations (outscale/admin), création de comptes par outscale, champ société, filtres région dans le cadre hypothèses, couleur accent #2596be, boutons Démo/Vider plus visibles |
