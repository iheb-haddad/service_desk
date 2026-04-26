-- Migration manuelle MySQL pour enrichir les tickets avec la solution
-- et les métadonnées de suggestion IA par similarité textuelle.

ALTER TABLE tickets
  ADD COLUMN solution TEXT NULL AFTER escalade_declenchee,
  ADD COLUMN ai_source_ticket_id INT NULL AFTER solution,
  ADD COLUMN ai_similarity_score FLOAT NULL AFTER ai_source_ticket_id,
  ADD COLUMN ai_suggested_solution TEXT NULL AFTER ai_similarity_score,
  ADD COLUMN ai_suggestion_status ENUM('NONE','PENDING','ACCEPTED','EDITED','REJECTED') NOT NULL DEFAULT 'NONE' AFTER ai_suggested_solution,
  ADD CONSTRAINT fk_tickets_ai_source_ticket
    FOREIGN KEY (ai_source_ticket_id) REFERENCES tickets(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE;
