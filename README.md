# 🏥 Projet-BUT-INFO - MedicSearch

**PROJET #4** - Entrepôt de données et agent IA pour les professionnels de santé

Développement d'une plateforme unifiée pour les données de santé utilisant le scraping automatisé et l'intelligence artificielle. Ce projet centralise les informations dispersées pour offrir une vision complète du médicament.

---

## 📋 Table des matières

- [Installation](#-installation)
- [Configuration](#-configuration)
- [Démarrage](#-démarrage)
- [Utilisation](#-utilisation)
- [Structure du projet](#-structure-du-projet)
- [Technos utilisées](#-technos-utilisées)
- [Scripts batch](#-scripts-batch)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 Installation

### 1️⃣ Prérequis

- **Python 3.9+** (avec pip)
- **Docker Desktop** (pour MongoDB)
- **Git** (pour version control)
- **Node.js** (optionnel, pour frontend avancé)

### 2️⃣ Installer les dépendances Python

```bash
# Activer l'environnement virtuel
.venv\Scripts\Activate.ps1

# Installer les dépendances
pip install -r Sources-20251202T134703Z-1-001/Sources/frontend_backend/requirements.txt
```

**Packages principaux:**
- `flask` - Framework web
- `pymongo` - Driver MongoDB
- `qdrant-client` - Recherche vectorielle
- `sentence-transformers` - Embeddings
- `python-dotenv` - Variables d'environnement

---

## ⚙️ Configuration

### 1️⃣ Fichier `.env`

Crée un fichier `.env` dans `Sources-20251202T134703Z-1-001/Sources/frontend_backend/`:

```env
# MongoDB
MONGO_URI=mongodb://localhost:27017/medicsearch

# Mistral AI
MISTRAL_API_KEY=votre_clé_api_mistral

# Flask
FLASK_ENV=development
SECRET_KEY=votre_secret_key

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### 2️⃣ Récupérer les clés API

- **Mistral**: https://console.mistral.ai/
- **Qdrant**: Configuration locale (pas besoin de clé)

---

## 🐳 Docker - Démarrage

### Option 1: Script batch (Windows)

```bash
# DÉMARRER Docker
double-clic sur: docker_start.bat

# ARRÊTER Docker
double-clic sur: docker_stop.bat

# VOIR LE STATUT
double-clic sur: docker_status.bat
```

### Option 2: Ligne de commande

```bash
cd Sources-20251202T134703Z-1-001/Sources/configuration

# Démarrer
docker-compose up -d

# Arrêter
docker-compose down

# Voir le statut
docker ps
```

**Conteneurs lancés:**
- ✅ MongoDB (port 27017)
- ✅ Qdrant (port 6333)
- ✅ Autres services configurés

---

## 🚀 Démarrage de l'application

### 1️⃣ Activer l'environnement virtuel

```bash
.venv\Scripts\Activate.ps1
```

### 2️⃣ Lancer Docker (si pas déjà lancé)

```bash
docker_start.bat
```

### 3️⃣ Lancer l'application Flask

```bash
cd Sources-20251202T134703Z-1-001/Sources/frontend_backend

python app.py
```

**Output attendu:**
```
* Running on http://localhost:5000
* Debug mode: on
```

### 4️⃣ Accéder au site

Ouvre ton navigateur: `http://localhost:5000`

---

## 📊 Utilisation

### 🔍 Recherche
- **Recherche textuelle:** Cherche par nom, symptômes, indications
- **Recherche vectorielle:** Utilise l'IA pour recherche sémantique

### 👤 Authentification
- Login/Register sur la page d'accueil
- Gestion des rôles (admin, user)
- Favoris personnels

### 🤖 Résumés IA
- Les résumés sont générés automatiquement avec Mistral
- Cached pour meilleure performance

### 📤 Export de données
Exporte la base MongoDB:

```bash
cd Sources-20251202T134703Z-1-001/Sources/frontend_backend

python export_backup.py
```

Crée un fichier: `medicsearch_backup_YYYYMMDD_HHMMSS.zip`

---

## 📁 Structure du projet

```
Projet-BUT-INFO/
├── 📄 README.md                    ← Ce fichier
├── 📄 .env                         ← Variables d'environnement (à créer)
├── 📄 .gitignore                   ← Fichiers ignorés par git
│
├── 🐳 docker_start.bat             ← Démarrer Docker
├── 🛑 docker_stop.bat              ← Arrêter Docker
├── 📊 docker_status.bat            ← Voir le statut
│
├── 🔧 github_setup.bat             ← Config GitHub
├── 📤 github_push.bat              ← Push vers GitHub
├── 🔄 github_sync.bat              ← Sync avec GitHub
├── 🔨 github_fix.bat               ← Fix conflits GitHub
│
└── 📦 Sources-20251202T134703Z-1-001/
    └── Sources/
        ├── configuration/
        │   ├── docker-compose.yml   ← Config Docker
        │   ├── Dockerfile           ← Image Docker
        │   └── .env                 ← Env Docker
        │
        └── frontend_backend/
            ├── 🎯 app.py            ← Application Flask (MAIN)
            ├── 📝 requirements.txt   ← Dépendances
            ├── .env                 ← Variables d'env (LOCAL)
            │
            ├── 🔧 config.py         ← Configuration app
            ├── 🗄️  models.py        ← Modèles MongoDB
            ├── 👤 users.py          ← Auth & users
            │
            ├── 🤖 ai_summary.py     ← Résumés avec Mistral
            ├── 🔍 qdrant_search.py  ← Recherche vectorielle
            ├── 📤 vector_search_route.py ← Route recherche
            │
            ├── 🧹 traiter_mistral.py    ← Traitement données
            ├── 🕷️  scraper.py           ← Web scraping
            ├── 📤 export_backup.py      ← Export BD (UTILE!)
            │
            ├── 📁 templates/        ← Pages HTML
            ├── 📁 static/           ← CSS, JS, images
            ├── 📁 scripts/          ← Scripts utilitaires
            ├── 📁 backups/          ← Sauvegardes BD
            │
            └── export_mongodb/      ← Outils export avancés
                ├── export_db.py     ← Export complet
                ├── examples.py      ← Menu interactif
                ├── config.py        ← Config export
                ├── README.md        ← Doc export
                └── QUICKSTART.md    ← Guide rapide
```

---

## 🛠️ Technos utilisées

### Backend
- **Python 3.9+**
- **Flask** - Framework web
- **PyMongo** - Base de données MongoDB
- **Qdrant** - Base vectorielle pour recherche IA
- **Sentence-Transformers** - Embeddings texte

### IA & NLP
- **Mistral AI API** - Génération texte & résumés
- **all-MiniLM-L6-v2** - Modèle embedding

### Frontend
- **HTML5/CSS3** - Pages web
- **JavaScript** - Interactions
- **Jinja2** - Templates

### Infrastructure
- **MongoDB** - Base de données NoSQL
- **Docker** - Containerisation
- **Git/GitHub** - Version control

---

## ⚡ Scripts batch (Windows)

### 🐳 Docker Management

| Fichier | Action |
|---------|--------|
| `docker_start.bat` | Démarrer Docker & conteneurs |
| `docker_stop.bat` | Arrêter Docker |
| `docker_status.bat` | Voir les conteneurs actifs |

### 🔧 GitHub Management

| Fichier | Action |
|---------|--------|
| `github_setup.bat` | Config initiale + 1er commit |
| `github_push.bat` | Push code vers GitHub |
| `github_sync.bat` | Sync local ↔ GitHub |
| `github_fix.bat` | Réparer conflits d'historique |

**Utilisation:** Double-clic sur le fichier `.bat` pour l'exécuter

---

## 📚 Workflows courants

### 🚀 Premier démarrage complet

```bash
# 1. Activer Python
.venv\Scripts\Activate.ps1

# 2. Démarrer Docker
docker_start.bat
# ⏳ Attendre 10-15 secondes

# 3. Lancer l'app
cd Sources-20251202T134703Z-1-001/Sources/frontend_backend
python app.py

# 4. Accéder
# Ouvre: http://localhost:5000
```

### 💾 Sauvegarder la base de données

```bash
cd Sources-20251202T134703Z-1-001/Sources/frontend_backend

# Export simple (fichiers JSON)
python export_backup.py

# Export avancé avec compression
cd export_mongodb
python export_db.py export --compress
```

### 📤 Envoyer sur GitHub

```bash
# Si première fois
github_setup.bat
github_push.bat

# Sinon, pour chaque modification
git add .
git commit -m "Description des changements"
git push
```

ou utiliser: `github_sync.bat`

### 🔄 Traiter les médicaments avec Mistral

```bash
cd Sources-20251202T134703Z-1-001/Sources/frontend_backend

python traiter_mistral.py
```

---

## 🐛 Troubleshooting

### ❌ Docker ne démarre pas

**Solution:**
1. Ouvre Docker Desktop manuellement
2. Attends qu'il démarre complètement
3. Lance `docker_start.bat`

### ❌ "Connexion refusée" MongoDB

**Solution:**
```bash
docker_status.bat
# Vérifie que MongoDB est en cours d'exécution
```

### ❌ erreur "MISTRAL_API_KEY non configurée"

**Solution:**
1. Créé le fichier `.env` dans `frontend_backend/`
2. Ajoute ta clé: `MISTRAL_API_KEY=sk-...`

### ❌ Git: "unrelated histories"

**Solution:**
```bash
github_fix.bat
```

### ❌ Flask ne démarre pas

**Solution:**
```bash
# Vérifie Python
python --version

# Vérifie les dépendances
pip install -r requirements.txt

# Relance
python app.py
```

### ❌ Port 5000 déjà utilisé

**Solution:**
```bash
# Tuer le processus
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Ou changer le port dans app.py
```

---

## 📞 Support & Contributions

### Fichiers d'aide

- 📖 `README.md` (ce fichier) - Vue d'ensemble
- 📖 `Sources-20251202T134703Z-1-001/Sources/frontend_backend/export_mongodb/README.md` - Guide export
- 📖 `Sources-20251202T134703Z-1-001/Sources/frontend_backend/export_mongodb/QUICKSTART.md` - Export rapide

### Besoin d'aide?

1. Vérifie le Troubleshooting
2. Relis la doc pertinente
3. Vérifie les logs (.env correct, services lancés)
4. Redemarre Docker et l'app

---

## 📝 Changelog

### v1.0 (20 Février 2026)
✅ Plateforme complète MedicSearch
✅ Recherche textuelle + vectorielle
✅ Résumés IA avec Mistral
✅ Export/import données MongoDB
✅ Scripts batch pour automation
✅ GitHub integration

---

## 📄 Licence

Projet académique BUT-INFO - Usage éducationnel

---

## 🎯 Résumé rapide

```
1. Activer Python:        .venv\Scripts\Activate.ps1
2. Démarrer Docker:       docker_start.bat
3. Lancer l'app:          python app.py (dans frontend_backend/)
4. Accéder:               http://localhost:5000
5. Arrêter:               docker_stop.bat
6. Exporter BD:           python export_backup.py
7. Push GitHub:           github_sync.bat
```

**C'est prêt! 🚀**
