from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

import requests

STEAM_PUBLISHED_FILE_DETAILS_URL = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)
WORKSHOP_SEARCH_URL = "https://steamcommunity.com/workshop/browse/"


@dataclass
class ModInfo:
    mod_id: str
    title: str
    dependencies: List[str]


class DayZModInstaller:
    def __init__(self, config: Dict):
        self.config = config
        self.server_mods_dir = Path(config["server_mods_dir"])
        self.workshop_content_dir = Path(config["workshop_content_dir"])
        self.server_mods_dir.mkdir(parents=True, exist_ok=True)

    def _steam_login_parts(self) -> List[str]:
        user, pwd = self._resolve_steam_credentials()
        if user and pwd:
            return ["+login", user, pwd]
        return ["+login", "anonymous"]

    def _resolve_steam_credentials(self) -> tuple[str, str]:
        user = str(self.config.get("steam_user") or self.config.get("steam_username") or "").strip()
        pwd = str(self.config.get("steam_password") or "").strip()

        steam_cfg_path = Path(self.config.get("steam_config_path", "config/steam.json"))
        if steam_cfg_path.exists():
            try:
                with open(steam_cfg_path, "r", encoding="utf-8") as f:
                    steam_cfg = json.load(f)
                user = str(steam_cfg.get("steam_username") or user).strip()
                pwd = str(steam_cfg.get("steam_password") or pwd).strip()
            except (OSError, json.JSONDecodeError):
                pass

        return user, pwd

    def _steamcmd_executable(self) -> str:
        return self.config.get("steamcmd_path", "steamcmd")

    def _run_steamcmd_download(self, mod_id: str) -> None:
        cmd = [
            self._steamcmd_executable(),
            *self._steam_login_parts(),
            "+workshop_download_item",
            "221100",
            str(mod_id),
            "validate",
            "+quit",
        ]
        subprocess.run(cmd, check=True)

    def _fetch_details(self, mod_ids: List[str]) -> Dict[str, ModInfo]:
        payload = {"itemcount": len(mod_ids)}
        for i, mod_id in enumerate(mod_ids):
            payload[f"publishedfileids[{i}]"] = str(mod_id)

        response = requests.post(STEAM_PUBLISHED_FILE_DETAILS_URL, data=payload, timeout=30)
        response.raise_for_status()

        details: Dict[str, ModInfo] = {}
        for item in response.json()["response"]["publishedfiledetails"]:
            item_id = str(item["publishedfileid"])
            children = [str(c["publishedfileid"]) for c in item.get("children", [])]
            details[item_id] = ModInfo(
                mod_id=item_id,
                title=item.get("title", f"mod_{item_id}"),
                dependencies=children,
            )
        return details

    def resolve_dependencies(self, root_mod_ids: List[str]) -> List[ModInfo]:
        resolved: Dict[str, ModInfo] = {}
        visited: Set[str] = set()

        def walk(mod_id: str) -> None:
            if mod_id in visited:
                return
            visited.add(mod_id)
            details = self._fetch_details([mod_id])
            if mod_id not in details:
                return
            mod_info = details[mod_id]
            for dep in mod_info.dependencies:
                walk(dep)
            resolved[mod_id] = mod_info

        for mod_id in root_mod_ids:
            walk(str(mod_id))
        return list(resolved.values())

    @staticmethod
    def _slugify_title(title: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "", title)
        return cleaned or "Mod"

    def _discover_mod_folder_name(self, mod_id: str, title: str) -> str:
        source = self.workshop_content_dir / mod_id
        if not source.exists():
            return f"@{mod_id}"

        preferred = [p.name for p in source.iterdir() if p.is_dir() and p.name.startswith("@")]
        if preferred:
            return preferred[0]
        return f"@{self._slugify_title(title)}"

    def _install_downloaded_mod(self, mod_info: ModInfo) -> str:
        source = self.workshop_content_dir / mod_info.mod_id
        if not source.exists():
            raise FileNotFoundError(f"Workshop content ausente para mod {mod_info.mod_id}: {source}")

        target_folder = self._discover_mod_folder_name(mod_info.mod_id, mod_info.title)
        target = self.server_mods_dir / target_folder
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        return target_folder

    def sync_mods(self, mod_ids: List[str]) -> Dict:
        mod_infos = self.resolve_dependencies(mod_ids)
        installed_folders: List[str] = []

        for mod in mod_infos:
            self._run_steamcmd_download(mod.mod_id)
            folder = self._install_downloaded_mod(mod)
            installed_folders.append(folder)

        return {
            "resolved_mods": [
                {"id": m.mod_id, "title": m.title, "dependencies": m.dependencies}
                for m in mod_infos
            ],
            "mod_arg": "-mod=" + ";".join(installed_folders),
            "mod_folders": installed_folders,
        }

    def uninstall_mod_folder(self, folder_name: str) -> None:
        target = self.server_mods_dir / folder_name
        if target.exists() and target.is_dir():
            shutil.rmtree(target)

    def search_workshop(self, query: str, limit: int = 10) -> List[Dict]:
        params = {"appid": 221100, "searchtext": query, "browsesort": "trend", "section": "readytouseitems"}
        response = requests.get(WORKSHOP_SEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        html = response.text

        results: List[Dict] = []
        seen: Set[str] = set()
        for mod_id in re.findall(r'"publishedfileid"\s*:\s*"(\d+)"', html):
            if mod_id in seen:
                continue
            seen.add(mod_id)
            try:
                details = self._fetch_details([mod_id]).get(mod_id)
                if details:
                    results.append({"id": details.mod_id, "title": details.title})
            except Exception:
                continue
            if len(results) >= limit:
                break
        return results


def load_manager_config(path: str = "config/manager.json") -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
