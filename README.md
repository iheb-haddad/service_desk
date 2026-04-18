# Digital Service Desk — BH Bank (PFE)

Application web de gestion de tickets IT : **employés** (demandes), **agents IT** (traitement), **administrateurs** (pilotage, comptes, assignations).

## Fonctionnalités principales

- Authentification sécurisée (hash de mot de passe, sessions Flask-Login, protection CSRF).
- Création de tickets : catégorie, urgence, description, pièces jointes.
- Priorité calculée automatiquement (urgence + poids catégorie).
- Assignation des tickets aux agents IT, changement de statut (y compris par l’admin).
- Escalade automatique si le délai SLA (par catégorie) est dépassé.
- Notifications en base liées aux utilisateurs et aux tickets.
- Commentaires, historique, clôture avec **évaluation de satisfaction** (note 1–5).

## Stack technique

- Python 3.10+, **Flask** 3, **Flask-SQLAlchemy**, **Flask-Login**, **Flask-WTF**
- **MySQL** 8+ (via **PyMySQL**)
- Interface : HTML / CSS (thème professionnel BH), Jinja2

## Installation (développement)

```bash
cd service_desk
python -m venv .venv

# Activer le venv :
# — Git Bash / MINGW64 (obligatoire : source + slash /) :
source .venv/Scripts/activate
# — Invite de commandes Windows (cmd) :
#   .venv\Scripts\activate.bat
# — PowerShell :
#   .venv\Scripts\Activate.ps1
# — Linux / macOS :
#   source .venv/bin/activate

pip install -r requirements.txt
# Windows cmd : copy .env.example .env
cp .env.example .env   # ou copie manuelle sous Git Bash
# Éditer .env : SECRET_KEY, DATABASE_URL
```

Sous **Git Bash**, ne pas utiliser `.venv\Scripts\activate` seul : Bash mange les antislashs et la commande échoue. Sans activation du venv, `pip install` installe dans le Python **global**.

Créer la base et les tables, puis les données de démo :

```bash
python init_db.py
```

Lancer l’application :

```bash
python run.py
```

Ouvrir : `http://127.0.0.1:5000`

Comptes de démonstration (après `init_db.py`) :

| Rôle    | E-mail          | Mot de passe |
|---------|-----------------|--------------|
| Admin   | admin@bh.tn     | Admin123!    |
| Employé | employe@bh.tn   | Employe123!  |
| Agent IT| agent@bh.tn     | Agent123!    |

Les fichiers uploadés sont stockés sous le dossier `uploads/` (créé automatiquement).
