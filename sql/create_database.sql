-- Script optionnel : création de la base vide (à exécuter une fois dans MySQL)
-- Adapter le nom de la base si besoin (doit correspondre à DATABASE_URL dans .env)

CREATE DATABASE IF NOT EXISTS bh_service_desk
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Puis lancer depuis le projet : python init_db.py
