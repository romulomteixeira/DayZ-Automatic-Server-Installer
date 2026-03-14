import psutil
import subprocess
import time

SERVER_PROCESS = "DayZServer_x64.exe"

def start_server():
    subprocess.Popen(["start_server.bat"], shell=True)

def watchdog():

    while True:

        running = False

        for p in psutil.process_iter():
            if SERVER_PROCESS in p.name():
                running = True

        if not running:
            print("Server crashed. Restarting...")
            start_server()

        time.sleep(30)