from __future__ import annotations

import os
import uuid
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


def allowed_extension(filename: str, allowed: set[str]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def save_upload(file: FileStorage, upload_root: str, ticket_id: int, allowed: set[str]) -> tuple[str, str, int] | None:
    if not file or not file.filename:
        return None
    if not allowed_extension(file.filename, allowed):
        return None
    raw = secure_filename(file.filename)
    ext = raw.rsplit(".", 1)[-1].lower() if "." in raw else ""
    stored = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    dest_dir = Path(upload_root) / "tickets" / str(ticket_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / stored
    file.save(str(path))
    size = path.stat().st_size
    return raw, stored, size
