import json
import subprocess

def start_cluster():

    with open("../config/cluster.json") as f:
        cluster = json.load(f)

    for s in cluster["servers"]:

        exe = f'{s["path"]}/DayZServer_x64.exe'

        subprocess.Popen([
            exe,
            "-config=serverDZ.cfg",
            f'-port={s["port"]}'
        ])

        print("Servidor iniciado:", s["name"])