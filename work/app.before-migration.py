from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "fabrica_tiktok.db"

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


def connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def setup_database() -> None:
    with connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                outfit TEXT,
                color TEXT,
                product TEXT,
                status TEXT NOT NULL DEFAULT 'briefing',
                generator TEXT NOT NULL DEFAULT 'flow',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


@app.get("/")
def visual_flow():
    """The visual canvas is the first screen of the local application."""
    return send_from_directory(ROOT / "frontend" / "dist", "index.html")


@app.get("/assets/<path:filename>")
def frontend_assets(filename):
    return send_from_directory(ROOT / "frontend" / "dist" / "assets", filename)


@app.get("/favicon.svg")
def favicon():
    return send_from_directory(ROOT / "frontend" / "dist", "favicon.svg")


@app.get("/creator")
def creator():
    return send_from_directory(ROOT / "outputs", "fabrica-tiktok.html")


@app.get("/api/campaigns")
def list_campaigns():
    with connection() as db:
        records = db.execute(
            "SELECT * FROM campaigns ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return jsonify([dict(row) for row in records])


@app.post("/api/campaigns")
def create_campaign():
    payload: dict[str, Any] = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    model_name = str(payload.get("model_name", "")).strip()
    if not name or not model_name:
        return jsonify({"error": "Nome da campanha e modelo são obrigatórios."}), 400

    fields = {
        "outfit": str(payload.get("outfit", "")).strip(),
        "color": str(payload.get("color", "")).strip(),
        "product": str(payload.get("product", "")).strip(),
        "generator": str(payload.get("generator", "flow")).strip().lower(),
    }
    if fields["generator"] not in {"flow", "grok"}:
        return jsonify({"error": "Gerador deve ser flow ou grok."}), 400

    with connection() as db:
        cursor = db.execute(
            """
            INSERT INTO campaigns (name, model_name, outfit, color, product, generator)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, model_name, fields["outfit"], fields["color"], fields["product"], fields["generator"]),
        )
        campaign_id = cursor.lastrowid
        row = db.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    return jsonify(dict(row)), 201


@app.patch("/api/campaigns/<int:campaign_id>")
def update_campaign(campaign_id: int):
    payload: dict[str, Any] = request.get_json(silent=True) or {}
    status = str(payload.get("status", "")).strip()
    allowed = {"briefing", "image_generated", "image_approved", "video_generated", "ready_to_publish", "published"}
    if status not in allowed:
        return jsonify({"error": "Status inválido."}), 400

    with connection() as db:
        result = db.execute(
            "UPDATE campaigns SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, campaign_id),
        )
        if result.rowcount == 0:
            return jsonify({"error": "Campanha não encontrada."}), 404
        row = db.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    return jsonify(dict(row))


if __name__ == "__main__":
    setup_database()
    app.run(host="127.0.0.1", port=5050, debug=True)
