import subprocess

STEAMCMD = "../steamcmd/steamcmd.exe"

def update_server(server_path):

    cmd = [
        STEAMCMD,
        "+login anonymous",
        "+force_install_dir", server_path,
        "+app_update 223350",
        "+quit"
    ]

    subprocess.run(cmd)