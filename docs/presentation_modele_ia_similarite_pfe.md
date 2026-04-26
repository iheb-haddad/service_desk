# Présentation du modèle d’intelligence artificielle par similarité textuelle

## Digital Service Desk — BH Bank (PFE)

_Document rédigé pour intégration au rapport de fin d’études. Il décrit le module « suggestion de solution » implémenté dans l’application._

---

## 1. Introduction et positionnement du « modèle IA »

Dans le cadre de ce projet de **service desk** (gestion des demandes IT), le terme **intelligence artificielle** désigne ici un **modèle léger d’aide à la décision**, basé sur la **similarité de texte** entre tickets. Il ne s’agit pas d’un grand modèle de langue (type GPT) ni d’un apprentissage profond sur GPU : il s’agit d’un **moteur de recherche de cas similaires** qui propose une **solution déjà validée dans le passé** lorsqu’un nouveau ticket ressemble fortement à un ancien problème.

Cette approche est volontairement **simple, explicable et intégrable** dans une application web classique (Flask, MySQL), ce qui convient à un contexte bancaire où la **traçabilité** et le **contrôle humain** (validation par l’agent IT) sont prioritaires.

---

## 2. But et objectifs du module

### 2.1 But général

Le module vise à **réduire le temps de traitement** des tickets en aidant les **agents IT** à retrouver rapidement une **solution éprouvée** lorsque le problème décrit est **répétitif** ou **proche** d’un incident déjà résolu.

### 2.2 Objectifs opérationnels

| Objectif                             | Description                                                                                                   |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| **Détection de tickets similaires**  | Comparer automatiquement le texte d’un nouveau ticket aux descriptions d’anciens tickets clos ou résolus.     |
| **Proposition de solution**          | Si un ticket historique est suffisamment proche, proposer la **solution enregistrée** associée à ce ticket.   |
| **Réduction du délai de traitement** | Moins de recherche manuelle dans l’historique ; point de départ immédiat pour l’agent.                        |
| **Aide à la qualité**                | Capitaliser sur les résolutions déjà documentées dans la base.                                                |
| **Responsabilité humaine**           | L’agent **valide**, **modifie** ou **rejette** la suggestion ; la solution finale reste sous contrôle métier. |

### 2.3 Ce que le module ne fait pas (limites assumées)

- Il ne **comprend** pas le texte au sens humain du terme (pas d’inférence sémantique profonde).
- Il ne garantit pas que la solution proposée soit **correcte** pour le nouveau contexte : c’est une **piste**, pas une décision automatique.
- Il dépend de la **qualité et de la quantité** des tickets historiques possédant une **solution renseignée**.
- Il est **sensible au vocabulaire** : deux formulations très différentes pour le même problème peuvent obtenir un score faible.

Ces limites sont typiques des approches **bag-of-words / TF-IDF** et doivent être présentées clairement dans le rapport comme **choix de conception** (simplicité, coût, explicabilité).

---

## 3. Besoin métier et problématique

### 3.1 Contexte

Les services desks traitent souvent des **demandes récurrentes** : réinitialisation de mot de passe, accès à une application, problème de messagerie, etc. Sans outil d’aide, l’agent doit :

- parcourir manuellement l’historique ;
- retrouver un cas comparable ;
- réadapter la réponse.

Cela augmente le **temps de première réponse** et le **temps de résolution**, surtout en période de forte charge.

### 3.2 Besoin fonctionnel

1. **À la création d’un ticket** par un employé, le système doit pouvoir **évaluer** s’il existe un ancien ticket **suffisamment proche** pour suggérer une solution.
2. **Côté agent**, l’interface doit **afficher clairement** la suggestion (texte, ticket source, score) et permettre **validation / modification / rejet**.
3. **Côté données**, il faut une **source de vérité** pour la « solution » des anciens tickets : dans cette application, c’est le champ **`solution`** renseigné par l’agent lors du passage du ticket en statut **Résolu** (et les tickets **Résolus** ou **Fermés** avec solution alimentent le corpus).

### 3.3 Besoin non fonctionnel

- **Intégration locale** : calcul effectué **dans l’application**, sans envoi obligatoire des données vers un service cloud externe (bon point pour la confidentialité, sous réserve que l’hébergement reste conforme aux politiques internes).
- **Paramétrage** : seuil de similarité, filtrage par catégorie, taille du corpus — configurables via variables d’environnement.
- **Traçabilité** : actions agent (acceptation, modification, rejet) enregistrées dans l’historique du ticket.

---

## 4. Données : entrées, sorties et stockage

### 4.1 Entrées (input)

| Élément                     | Rôle                                                                                                                                    |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Texte du nouveau ticket** | Champs `titre` et `description` concaténés et normalisés pour la comparaison.                                                           |
| **Anciens tickets**         | Tickets en statut **Résolu** ou **Fermé**, avec champ **`solution` non vide**, exclus du ticket courant.                                |
| **Filtre optionnel**        | Même **catégorie** que le nouveau ticket (paramètre `AI_SIMILARITY_SAME_CATEGORY_ONLY`).                                                |
| **Limite de corpus**        | Nombre maximum de tickets historiques pris en compte (ex. 500), les plus récents en priorité (`date_resolution`, puis `date_creation`). |

### 4.2 Sorties (output)

Deux cas possibles :

1. **Solution suggérée** : identifiant du ticket source, **score de similarité**, texte de la **solution** du ticket source copié dans la suggestion ; statut de suggestion **`pending`** jusqu’à action de l’agent.
2. **Aucune solution trouvée** : si le corpus est vide, si le texte est vide, si le meilleur score est **strictement inférieur** au seuil configuré, ou si la fonctionnalité est désactivée — les champs IA sont remis à **`none`** côté statut et champs associés vidés.

### 4.3 Persistance en base de données

Les informations sont stockées sur la table **`tickets`** (champs ajoutés par migration SQL) :

| Champ                   | Description                                                                |
| ----------------------- | -------------------------------------------------------------------------- |
| `solution`              | Texte de résolution saisi par l’agent (corpus pour les prochains tickets). |
| `ai_source_ticket_id`   | Référence vers le ticket historique retenu comme « voisin ».               |
| `ai_similarity_score`   | Score numérique (similarité cosinus sur vecteurs TF-IDF).                  |
| `ai_suggested_solution` | Texte de la solution proposée (copie au moment du calcul).                 |
| `ai_suggestion_status`  | États : `none`, `pending`, `accepted`, `edited`, `rejected`.               |

---

## 5. Enchaînement des étapes (flux applicatif)

### 5.1 Création d’un ticket (employé)

1. L’employé soumet le formulaire (titre, description, catégorie, urgence, pièces jointes éventuelles).
2. Le ticket est **enregistré** en base (statut initial, priorité, SLA, etc.).
3. Après validation transactionnelle (`commit`), le service **`apply_ai_suggestion`** est appelé.
4. Le service interroge le **corpus** (tickets résolus/fermés avec solution), calcule la similarité, et met à jour les champs **`ai_*`** si le score dépasse le seuil ; sinon statut **`none`**.

### 5.2 Traitement par l’agent IT

1. L’agent ouvre la fiche ticket qui lui est assignée.
2. S’il existe une suggestion, la section **« Suggestion IA »** affiche le **texte proposé**, l’**identifiant public** (tronqué) du ticket source et le **score**.
3. L’agent peut :
   - **Valider** la suggestion : la solution est recopiée dans `solution`, statut **`accepted`**, un **commentaire** est ajouté pour visibilité côté demandeur ;
   - **Modifier** puis valider : `solution` mise à jour, statut **`edited`**, commentaire avec le texte modifié ;
   - **Rejeter** : statut **`rejected`**, pas de commentaire automatique.
4. Lors du passage en **Résolu**, l’agent doit renseigner le champ **solution** (obligatoire dans l’implémentation actuelle) : cela **alimente le corpus** pour les prochains tickets.

### 5.3 Clôture côté employé (rappel du processus existant)

Après résolution, l’employé peut clôturer avec satisfaction ; le ticket peut passer **Fermé**. Les tickets **Fermés** avec solution restent éligibles au corpus, ce qui élargit la base d’apprentissage « historique ».

---

## 6. Algorithme utilisé

### 6.1 Famille d’algorithmes

Le module repose sur la **vectorisation TF-IDF** (_Term Frequency — Inverse Document Frequency_) combinée à la **similarité cosinus** entre vecteurs.

### 6.2 Principe de la TF-IDF

- Chaque document (ici : le texte « titre + description » d’un ticket) est représenté par un **vecteur** dans un espace dont les dimensions correspondent aux **termes** (mots ou tokens) du corpus.
- La composante **TF** reflète la fréquence d’un terme dans le document.
- La composante **IDF** diminue le poids des termes **très fréquents** dans tout le corpus (ex. « le », « de », mots peu discriminants s’ils ne sont pas filtrés).
- Le résultat est une représentation numérique permettant de **comparer** deux textes par leurs profils de mots.

### 6.3 Principe de la similarité cosinus

Une fois les vecteurs TF-IDF calculés pour le **ticket courant** et pour chaque ticket du **corpus**, on mesure l’angle entre les vecteurs. Le **cosinus** de cet angle vaut **1** pour des directions identiques (textes très proches au sens bag-of-words) et se rapproche de **0** lorsque les textes partagent peu de termes pondérés.

Formule (rappel conceptuel) : pour deux vecteurs **u** et **v**,

\[
\cos(\theta) = \frac{u \cdot v}{\|u\| \|v\|}
\]

Dans l’implémentation, cette mesure est fournie par la fonction **`cosine_similarity`** de scikit-learn sur la matrice sparse produite par **`TfidfVectorizer`**.

### 6.4 Normalisation du texte (prétraitement)

Avant vectorisation, le texte subit une **normalisation légère** :

- passage en **minuscules** ;
- **compression des espaces** (séparation des tokens par espaces).

Il n’y a pas, dans la version actuelle, de **stemming** ni de **lemmatisation** du français, ni de liste de **stop-words** dédiée : c’est un compromis **simplicité / rapidité de mise en œuvre**. Le rapport peut mentionner ces pistes d’**amélioration** (ex. `stop_words='french'` ou prétraitement linguistique).

### 6.5 Sélection du « meilleur voisin »

1. Calcul des similarités entre le ticket courant et **tous** les documents du corpus (sous-ensemble limité en nombre).
2. Sélection de l’**indice** du score **maximum**.
3. Comparaison du score maximum au **seuil minimal** `AI_SIMILARITY_MIN_SCORE` (défaut **0,30** dans la configuration du projet).
4. Si le score est insuffisant, **aucune suggestion** n’est retournée.

### 6.6 Intérêt et limites de TF-IDF + cosinus (pour le jury PFE)

**Intérêts :**

- Implémentation **rapide**, bibliothèque **mature** (scikit-learn).
- **Explicable** : on peut montrer le ticket source et un score chiffré.
- **Sans entraînement supervisé** : pas besoin de jeu d’étiquettes autres que les solutions déjà saisies.

**Limites :**

- Sensible au **vocabulaire exact** ; synonymes ou paraphrases peuvent faire baisser le score.
- Ne capture pas les **relations** entre mots (ordre, négation complexe) aussi bien qu’un modèle sémantique moderne.
- Qualité du corpus = qualité des suggestions.

---

## 7. Technologies et outils utilisés

### 7.1 Langage et framework web

| Technologie          | Usage                                              |
| -------------------- | -------------------------------------------------- |
| **Python 3.10+**     | Langage principal du backend.                      |
| **Flask 3**          | Framework web (routes, sessions, rendu Jinja2).    |
| **Flask-SQLAlchemy** | ORM et accès à la base MySQL.                      |
| **Flask-Login**      | Authentification et rôles (employé, agent, admin). |
| **Flask-WTF / CSRF** | Protection des formulaires POST.                   |

### 7.2 Base de données et déploiement local

| Technologie                                          | Usage                                                                                       |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **MySQL 8** (souvent via **XAMPP** en développement) | Persistance des tickets, utilisateurs, statuts, champs IA.                                  |
| **PyMySQL**                                          | Driver MySQL pour SQLAlchemy (`mysql+pymysql://...`).                                       |
| **phpMyAdmin** (XAMPP)                               | Exécution du script **`sql/alter_tickets_ai_similarity.sql`** sans ligne de commande MySQL. |

### 7.3 Bibliothèque « intelligence artificielle » / calcul

| Technologie                                       | Usage                                   |
| ------------------------------------------------- | --------------------------------------- |
| **scikit-learn**                                  | `TfidfVectorizer`, `cosine_similarity`. |
| **NumPy** (dépendance transitive de scikit-learn) | Calculs matriciels sous-jacents.        |

### 7.4 Configuration et dépendances projet

| Fichier / outil             | Rôle                                                                                                                       |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **`requirements.txt`**      | Déclaration de `scikit-learn` et des paquets Flask.                                                                        |
| **`.env` / `.env.example`** | Variables `AI_SIMILARITY_ENABLED`, `AI_SIMILARITY_MIN_SCORE`, `AI_SIMILARITY_SAME_CATEGORY_ONLY`, `AI_MAX_CORPUS_TICKETS`. |
| **`app/config.py`**         | Lecture des variables d’environnement et exposition à l’application.                                                       |

### 7.5 Fichiers clés du code (références pour le rapport)

| Fichier                               | Rôle                                                                             |
| ------------------------------------- | -------------------------------------------------------------------------------- |
| `app/services/similarity.py`          | Logique TF-IDF, filtrage du corpus, application des suggestions.                 |
| `app/routes/employe.py`               | Appel après création de ticket.                                                  |
| `app/routes/agent.py`                 | Solution obligatoire à la résolution ; routes accept / edit / reject suggestion. |
| `templates/agent/ticket_detail.html`  | Interface utilisateur de la suggestion IA.                                       |
| `app/models.py`                       | Modèle de données `Ticket`, énumération `AISuggestionStatus`.                    |
| `sql/alter_tickets_ai_similarity.sql` | Migration des colonnes sur la table `tickets`.                                   |

---

## 8. Paramètres configurables (détail pour le rapport)

| Variable                           | Signification                                                              | Valeur par défaut (projet) |
| ---------------------------------- | -------------------------------------------------------------------------- | -------------------------- |
| `AI_SIMILARITY_ENABLED`            | Active ou désactive tout le calcul de suggestion.                          | `true`                     |
| `AI_SIMILARITY_MIN_SCORE`          | Seuil minimal sur le score cosinus pour accepter une suggestion.           | `0.30`                     |
| `AI_SIMILARITY_SAME_CATEGORY_ONLY` | Si `true`, le corpus ne contient que les tickets de la **même catégorie**. | `true`                     |
| `AI_MAX_CORPUS_TICKETS`            | Nombre maximum de tickets historiques chargés pour le calcul.              | `500`                      |

Ces paramètres permettent d’**ajuster** le comportement lors de la démonstration ou des tests (baisser le seuil pour voir plus de suggestions, ou désactiver l’IA pour comparer).

---

## 9. Considérations éthiques, RGPD et sécurité (paragraphe type rapport)

- Les données traitées sont celles **déjà collectées** par le service desk (titres, descriptions, solutions internes). Le module **ne crée pas** de nouvelle catégorie de données personnelle ; il **réorganise** l’information existante pour l’affichage à l’agent.
- Le traitement peut rester **on-premise** ou sur un serveur contrôlé par l’organisation, sans appel à une API externe d’IA générative, ce qui simplifie la **maîtrise des flux** de données.
- La **décision finale** appartient à l’**agent humain** ; la suggestion doit être présentée comme **aide**, avec possibilité de rejet et de modification — point important pour la **responsabilité** et la **qualité du service**.
- Le rapport peut mentionner la **traçabilité** via l’historique des actions sur le ticket (création, changement de statut, actions sur la suggestion IA).

---

## 10. Perspectives d’évolution (pour conclure le chapitre « IA »)

1. **Stop-words français** et éventuellement **n-grammes** (`ngram_range`) pour mieux capturer des expressions multi-mots.
2. **Embeddings** (Sentence-BERT, modèles multilingues) pour une similarité **sémantique** plus robuste aux paraphrases — au prix de complexité, taille des modèles et temps de calcul.
3. **Feedback** : enregistrer si la suggestion a été utile pour **ré-ordonner** ou **pondérer** les tickets sources.
4. **Interface employé** : afficher une version « informative » (sans divulguer de données confidentielles d’autres tickets) si le métier le valide.

---

## 11. Synthèse en une phrase (résumé exécutif)

Le module implémenté est un **système de recommandation de solutions** basé sur la **similarité TF-IDF et cosinus** entre le texte d’un nouveau ticket et l’historique des tickets **résolus ou fermés** disposant d’une **solution documentée**, avec **paramètres configurables** et **validation obligatoire par l’agent IT** avant de considérer la suggestion comme partie intégrante du traitement.

---

_Fin du document — à copier-coller ou importer dans Word / LibreOffice pour mise en forme du rapport PFE._
