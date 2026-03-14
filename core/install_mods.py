import json
import subprocess
from steam_auth import get_login

from logger import log

log("Iniciando instalação de mods")

STEAMCMD = "steamcmd/steamcmd.exe"

login_cmd = get_login()

# carregar mods
with open("config/mods.json") as f:
    mods = json.load(f)["mods"]

print("\nInstalando mods...\n")

for mod in mods:

    print("Instalando mod:", mod)
    log("Instalando mod "+str(mod))

    cmd = [
        STEAMCMD,
        *login_cmd,
        "+workshop_download_item", "221100", str(mod),
        "+quit"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    for line in process.stdout:
        print(line.strip())

    process.wait()

print("\nInstalação de mods concluída.")
log("\nInstalação de mods concluída.")