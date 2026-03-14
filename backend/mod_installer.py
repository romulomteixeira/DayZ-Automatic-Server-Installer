from __future__ import annotations

import json
import os
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


@dataclass
class ModInfo:
    mod_id: str
    title: str
    dependencies: List[str]


class DayZModInstaller:
    """Instala mods de forma inteligente, resolve dependências e gera launch args."""

    def __init__(self, config: Dict):
        self.config = config
        self.server_mods_dir = Path(config["server_mods_dir"])
        self.workshop_content_dir = Path(config["workshop_content_dir"])
        self.server_mods_dir.mkdir(parents=True, exist_ok=True)

    def _steam_login_parts(self) -> List[str]:
        user = self.config.get("steam_user")
        pwd = self.config.get("steam_password")
        if user and pwd:
            return ["+login", user, pwd]
        return ["+login", "anonymous"]

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

        mod_arg = "-mod=" + ";".join(installed_folders)
        return {
            "resolved_mods": [
                {"id": m.mod_id, "title": m.title, "dependencies": m.dependencies}
                for m in mod_infos
            ],
            "mod_arg": mod_arg,
            "mod_folders": installed_folders,
        }


def load_manager_config(path: str = "config/manager.json") -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
