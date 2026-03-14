from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import psutil
from flask import Flask, jsonify, request
from flask_cors import CORS

from mod_installer import DayZModInstaller, load_manager_config
from rcon_monitor import RconPlayerMonitor

app = Flask(__name__)
CORS(app)

CONFIG = load_manager_config()
installer = DayZModInstaller(CONFIG)
rcon = RconPlayerMonitor(CONFIG["rcon_host"], int(CONFIG["rcon_port"]), CONFIG["rcon_password"])

DATA_DIR = Path(CONFIG.get("data_dir", "data/manager"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SERVERS_FILE = DATA_DIR / "servers.json"
MODS_FILE = DATA_DIR / "installed_mods.json"
METRICS_FILE = DATA_DIR / "metrics.json"
MAPS_FILE = Path(CONFIG.get("maps_config_path", "manager/maps.json"))
DEFAULT_MODS_FILE = Path(CONFIG.get("mods_config_path", "config/mods.json"))


def read_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def seed_files() -> None:
    if not SERVERS_FILE.exists():
        write_json(SERVERS_FILE, {"servers": []})
    if not MODS_FILE.exists():
        write_json(MODS_FILE, {"mods": []})
    if not METRICS_FILE.exists():
        write_json(METRICS_FILE, {"points": []})


seed_files()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_players() -> List[str]:
    try:
        return rcon.get_players()
    except Exception:
        return []


def capture_metric() -> Dict:
    point = {
        "ts": now_iso(),
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "players": len(safe_players()),
    }
    payload = read_json(METRICS_FILE, {"points": []})
    payload["points"].append(point)
    payload["points"] = payload["points"][-50000:]
    write_json(METRICS_FILE, payload)
    return point


def metric_collector() -> None:
    interval = int(CONFIG.get("metrics_interval_seconds", 300))
    while True:
        try:
            capture_metric()
        except Exception:
            pass
        time.sleep(interval)


threading.Thread(target=metric_collector, daemon=True).start()


def _range_to_start(range_key: str) -> datetime:
    now = datetime.now(timezone.utc)
    mapping = {
        "1d": now - timedelta(days=1),
        "7d": now - timedelta(days=7),
        "15d": now - timedelta(days=15),
        "1m": now - timedelta(days=30),
        "3m": now - timedelta(days=90),
        "6m": now - timedelta(days=180),
        "1y": now - timedelta(days=365),
    }
    return mapping.get(range_key, mapping["7d"])


def default_mods() -> List[str]:
    payload = read_json(DEFAULT_MODS_FILE, {"mods": []})
    return [str(m) for m in payload.get("mods", [])]


def chiemsee_mod_id() -> str:
    maps = read_json(MAPS_FILE, {})
    return str(maps["chiemsee"]["workshop_id"])


def list_servers() -> List[Dict]:
    return read_json(SERVERS_FILE, {"servers": []})["servers"]


def save_servers(servers: List[Dict]) -> None:
    write_json(SERVERS_FILE, {"servers": servers})


def list_mods() -> List[Dict]:
    return read_json(MODS_FILE, {"mods": []})["mods"]


def save_mods(mods: List[Dict]) -> None:
    write_json(MODS_FILE, {"mods": mods})


def recompute_mod_usage() -> None:
    servers = list_servers()
    used_ids = {m for s in servers for m in s.get("mods", [])}
    mods = list_mods()
    for mod in mods:
        mod["in_use"] = mod["id"] in used_ids
    save_mods(mods)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/home")
def home():
    players = safe_players()
    return jsonify(
        {
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "players_online": len(players),
            "players": players,
            "servers": list_servers(),
        }
    )


@app.get("/api/metrics")
def metrics():
    range_key = request.args.get("range", "7d")
    start_q = request.args.get("start")
    end_q = request.args.get("end")

    end_dt = datetime.now(timezone.utc) if not end_q else datetime.fromisoformat(end_q)
    start_dt = _range_to_start(range_key) if not start_q else datetime.fromisoformat(start_q)

    points = read_json(METRICS_FILE, {"points": []})["points"]
    filtered = []
    for p in points:
        ts = datetime.fromisoformat(p["ts"])
        if start_dt <= ts <= end_dt:
            filtered.append(p)
    return jsonify({"range": range_key, "start": start_dt.isoformat(), "end": end_dt.isoformat(), "points": filtered})


@app.post("/api/mods/sync")
def sync_mods():
    body = request.get_json(silent=True) or {}
    mod_ids = [str(m) for m in (body.get("mods") or default_mods())]
    if body.get("include_chiemsee"):
        mod_ids.append(chiemsee_mod_id())

    result = installer.sync_mods(mod_ids)
    current_mods = {m["id"]: m for m in list_mods()}
    for item, folder in zip(result["resolved_mods"], result["mod_folders"]):
        current_mods[item["id"]] = {
            "id": item["id"],
            "title": item["title"],
            "folder": folder,
            "in_use": False,
        }
    save_mods(list(current_mods.values()))
    recompute_mod_usage()
    return jsonify(result)


@app.post("/api/maps/chiemsee/install")
def install_chiemsee():
    return jsonify(installer.sync_mods([chiemsee_mod_id()]))


@app.get("/api/workshop/search")
def search_workshop():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    return jsonify({"results": installer.search_workshop(q)})


@app.get("/api/servers")
def get_servers():
    return jsonify({"servers": list_servers()})


@app.post("/api/servers")
def create_server():
    body = request.get_json(force=True)
    server = {
        "id": str(uuid.uuid4()),
        "name": body["name"],
        "port": int(body["port"]),
        "status": "stopped",
        "mods": [],
        "config": {
            "map": body.get("map", "chernarusplus"),
            "max_players": int(body.get("max_players", 60)),
            "time_multiplier": float(body.get("time_multiplier", 1.0)),
            "game_speed": float(body.get("game_speed", 1.0)),
        },
    }
    servers = list_servers()
    servers.append(server)
    save_servers(servers)
    return jsonify(server), 201


@app.delete("/api/servers/<server_id>")
def delete_server(server_id: str):
    servers = [s for s in list_servers() if s["id"] != server_id]
    save_servers(servers)
    recompute_mod_usage()
    return jsonify({"deleted": server_id})


@app.post("/api/servers/<server_id>/start")
def start_server(server_id: str):
    servers = list_servers()
    for s in servers:
        if s["id"] == server_id:
            s["status"] = "running"
    save_servers(servers)
    return jsonify({"status": "running"})


@app.post("/api/servers/<server_id>/stop")
def stop_server(server_id: str):
    servers = list_servers()
    for s in servers:
        if s["id"] == server_id:
            s["status"] = "stopped"
    save_servers(servers)
    return jsonify({"status": "stopped"})


@app.put("/api/servers/<server_id>/config")
def update_server_config(server_id: str):
    body = request.get_json(force=True)
    servers = list_servers()
    updated = None
    for s in servers:
        if s["id"] == server_id:
            s["config"].update(body)
            updated = s
    save_servers(servers)
    return jsonify(updated or {})


@app.post("/api/servers/<server_id>/mods/install")
def install_server_mod(server_id: str):
    body = request.get_json(force=True)
    mod_id = str(body["mod_id"])
    result = installer.sync_mods([mod_id])

    mods_map = {m["id"]: m for m in list_mods()}
    for item, folder in zip(result["resolved_mods"], result["mod_folders"]):
        mods_map[item["id"]] = {"id": item["id"], "title": item["title"], "folder": folder, "in_use": True}

    servers = list_servers()
    for s in servers:
        if s["id"] == server_id:
            for item in result["resolved_mods"]:
                if item["id"] not in s["mods"]:
                    s["mods"].append(item["id"])

    save_servers(servers)
    save_mods(list(mods_map.values()))
    recompute_mod_usage()
    return jsonify(result)


@app.post("/api/servers/<server_id>/mods/uninstall")
def uninstall_server_mod(server_id: str):
    body = request.get_json(force=True)
    mod_id = str(body["mod_id"])

    servers = list_servers()
    for s in servers:
        if s["id"] == server_id:
            s["mods"] = [m for m in s.get("mods", []) if m != mod_id]
    save_servers(servers)

    recompute_mod_usage()
    return jsonify({"server_id": server_id, "mod_id": mod_id, "unlinked": True})


@app.get("/api/mods")
def get_mods():
    filter_q = request.args.get("filter", "all")
    mods = list_mods()
    if filter_q == "used":
        mods = [m for m in mods if m.get("in_use")]
    elif filter_q == "unused":
        mods = [m for m in mods if not m.get("in_use")]
    return jsonify({"mods": mods})


@app.delete("/api/mods/<mod_id>")
def delete_mod(mod_id: str):
    mods = list_mods()
    target = next((m for m in mods if m["id"] == mod_id), None)
    if target and not target.get("in_use"):
        installer.uninstall_mod_folder(target["folder"])
        mods = [m for m in mods if m["id"] != mod_id]
        save_mods(mods)
        return jsonify({"deleted": mod_id})
    return jsonify({"error": "mod em uso por servidor"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
