import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(BASE_DIR, "config", "steam.json")

def get_login():

    with open(CONFIG, encoding="utf-8") as f:
        steam = json.load(f)

    mode = steam.get("auth_mode", "anonymous")

    if mode == "anonymous":
        return ["+login", "anonymous"]

    username = steam["steam_username"]
    password = steam["steam_password"]

    return ["+login", username, password]