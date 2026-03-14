from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
SERVERS_ROOT = Path(CONFIG.get("servers_root", "servers"))
STEAMCMD_APP_ID = str(CONFIG.get("dayz_server_app_id", "223350"))
SERVER_BINARY_NAME = CONFIG.get("server_binary_name", "DayZServer_x64.exe")
SERVER_CFG_NAME = CONFIG.get("server_cfg_name", "serverDZ.cfg")
DEFAULT_INSTALL_BACKUP_DIR = Path(CONFIG.get("default_install_backup_dir", "servers/.default_install_backup"))

SERVER_PROCESSES: Dict[str, subprocess.Popen] = {}
BACKUP_LOCK = threading.Lock()


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


def _sanitize_server_folder(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    return cleaned.strip("._") or "server"


def _steam_login_parts() -> List[str]:
    user, pwd = _resolve_steam_credentials()
    if user and pwd:
        return ["+login", user, pwd]
    return ["+login", "anonymous"]


def _resolve_steam_credentials() -> tuple[str, str]:
    user = str(CONFIG.get("steam_user") or CONFIG.get("steam_username") or "").strip()
    pwd = str(CONFIG.get("steam_password") or "").strip()

    steam_cfg_path = Path(CONFIG.get("steam_config_path", "config/steam.json"))
    if steam_cfg_path.exists():
        try:
            with open(steam_cfg_path, "r", encoding="utf-8") as f:
                steam_cfg = json.load(f)
            user = str(steam_cfg.get("steam_username") or user).strip()
            pwd = str(steam_cfg.get("steam_password") or pwd).strip()
        except (OSError, json.JSONDecodeError):
            pass

    return user, pwd


def _steamcmd_executable() -> str:
    return CONFIG.get("steamcmd_path", "steamcmd")


def _install_server_files(server_path: Path) -> None:
    server_path.mkdir(parents=True, exist_ok=True)
    cmd = [
        _steamcmd_executable(),
        *_steam_login_parts(),
        "+force_install_dir",
        str(server_path.resolve()),
        "+app_update",
        STEAMCMD_APP_ID,
        "validate",
        "+quit",
    ]
    subprocess.run(cmd, check=True)


def _server_install_valid(path: Path) -> bool:
    return (path / SERVER_BINARY_NAME).exists()


def _copy_default_install(server_path: Path) -> None:
    if server_path.exists():
        shutil.rmtree(server_path)
    shutil.copytree(DEFAULT_INSTALL_BACKUP_DIR, server_path)


def _ensure_backup_default_install() -> bool:
    with BACKUP_LOCK:
        if _server_install_valid(DEFAULT_INSTALL_BACKUP_DIR):
            return False

        if DEFAULT_INSTALL_BACKUP_DIR.exists():
            shutil.rmtree(DEFAULT_INSTALL_BACKUP_DIR, ignore_errors=True)

        _install_server_files(DEFAULT_INSTALL_BACKUP_DIR)
        return True


def _prepare_server_install(server_path: Path) -> Dict[str, Any]:
    created_backup = _ensure_backup_default_install()
    _copy_default_install(server_path)
    return {
        "install_source": "default_backup",
        "default_backup_created": created_backup,
    }


def _parse_server_cfg(cfg_path: Path) -> Dict[str, str]:
    if not cfg_path.exists():
        return {}

    params: Dict[str, str] = {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("//") or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().rstrip(";")
            if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                value = value[1:-1]
            params[key] = value
    return params


def _serialize_cfg_value(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text.lower() in {"true", "false"}:
        return "1" if text.lower() == "true" else "0"
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", text):
        return text
    escaped = text.replace('"', '\\"')
    return f'"{escaped}"'


def _write_server_cfg(cfg_path: Path, params: Dict[str, str]) -> None:
    ordered = sorted(params.items(), key=lambda item: item[0].lower())
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write("// Arquivo gerado automaticamente pelo painel\n")
        for key, value in ordered:
            f.write(f"{key} = {_serialize_cfg_value(value)};\n")


def _default_server_cfg(name: str, port: int) -> Dict[str, str]:
    return {
        "hostname": name,
        "password": "",
        "passwordAdmin": "",
        "maxPlayers": "60",
        "verifySignatures": "2",
        "disableVoN": "0",
        "vonCodecQuality": "20",
        "serverTimeAcceleration": "1",
        "serverNightTimeAcceleration": "1",
        "serverTimePersistent": "1",
        "guaranteedUpdates": "1",
        "steamPort": str(port + 100),
    }


def _find_server(servers: List[Dict], server_id: str) -> Optional[Dict]:
    return next((s for s in servers if s["id"] == server_id), None)


def _server_path(server: Dict) -> Path:
    return Path(server["path"])


def _build_mod_arg(server: Dict) -> str:
    mods_catalog = {m["id"]: m for m in list_mods()}
    folders = []
    for mod_id in server.get("mods", []):
        mod_data = mods_catalog.get(mod_id)
        if mod_data and mod_data.get("folder"):
            folders.append(mod_data["folder"])
    if not folders:
        return ""
    return "-mod=" + ";".join(folders)


def _start_server_process(server: Dict) -> subprocess.Popen:
    server_dir = _server_path(server)
    exe = server_dir / SERVER_BINARY_NAME
    if not exe.exists():
        raise FileNotFoundError(f"Executável não encontrado: {exe}")

    cfg_path = server_dir / SERVER_CFG_NAME
    if not cfg_path.exists():
        _write_server_cfg(cfg_path, _default_server_cfg(server["name"], int(server["port"])))

    cmd = [str(exe), f"-config={SERVER_CFG_NAME}"]
    mod_arg = _build_mod_arg(server)
    if mod_arg:
        cmd.append(mod_arg)
    return subprocess.Popen(cmd, cwd=server_dir)


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
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return jsonify({"error": "nome do servidor é obrigatório"}), 400

    try:
        port = int(body.get("port"))
    except (TypeError, ValueError):
        return jsonify({"error": "porta inválida"}), 400

    if port <= 0 or port > 65535:
        return jsonify({"error": "porta deve estar entre 1 e 65535"}), 400

    folder = _sanitize_server_folder(name)
    server_dir = SERVERS_ROOT / folder

    servers = list_servers()
    if any(s.get("name", "").strip().lower() == name.lower() for s in servers):
        return jsonify({"error": "já existe um servidor com esse nome"}), 409

    if any(int(s.get("port", 0)) == port for s in servers):
        return jsonify({"error": "já existe um servidor usando essa porta"}), 409

    if any(Path(s.get("path", "")) == server_dir for s in servers):
        return jsonify({"error": "pasta do servidor já está em uso por outro registro"}), 409

    try:
        install_meta = _prepare_server_install(server_dir)
    except FileNotFoundError as exc:
        return jsonify({"error": f"steamcmd não encontrado: {exc}"}), 500
    except subprocess.CalledProcessError as exc:
        return jsonify({"error": f"falha ao instalar arquivos base do servidor (steamcmd exit code {exc.returncode})"}), 500
    except Exception as exc:
        return jsonify({"error": f"falha ao preparar instalação do servidor: {exc}"}), 500

    cfg_path = server_dir / SERVER_CFG_NAME
    try:
        if not cfg_path.exists():
            _write_server_cfg(cfg_path, _default_server_cfg(name, port))
    except Exception as exc:
        return jsonify({"error": f"falha ao criar serverDZ.cfg: {exc}"}), 500

    server = {
        "id": str(uuid.uuid4()),
        "name": name,
        "port": port,
        "status": "stopped",
        "path": str(server_dir),
        "folder": folder,
        "mods": [],
        "config": _parse_server_cfg(cfg_path),
    }
    servers.append(server)
    save_servers(servers)
    return jsonify({**server, **install_meta}), 201


@app.delete("/api/servers/<server_id>")
def delete_server(server_id: str):
    servers = list_servers()
    target = _find_server(servers, server_id)

    process = SERVER_PROCESSES.pop(server_id, None)
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()

    if target:
        shutil.rmtree(_server_path(target), ignore_errors=True)

    servers = [s for s in servers if s["id"] != server_id]
    save_servers(servers)
    recompute_mod_usage()
    return jsonify({"deleted": server_id})


@app.post("/api/servers/<server_id>/start")
def start_server(server_id: str):
    servers = list_servers()
    target = _find_server(servers, server_id)
    if not target:
        return jsonify({"error": "servidor não encontrado"}), 404

    running = SERVER_PROCESSES.get(server_id)
    if running and running.poll() is None:
        target["status"] = "running"
        save_servers(servers)
        return jsonify({"status": "running"})

    process = _start_server_process(target)
    SERVER_PROCESSES[server_id] = process
    target["status"] = "running"
    save_servers(servers)
    return jsonify({"status": "running"})


@app.post("/api/servers/<server_id>/stop")
def stop_server(server_id: str):
    servers = list_servers()
    target = _find_server(servers, server_id)
    if not target:
        return jsonify({"error": "servidor não encontrado"}), 404

    process = SERVER_PROCESSES.pop(server_id, None)
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()

    target["status"] = "stopped"
    save_servers(servers)
    return jsonify({"status": "stopped"})


@app.put("/api/servers/<server_id>/config")
def update_server_config(server_id: str):
    body = request.get_json(force=True)
    servers = list_servers()
    updated = None
    for s in servers:
        if s["id"] == server_id:
            current_cfg = s.get("config") or {}
            updates = body.get("set", body)
            removals = body.get("delete", [])

            if isinstance(updates, dict):
                for key, value in updates.items():
                    current_cfg[str(key)] = str(value)

            if isinstance(removals, list):
                for key in removals:
                    current_cfg.pop(str(key), None)

            s["config"] = current_cfg
            _write_server_cfg(_server_path(s) / SERVER_CFG_NAME, current_cfg)
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
