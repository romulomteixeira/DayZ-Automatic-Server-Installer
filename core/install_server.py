import subprocess
import os
from steam_auth import get_login

STEAMCMD = "../steamcmd/steamcmd.exe"

SERVER_DIR = os.path.abspath("../servers/server1")

def install_server():

    os.makedirs(SERVER_DIR,exist_ok=True)

    login_cmd = get_login()

    cmd = [
        STEAMCMD,
        *login_cmd,
        "+force_install_dir", SERVER_DIR,
        "+app_update","223350","validate",
        "+quit"
    ]

    print("\nExecutando SteamCMD...\n")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    for line in process.stdout:
        print(line.strip())

    process.wait()

    exe = os.path.join(SERVER_DIR,"DayZServer_x64.exe")

    if os.path.exists(exe):
        print("\nServidor instalado com sucesso.")
        return True

    print("\nERRO: DayZServer_x64.exe nao encontrado.")
    return False


if __name__ == "__main__":

    ok = install_server()

    if not ok:
        input("Pressione ENTER para sair")