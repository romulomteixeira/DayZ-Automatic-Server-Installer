import os
import subprocess
import json
import time
from workshop import get_mod_details

CONFIG = json.load(open("config.json"))

STEAMCMD = CONFIG["steamcmd"]
MODS_FILE = CONFIG["mods_file"]
SERVER_MODS = CONFIG["server_path"] + "/mods"

def load_mods():

    with open(MODS_FILE) as f:
        return [x.strip() for x in f if x.strip()]

def download_mod(mod_id):

    cmd = [
        STEAMCMD,
        "+login", CONFIG["steam_user"],
        "+workshop_download_item", "221100", mod_id,
        "validate",
        "+quit"
    ]

    subprocess.run(cmd)

def install_mod(mod_id):

    src = f"../steamcmd/steamapps/workshop/content/221100/{mod_id}"
    dst = f"{SERVER_MODS}/@{mod_id}"

    subprocess.run(["xcopy", src, dst, "/E", "/I", "/Y"], shell=True)

def install_all():

    mods = load_mods()
    details = get_mod_details(mods)

    for mod in details:

        print("Installing:", mod["name"])

        download_mod(mod["id"])
        install_mod(mod["id"])

        for dep in mod["dependencies"]:
            download_mod(dep)
            install_mod(dep)

def scheduled_restart(interval_minutes):

    while True:

        time.sleep(interval_minutes * 60)

        print("Restarting server...")

        subprocess.run(["taskkill","/f","/im","DayZServer_x64.exe"])

        subprocess.Popen(["start_server.bat"], shell=True)

def install_map(map_key):

    with open("maps.json") as f:
        maps = json.load(f)

    if map_key not in maps:
        print("Mapa não encontrado")
        return

    map_id = maps[map_key]["workshop_id"]

    download_mod(map_id)
    install_mod(map_id)

    print("Mapa instalado:", maps[map_key]["name"])