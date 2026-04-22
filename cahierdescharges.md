# OUTSCALE Cloud Estimator — Spécification complète

> **Version :** catalogue v57 · Mars 2025  
> **Source tarifaire :** [fr.outscale.com/tarifs](https://fr.outscale.com/tarifs/)  
> **Stack :** HTML5 single-file · React 18 (UMD) · Babel standalone · Tailwind CSS  
> **Persistance :** `window.storage` (API Claude artifacts)

---

## Table des matières

1. [Architecture générale](#1-architecture-générale)
2. [Régions](#2-régions)
3. [Types de ressources](#3-types-de-ressources)
4. [Formules de calcul](#4-formules-de-calcul)
5. [Scénarios d'engagement (RI)](#5-scénarios-dengagement-ri)
6. [Catalogue tarifaire complet](#6-catalogue-tarifaire-complet)
7. [Structure des données (lignes)](#7-structure-des-données-lignes)
8. [Composants React](#8-composants-react)
9. [Persistance et import/export](#9-persistance-et-importexport)
10. [Mise à jour des tarifs via API Claude](#10-mise-à-jour-des-tarifs-via-api-claude)
11. [Charte graphique](#11-charte-graphique)
12. [Données de démonstration](#12-données-de-démonstration)

---

## 1. Architecture générale

Application HTML autonome (single-file), ouvrable dans tout navigateur moderne sans serveur.

```
outscale_calculator.html
├── <style>          CSS variables + classes utilitaires (pas de framework CSS externe)
├── <script>         React 18 (UMD CDN) + Babel standalone
└── JSX inline       Tous les composants dans un seul <script type="text/babel">
```

### Onglets de navigation

| ID | Label | Description |
|----|-------|-------------|
| `split` | Côte à côte | Saisie + Synthèse en colonnes |
| `input` | Saisie | Formulaire seul |
| `view` | Synthèse | Tableau croisé + comparaison régionale |
| `catalog` | Tarifs | Grille tarifaire éditable + fetch en ligne |
| `help` | Aide | Guide utilisateur |

### Constantes globales

```js
const HPM = 730;  // Heures par mois (base de facturation)
```

---

## 2. Régions

Ordre fixe — **l'index dans chaque tableau de tarifs correspond à cet ordre :**

| Index | ID | Drapeau | Abréviation | Nom complet |
|-------|----|---------|-------------|-------------|
| 0 | `eu-west-2` | 🇫🇷 | EU-W2 | Europe Ouest (France) |
| 1 | `cloudgouv-eu-west-1` | 🇫🇷 | GOUV | Cloud Souverain (France) |
| 2 | `us-west-1` | 🇺🇸 | US-W1 | US Ouest |
| 3 | `us-east-2` | 🇺🇸 | US-E2 | US Est |
| 4 | `ap-northeast-1` | 🇯🇵 | AP-NE1 | Asie Pacifique (Japon) |

> **Note :** `0` dans un tableau de tarifs signifie « non disponible / sur demande » dans cette région.

---

## 3. Types de ressources

| Type interne | Label UI | Champs spécifiques |
|---|---|---|
| `compute` | VM (FCU) | `qty`, `cpu_gen`, `vcore`, `ram`, `perf`, `dedicated`, `usage`, `engagement`, `storage_type?`, `storage_gb?`, `iops?` |
| `dedicated-access` | Accès FCU Dedicated | `qty`, `usage`, `engagement` |
| `gpu` | GPU flexible | `gpu_qty`, `gpu_type`, `usage`, `engagement` |
| `oks` | OKS Control Plane | `qty`, `cp`, `usage`, `engagement` |
| `bsu` | Stockage bloc | `qty`, `storage_type`, `storage_gb`, `iops` |
| `oos` | Stockage objet | `storage_gb` |
| `net` | Réseau | `net_type`, `net_qty` |
| `lic` | Licence | `lic_type`, `lic_qty` |

### Valeurs des énumérations

**`cpu_gen`** (génération CPU) : `v1` `v2` `v3` `v4` `v5` `v6` `v7`

**`perf`** (performance) :

| Valeur | Label UI | Alias catalogue |
|--------|----------|-----------------|
| `medium` | medium (p3) | Performance normale |
| `high` | high (p2) | Performance élevée |
| `highest` | highest (p1) | Performance maximale |

**`storage_type`** (BSU) :
- `BSU Magnetic (standard)`
- `BSU Performance (gp2)`
- `BSU Enterprise (io1)` ← IOPS provisionnées facturées en plus
- `Snapshots`

**`gpu_type`** :
`Nvidia K2` · `Nvidia P6` · `Nvidia P100` · `Nvidia V100` · `Nvidia A100-40` · `Nvidia A100-80` · `Nvidia A10` · `Nvidia L40` · `Nvidia H100` · `Nvidia H200`

**`cp`** (OKS) :
- `cp.mono.master`
- `cp.3.masters.small`
- `cp.3.masters.medium`
- `cp.3.masters.large`

**`net_type`** (réseau) :
- `VPN IPsec`
- `LBU ( / h)`
- `EIP ( / h)`
- `NAT gateway ( / h)`
- `DirectLink 1 Gb/s (par mois)`
- `DirectLink 10 Gb/s (par mois)`
- `DirectLink - frais de mise en service` ← one-shot
- `Hosted DirectLink - frais de mise en service` ← one-shot
- `Hosted DirectLink 1 Gb/s (par mois)`
- `Hosted DirectLink 10 Gb/s (par mois)`

**`lic_type`** (licences) :
- `Windows Server 2019/2022 (pack 2 cœurs — jusqu'à 2 VMs)`
- `Microsoft SQL Server 2019 — Web Edition (pack 2 cœurs)`
- `Microsoft SQL Server 2019 — Standard (pack 2 cœurs)`
- `Microsoft SQL Server 2019 — Enterprise (pack 2 cœurs)`
- `Red Hat Enterprise Linux (1 licence par vCore)`
- `Oracle Linux OS (par VM)`
- `Red Hat Enterprise Linux OS (par VM)`
- `Windows 10 E3 VDA (par VM)`

---

## 4. Formules de calcul

> Toutes les formules produisent un **coût mensuel HT en euros**.  
> `ri` = index de la région (0–4), `HPM = 730`, `disc` = taux de remise RI (0.0–0.60), `usage` ∈ [0,1].

### 4.1 Compute (VM FCU)

```
coût_compute_horaire = vCores × tarif_vCore[gen][perf][ri]
                     + RAM_GiB × tarif_RAM[ri]

coût_mensuel_VM = coût_compute_horaire × qty × HPM × usage × (1 − disc) × ded_mult

ded_mult = 1.10  si VM dédiée (dedicated = true)
ded_mult = 1.00  sinon
```

Si un volume BSU est attaché à la ligne compute :

```
coût_stockage = (tarif_BSU_gb[ri] × storage_gb + tarif_BSU_iops[ri] × iops) × qty

coût_mensuel_total = coût_mensuel_VM + coût_stockage
```

> **Règle VM dédiée :** +10 % sur le tarif compute uniquement. Le surcoût s'applique **après** la remise RI.  
> **Règle VM dédiée :** une ligne `dedicated-access` séparée doit être ajoutée (frais d'accès horaire au pool dédié).

### 4.2 Accès FCU Dedicated

```
coût_mensuel = tarif_ded_fee[ri] × HPM × qty × usage × (1 − disc)
```

### 4.3 GPU Flexible

```
gpu_disc = MIN(disc, 0.30)   ← remise RI PLAFONNÉE à 30%, quelle que soit la durée

coût_mensuel = tarif_gpu[type][ri] × gpu_qty × HPM × usage × (1 − gpu_disc)
```

> **Règle GPU :** la remise RI est plafonnée à 30 % même pour un engagement 3 ans (contrairement au compute où elle peut atteindre 60 %).

### 4.4 OKS Control Plane

```
coût_mensuel = tarif_oks[cp_type][ri] × HPM × qty × usage × (1 − disc)
```

> OKS disponible uniquement en `eu-west-2` (ri=0) et `cloudgouv-eu-west-1` (ri=1). Les autres régions ont un tarif `0`.

### 4.5 Stockage BSU (volumes indépendants)

```
coût_mensuel = (tarif_bsu_gb[type][ri] × storage_gb
             + tarif_bsu_iops[type][ri] × iops) × qty
```

Pas de facteur `HPM` ni `usage` — facturation mensuelle fixe au GiB.

### 4.6 Stockage objet OOS

```
coût_mensuel = tarif_oos_gb[ri] × storage_gb
```

### 4.7 Réseau — services horaires (VPN, LBU, NAT, EIP)

```
coût_mensuel = tarif_service[ri] × net_qty × HPM
```

### 4.8 Réseau — DirectLink et Hosted DirectLink (abonnements mensuels)

```
coût_mensuel = tarif_dl[bande][ri] × net_qty
```

Pour les **frais de mise en service** (one-shot) :

```
setup = tarif_dl_setup[ri] × net_qty
coût_mensuel = 0

// Impact sur les projections :
annuel      = mensuel × 12 + setup
trois_ans   = (mensuel × 12 + setup) × 3 − setup × 2
             = mensuel × 36 + setup   ← le setup n'est compté qu'UNE fois sur 3 ans
```

### 4.9 Licences

```
facteur = HPM    si base = "h" (facturation horaire)
facteur = 1      si base = "m" (facturation mensuelle)
facteur = 1/12   si base = "y" (facturation annuelle)

coût_mensuel = tarif_lic[type][ri] × facteur × lic_qty
```

> Les licences Microsoft et RHEL ont les mêmes tarifs dans toutes les régions (`price[0..4]` identiques).

### 4.10 Projections temporelles

Calculées pour chaque ligne après `monthly` et `setup` :

```
yearly     = monthly × 12 + setup
three_year = yearly × 3 − setup × 2
           = monthly × 36 + setup     (setup une seule fois sur 3 ans)
```

Puis agrégées par groupe et en total général.

---

## 5. Scénarios d'engagement (RI)

| ID | Label | Remise (`disc`) | Durée | Mode paiement |
|----|-------|-----------------|-------|---------------|
| `on-demand` | À la demande | 0 % | — | — |
| `ri-1m-upfront` | RI 1 mois — upfront | 30 % | 1 mois | Upfront |
| `ri-1y-upfront` | RI 1 an — upfront | 40 % | 1 an | Upfront |
| `ri-2y-upfront` | RI 2 ans — upfront | 50 % | 2 ans | Upfront |
| `ri-3y-upfront` | RI 3 ans — upfront | 60 % | 3 ans | Upfront |
| `ri-1y-quarterly` | RI 1 an — trimestriel | 37 % | 1 an | Trimestriel |
| `ri-2y-quarterly` | RI 2 ans — trimestriel | 45 % | 2 ans | Trimestriel |
| `ri-3y-quarterly` | RI 3 ans — trimestriel | 53 % | 3 ans | Trimestriel |
| `ri-2y-yearly` | RI 2 ans — annuel | 48 % | 2 ans | Annuel |
| `ri-3y-yearly` | RI 3 ans — annuel | 56 % | 3 ans | Annuel |

> Les remises RI s'appliquent au **compute** (FCU, Dedicated, OKS).  
> Les **GPU** sont plafonnés à 30 % (cf. §4.3).  
> Le **stockage** (BSU, OOS) et le **réseau** ne bénéficient pas de remise RI.  
> Les **licences** ne bénéficient pas de remise RI.

---

## 6. Catalogue tarifaire complet

> Format des tableaux : `[EU-W2, GOUV, US-W1, US-E2, AP-NE1]`  
> `0` = non disponible / sur demande dans cette région.

### 6.1 RAM

| Ressource | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|-----------|-------|------|-------|-------|--------|
| RAM (€/GiB/h) | 0.005 | 0.006 | 0.004 | 0.004 | 0.004 |

### 6.2 Accès FCU Dedicated

| Ressource | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|-----------|-------|------|-------|-------|--------|
| Accès dedicated (€/h) | 2.000 | 2.400 | 2.100 | 1.800 | 2.220 |

### 6.3 vCore par génération et performance (€/vCore/h)

#### Génération v7

| Perf | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|------|-------|------|-------|-------|--------|
| medium | 0.034 | 0.041 | 0.037 | 0.032 | 0.048 |
| high | 0.038 | 0.046 | 0.042 | 0.034 | 0.051 |
| highest | 0.043 | 0.052 | 0.048 | 0.037 | 0.054 |

#### Génération v6

| Perf | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|------|-------|------|-------|-------|--------|
| medium | 0.031 | 0.037 | 0.034 | 0.028 | 0.043 |
| high | 0.035 | 0.042 | 0.039 | 0.031 | 0.045 |
| highest | 0.040 | 0.048 | 0.045 | 0.034 | 0.054 |

#### Génération v5

| Perf | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|------|-------|------|-------|-------|--------|
| medium | 0.031 | 0.037 | 0.034 | 0.028 | 0.043 |
| high | 0.035 | 0.042 | 0.039 | 0.031 | 0.045 |
| highest | 0.040 | 0.048 | 0.045 | 0.034 | 0.054 |

#### Génération v4

| Perf | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|------|-------|------|-------|-------|--------|
| medium | 0.033 | 0.040 | 0.033 | 0.027 | 0.043 |
| high | 0.039 | 0.047 | 0.042 | 0.033 | 0.048 |
| highest | 0.046 | 0.055 | 0.053 | 0.041 | 0.054 |

#### Génération v3

| Perf | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|------|-------|------|-------|-------|--------|
| medium | 0.020 | 0.024 | 0.024 | 0.019 | 0.026 |
| high | 0.039 | 0.047 | 0.042 | 0.033 | 0.048 |
| highest | 0.041 | 0.049 | 0.043 | 0.037 | 0.051 |

#### Génération v2

| Perf | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|------|-------|------|-------|-------|--------|
| medium | 0.016 | 0.019 | 0.020 | 0.015 | 0.021 |
| high | 0.022 | 0.026 | 0.026 | 0.021 | 0.028 |
| highest | 0.028 | 0.034 | 0.031 | 0.026 | 0.034 |

#### Génération v1

| Perf | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|------|-------|------|-------|-------|--------|
| medium | 0.011 | 0.013 | 0.013 | 0.011 | 0.014 |
| high | 0.016 | 0.019 | 0.018 | 0.015 | 0.019 |
| highest | 0.020 | 0.024 | 0.022 | 0.018 | 0.024 |

### 6.4 GPU Nvidia (€/GPU/h)

| GPU | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|-----|-------|------|-------|-------|--------|
| Nvidia K2 | 0.550 | 0.660 | 0.580 | 0.500 | 0.611 |
| Nvidia P6 | 1.000 | 1.200 | 1.260 | 1.080 | 1.332 |
| Nvidia P100 | 1.200 | 1.440 | 1.100 | 0.950 | 1.170 |
| Nvidia V100 | 1.800 | 0 | 1.890 | 1.620 | 1.980 |
| Nvidia A100-40 | 2.000 | 2.400 | 2.600 | 2.600 | 2.600 |
| Nvidia A100-80 | 3.600 | 4.320 | 0 | 0 | 0 |
| Nvidia A10 | 1.500 | 1.800 | 0 | 0 | 0 |
| Nvidia L40 | 2.000 | 2.400 | 2.200 | 2.200 | 2.640 |
| Nvidia H100 | 4.000 | 4.800 | 4.400 | 4.400 | 4.510 |
| Nvidia H200 | 5.200 | 6.240 | 5.200 | 5.200 | 5.500 |

### 6.5 OKS Control Plane (€/h)

| Plan | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|------|-------|------|-------|-------|--------|
| cp.mono.master | 0.040 | 0.048 | 0 | 0 | 0 |
| cp.3.masters.small | 0.130 | 0.156 | 0 | 0 | 0 |
| cp.3.masters.medium | 0.260 | 0.312 | 0 | 0 | 0 |
| cp.3.masters.large | 0.390 | 0.468 | 0 | 0 | 0 |

### 6.6 Stockage BSU (€/GiB/mois · €/IOPS/mois)

| Type | Métrique | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|------|----------|-------|------|-------|-------|--------|
| BSU Magnetic (standard) | GiB | 0.039 | 0.047 | 0.058 | 0.058 | 0.039 |
| BSU Performance (gp2) | GiB | 0.110 | 0.132 | 0.110 | 0.110 | 0.110 |
| BSU Enterprise (io1) | GiB | 0.130 | 0.156 | 0.130 | 0.130 | 0.130 |
| BSU Enterprise (io1) | IOPS | 0.010 | 0.012 | 0.010 | 0.010 | 0.010 |
| Snapshots | GiB | 0.055 | 0.066 | 0.055 | 0.055 | 0.055 |

### 6.7 Stockage objet OOS (€/GiB/mois)

| Ressource | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|-----------|-------|------|-------|-------|--------|
| OOS Enterprise | 0.025 | 0.030 | 0.025 | 0.025 | 0.025 |

### 6.8 Réseau (€/h)

| Service | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|---------|-------|------|-------|-------|--------|
| VPN IPsec | 0.030 | 0.036 | 0.031 | 0.027 | 0.033 |
| NAT Gateway | 0.050 | 0.060 | 0.052 | 0.045 | 0.056 |
| LBU | 0.030 | 0.036 | 0.032 | 0.027 | 0.033 |
| EIP | 0.005 | 0.006 | 0.005 | 0.005 | 0.006 |

### 6.9 DirectLink (€)

| Service | EU-W2 | GOUV | US-W1 | US-E2 | AP-NE1 |
|---------|-------|------|-------|-------|--------|
| DirectLink setup (one-shot) | 1 000 | 1 200 | 1 050 | 900 | 1 500 |
| DirectLink 1 Gbps /mois | 400 | 480 | 420 | 360 | 600 |
| DirectLink 10 Gbps /mois | 2 800 | 3 360 | 2 940 | 2 520 | 4 200 |
| Hosted DirectLink setup | 4 200 | 4 200 | 0 | 0 | 0 |
| Hosted DirectLink 1 Gbps /mois | 2 950 | 2 950 | 0 | 0 | 0 |
| Hosted DirectLink 10 Gbps /mois | 4 950 | 4 950 | 0 | 0 | 0 |

### 6.10 Licences (€/h par unité, identiques dans toutes les régions)

| Licence | €/h | Base |
|---------|-----|------|
| Windows Server 2019/2022 (pack 2 cœurs — jusqu'à 2 VMs) | 0.121 | horaire |
| Microsoft SQL Server 2019 — Web Edition (pack 2 cœurs) | 0.036 | horaire |
| Microsoft SQL Server 2019 — Standard (pack 2 cœurs) | 0.566 | horaire |
| Microsoft SQL Server 2019 — Enterprise (pack 2 cœurs) | 2.168 | horaire |
| Red Hat Enterprise Linux (1 licence par vCore) | 0.019 | horaire |
| Oracle Linux OS (par VM) | 0.200 | horaire (EU-W2 et GOUV seulement) |
| Red Hat Enterprise Linux OS (par VM) | 0.200 | horaire (EU-W2 et GOUV seulement) |
| Windows 10 E3 VDA (par VM) | 0.060 | horaire |

---

## 7. Structure des données (lignes)

Chaque ligne d'estimation est un objet JavaScript avec les champs communs suivants :

```js
{
  id:          string,    // UID unique (Math.random().toString(36).slice(2,10))
  type:        string,    // Type de ressource (cf. §3)
  desc:        string,    // Description libre
  engagement:  string,    // ID scénario RI (cf. §5), défaut "on-demand"
  usage:       number,    // Facteur d'utilisation 0–1, défaut 1
  _open:       boolean,   // État UI (accordéon ouvert), non persisté
}
```

Champs spécifiques par type :

```js
// compute
{ qty, cpu_gen, vcore, ram, perf, dedicated,
  storage_type?, storage_gb?, iops? }

// dedicated-access
{ qty }

// gpu
{ gpu_qty, gpu_type }

// oks
{ qty, cp }

// bsu
{ qty, storage_type, storage_gb, iops }

// oos
{ storage_gb }

// net
{ net_type, net_qty }

// lic
{ lic_type, lic_qty }
```

### Format d'export JSON

```json
{
  "lines": [ ...tableau de lignes (sans _open)... ],
  "catalog": { ...objet DEFAULT_C avec éventuelles modifications... }
}
```

---

## 8. Composants React

### Hiérarchie

```
App
├── Header
│   ├── Logo (img CDN + fallback SVG)
│   ├── RegionSelector (5 boutons)
│   ├── NavTabs (5 onglets)
│   └── IO buttons (Import / Export)
├── WarnBanner
├── [tab = split | input]  InputPanel
│   ├── FilterChips
│   ├── LineEditor[] (accordéon par ressource)
│   └── AddMenu (dropdown)
├── [tab = split | view]   SynthesisPanel
│   ├── PivotTable (KPIs + tableau croisé expandable)
│   ├── EngagementBreakdown
│   └── RegionComparison
├── [tab = catalog]  CatalogPage
│   ├── ActionBar (fetch, apply, reset)
│   └── PriceGrid (PriceRow[] par section)
└── [tab = help]  HelpPage
```

### `calcLine(line, C, regionId)` → `{group, monthly, yearly, three_year, setup, detail}`

Fonction pure sans effet de bord. Prend la ligne, le catalogue actif `C`, et l'ID de région. Retourne les coûts calculés selon les formules de §4.

### `PivotTable`

Affiche les résultats groupés par catégorie avec trois horizons temporels (mois / an / 3 ans) et des barres de progression proportionnelles. Chaque groupe est cliquable pour voir le détail ligne par ligne.

### `CatalogPage`

Gère un état local `edits` (map `clé → valeur string`) pour tracker les modifications non appliquées. Les cellules dirty sont orange, les cellules sauvegardées (après clic Appliquer) sont vertes pendant la session. La fonction `applyEdits()` reconstruit le catalogue via un deep-clone et parsing des clés composées.

**Format des clés d'édition :**

| Préfixe | Exemple de clé | Champ ciblé |
|---------|---------------|-------------|
| `ram` | `ram__2` | `C.ram[2]` |
| `ded_fee` | `ded_fee__0` | `C.ded_fee[0]` |
| `vcore` | `vcore__v7__high__1` | `C.vcore.v7.high[1]` |
| `gpu` | `gpu__Nvidia H100__3` | `C.gpu["Nvidia H100"][3]` |
| `oks` | `oks__cp.mono.master__0` | `C.oks["cp.mono.master"][0]` |
| `stor_gb` | `stor_gb__BSU Performance (gp2)__2` | `C.storage["BSU Performance (gp2)"].gb[2]` |
| `stor_iops` | `stor_iops__BSU Enterprise (io1)__1` | `C.storage["BSU Enterprise (io1)"].iops[1]` |
| `oos` | `oos__4` | `C.oos.gb[4]` |
| `vpn` | `vpn__0` | `C.vpn[0]` |
| `nat` | `nat__1` | `C.nat[1]` |
| `lbu` | `lbu__2` | `C.lbu[2]` |
| `eip` | `eip__3` | `C.eip[3]` |
| `dl_setup` | `dl_setup__0` | `C.dl_setup[0]` |
| `dl_1g` | `dl_1g__1` | `C.dl_1gbps[1]` |
| `dl_10g` | `dl_10g__0` | `C.dl_10gbps[0]` |
| `hdl_setup` | `hdl_setup__0` | `C.hdl_setup[0]` |
| `hdl_1g` | `hdl_1g__1` | `C.hdl_1gbps[1]` |
| `hdl_10g` | `hdl_10g__0` | `C.hdl_10gbps[0]` |
| `lic` | `lic__Windows Server...__2` | `C.lic["Windows Server..."].price[2]` |

---

## 9. Persistance et import/export

### `window.storage` (API Claude artifacts)

```js
// Clés utilisées
await window.storage.get("outscale:region")    // ID région sélectionnée
await window.storage.set("outscale:region", id)

await window.storage.get("outscale:catalog")   // JSON.stringify(C)
await window.storage.set("outscale:catalog", JSON.stringify(C))

await window.storage.get("outscale:lines")     // JSON.stringify(lines sans _open)
await window.storage.set("outscale:lines", JSON.stringify(...))

await window.storage.get("outscale:lastFetch") // string date fr-FR
await window.storage.set("outscale:lastFetch", dateString)
```

Toutes les opérations sont dans des blocs `try/catch`. En cas d'erreur (env. hors artifacts), les données de démo sont chargées.

### Import JSON

```js
// Structure attendue
{
  lines: [ ...lignes... ],  // champ obligatoire
  catalog: { ...C... }      // champ optionnel — remplace le catalogue si présent
}
```

Chaque ligne reçoit un nouvel `id` si absent : `x.id || UID()`.

---

## 10. Mise à jour des tarifs via API Claude

Appel à `https://api.anthropic.com/v1/messages` avec le modèle `claude-sonnet-4-20250514` et l'outil `web_search_20250305`.

### Requête

```js
fetch("https://api.anthropic.com/v1/messages", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "claude-sonnet-4-20250514",
    max_tokens: 3000,
    tools: [{ type: "web_search_20250305", name: "web_search" }],
    messages: [{ role: "user", content: PROMPT }]
  })
})
```

### Prompt

Le prompt demande à Claude de :
1. Scraper `https://fr.outscale.com/tarifs/` via `web_search`
2. Retourner **uniquement** un JSON respectant exactement le schéma de `DEFAULT_C`
3. Utiliser `0` pour les valeurs N/A ou sur demande
4. Respecter l'ordre des 5 régions : `[EU-W2, GOUV, US-W1, US-E2, AP-NE1]`
5. Ne pas inclure de backticks markdown ni de texte autour du JSON

### Traitement de la réponse

```js
// Extraire le texte (plusieurs blocs possibles : text, tool_use, tool_result)
const text = data.content
  .filter(b => b.type === "text")
  .map(b => b.text)
  .join("\n");

// Nettoyer et parser
const clean = text.replace(/```json\s*/gi, "").replace(/```\s*/gi, "").trim();
const jsonStart = clean.indexOf("{");
const jsonEnd = clean.lastIndexOf("}");
const parsed = JSON.parse(clean.slice(jsonStart, jsonEnd + 1));

// Merger dans le catalogue courant (deep merge)
function merge(target, src) {
  for (const k of Object.keys(src)) {
    if (typeof src[k] === "object" && !Array.isArray(src[k]) && src[k] !== null) {
      if (!target[k]) target[k] = {};
      merge(target[k], src[k]);
    } else {
      target[k] = src[k];
    }
  }
}
```

### États du fetch

| État | Couleur bannière | Durée |
|------|-----------------|-------|
| `idle` | — | permanent |
| `loading` | Bleu info | pendant la requête |
| `ok` | Vert | 10 s puis retour idle |
| `error` | Rouge | 8 s puis retour idle |

---

## 11. Charte graphique

### Palette CSS (variables)

```css
:root {
  /* Bleu Outscale (brand primary) */
  --os-blue:        #005386;
  --os-blue-dark:   #002f4e;   /* header, titres */
  --os-blue-mid:    #006ea8;
  --os-blue-pale:   #e6f2fa;   /* fonds clairs */
  --os-blue-pale2:  #f0f7fc;   /* hover rows */

  /* Orange accent Outscale */
  --os-orange:      #f47920;   /* CTA, barres de progression */
  --os-orange-dark: #c75f0f;   /* hover CTA */
  --os-orange-pale: #fff4eb;   /* fonds warnings */

  /* Application */
  --bg:       #f2f5f9;   /* fond page */
  --panel:    #ffffff;   /* fond cartes */
  --panel-2:  #f7f9fb;   /* fond secondaire */
  --border:   #dce4ec;
  --border-2: #c4d0db;
  --text:     #1a2b3a;
  --text-dim: #4d6070;
  --text-muted: #8098ac;

  /* Sémantiques */
  --ok:    #0f7a3c;  --ok-bg:   #e6f5ec;
  --warn:  #b45309;  --warn-bg: #fffbeb;
  --err:   #b91c1c;  --err-bg:  #fef2f2;
}
```

### Typographie

- **Corps :** DM Sans (Google Fonts) — weights 300, 400, 500, 600, 700
- **Monospace :** DM Mono (Google Fonts) — weights 400, 500  
  Utilisé pour les valeurs numériques, les tarifs, les identifiants

### Couleurs des badges par type de ressource

| Type | Fond | Texte |
|------|------|-------|
| compute | `#dbeafe` | `#1e4d8c` |
| dedicated-access | `#dbeafe` | `#1e4d8c` |
| gpu | `#ede9fe` | `#5b21b6` |
| oks | `#cffafe` | `#0e7490` |
| bsu | `#e0f2fe` | `#075985` |
| oos | `#e0f2fe` | `#0369a1` |
| net | `#d1fae5` | `#065f46` |
| lic | `#fce7f3` | `#9d174d` |

### Logo

Chargé depuis le CDN Outscale (`outscale-1eecc.kxcdn.com`). Fallback : SVG reconstruit avec le texte `OUTSCALE` en blanc gras + arc/swoosh orange caractéristique de Dassault Systèmes.

Header : fond `#002f4e`, bordure basse `3px solid #f47920`.

---

## 12. Données de démonstration

26 lignes couvrant tous les types de ressources, conçues pour valider les formules. Total attendu en `eu-west-2` à la demande : **~37 730 €/mois**.

| # | Type | Description | Paramètres clés |
|---|------|-------------|-----------------|
| 1 | compute | VM inference v10 | 1×126vC·1024GiB v7/highest, RI 1Y upfront |
| 2 | compute | Web tier | 1×4vC·16GiB v7/high, on-demand |
| 3 | compute | Worker pool | 3×2vC·4GiB v7/medium, on-demand |
| 4 | compute | App front HA | 2×4vC·16GiB v7/highest, on-demand |
| 5 | compute | SGBD + BSU gp2 | 1×2vC·4GiB v7/high + 500GiB gp2 |
| 6 | compute | Cluster RI 1M | 2×8vC·12GiB v7/high, RI 1M upfront |
| 7 | compute | Cluster RI 2Y | 3×8vC·12GiB v7/high, RI 2Y upfront |
| 8 | compute | Cluster RI 3Y | 4×8vC·12GiB v7/high, RI 3Y upfront |
| 9 | dedicated-access | Accès FCU Dedicated | 1 accès |
| 10 | compute | VM dédiée bastion | 1×8vC·32GiB v7/high, dedicated=true |
| 11 | oks | OKS Control Plane HA | 1×cp.3.masters.small |
| 12 | gpu | GPU inférence H100 | 1×H100, on-demand |
| 13 | gpu | Ferme GPU H200 | 8×H200, RI 1Y upfront (cap 30%) |
| 14 | bsu | BSU Magnetic | 2×300GiB standard |
| 15 | bsu | BSU Performance | 1×1500GiB gp2 |
| 16 | bsu | BSU Enterprise | 1×100GiB io1 + 10000 IOPS |
| 17 | bsu | Snapshots | 1×3000GiB |
| 18 | oos | Stockage objet OOS | 150 GiB |
| 19 | lic | Windows Server | 4×pack 2 cœurs |
| 20 | lic | SQL Server Standard | 2×pack 2 cœurs |
| 21 | lic | SQL Server Enterprise | 2×pack 2 cœurs |
| 22 | lic | RHEL | 4×par vCore |
| 23 | net | VPN IPsec | 1 connexion |
| 24 | net | LBU | 1 load balancer |
| 25 | net | NAT Gateway | 1 passerelle |
| 26 | net | EIP | 2 adresses IP publiques |

---

## Annexe — Reproduire le projet from scratch

### Dépendances CDN (dans le `<head>`)

```html
<!-- React 18 UMD -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>

<!-- Tailwind CSS (utilitaires de layout) -->
<script src="https://cdn.tailwindcss.com"></script>

<!-- Babel pour transpiler JSX dans le navigateur -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.5/babel.min.js"></script>

<!-- Polices Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Point d'entrée

```html
<div id="root"></div>
<script type="text/babel" data-presets="react">
  // Tout le code JSX ici
  ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
</script>
```

### Ordre de déclaration dans le script

1. `DEFAULT_C` — catalogue de tarifs par défaut
2. `REGIONS`, `FLAG` — définition des régions
3. `ENGAGEMENTS` — scénarios RI
4. `GROUPS` — groupes de ressources
5. `BLABELS`, `BCLS` — labels et classes des badges
6. `HPM`, `UID`, `fE`, `fp` — constantes et helpers
7. `calcLine()` — moteur de calcul
8. `DEMO` — données de démonstration
9. Composants : `Bdg`, `Fld`, `Sel`, `Num`, `LineEditor`, `AddMenu`, `PivotTable`, `EngBreakdown`, `RegionComp`, `CatalogPage`, `HelpPage`
10. `App` — composant racine
11. `ReactDOM.createRoot(...).render(<App/>)`
