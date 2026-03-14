import subprocess
import json
from steam_auth import load_steam_credentials

STEAMCMD = "../steamcmd/steamcmd.exe"

def install_mod(mod_id):

    username, password = load_steam_credentials()

    cmd = [
        STEAMCMD,
        "+login", username, password,
        "+workshop_download_item", "221100", mod_id,
        "+quit"
    ]

    subprocess.run(cmd)

def install_mod_list():

    with open("../config/mods.json") as f:
        mods = json.load(f)

    for mod in mods["mods"]:
        install_mod(mod)