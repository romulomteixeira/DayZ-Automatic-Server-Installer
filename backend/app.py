from __future__ import annotations

import json
import os
from pathlib import Path

import psutil
from flask import Flask, jsonify, request
from flask_cors import CORS

from mod_installer import DayZModInstaller, load_manager_config
from rcon_monitor import RconPlayerMonitor

app = Flask(__name__)
CORS(app)

CONFIG = load_manager_config()
MODS_CONFIG_PATH = Path(CONFIG.get("mods_config_path", "config/mods.json"))
MAPS_CONFIG_PATH = Path(CONFIG.get("maps_config_path", "manager/maps.json"))

installer = DayZModInstaller(CONFIG)
rcon = RconPlayerMonitor(
    host=CONFIG["rcon_host"],
    port=int(CONFIG["rcon_port"]),
    password=CONFIG["rcon_password"],
)


def read_default_mods() -> list[str]:
    with open(MODS_CONFIG_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return [str(m) for m in payload.get("mods", [])]


def get_chiemsee_mod_id() -> str:
    with open(MAPS_CONFIG_PATH, "r", encoding="utf-8") as f:
        maps = json.load(f)
    return str(maps["chiemsee"]["workshop_id"])


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/status")
def status():
    players = []
    rcon_error = None
    try:
        players = rcon.get_players()
    except Exception as exc:  # noqa: BLE001
        rcon_error = str(exc)

    return jsonify(
        {
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "players": players,
            "rcon_error": rcon_error,
            "server_mods_dir": CONFIG["server_mods_dir"],
            "steamcmd": CONFIG.get("steamcmd_path", "steamcmd"),
        }
    )


@app.post("/api/mods/sync")
def sync_mods():
    body = request.get_json(silent=True) or {}
    mod_ids = body.get("mods") or read_default_mods()
    include_chiemsee = bool(body.get("include_chiemsee", False))

    if include_chiemsee:
        mod_ids = [*mod_ids, get_chiemsee_mod_id()]

    result = installer.sync_mods([str(mod) for mod in mod_ids])
    return jsonify(result)


@app.post("/api/maps/chiemsee/install")
def install_chiemsee():
    mod_id = get_chiemsee_mod_id()
    result = installer.sync_mods([mod_id])
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
