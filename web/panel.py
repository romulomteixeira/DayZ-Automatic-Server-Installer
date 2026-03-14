from flask import Flask, render_template
import psutil
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from monitor.player_monitor import get_players

app = Flask(__name__)

@app.route("/")
def dashboard():

    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    players = get_players()

    return render_template(
        "dashboard.html",
        cpu=cpu,
        ram=ram,
        players=players
    )

app.run(port=80)