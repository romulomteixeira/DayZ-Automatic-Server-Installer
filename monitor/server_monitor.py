import psutil
import subprocess
import time

SERVER="DayZServer_x64.exe"

def running():

    for p in psutil.process_iter():

        if SERVER in p.name():
            return True

    return False

while True:

    if not running():

        subprocess.Popen("../servers/server1/DayZServer_x64.exe")

    time.sleep(30)