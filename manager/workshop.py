import requests

STEAM_API = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"

def get_mod_details(mod_ids):

    payload = {"itemcount": len(mod_ids)}

    for i, m in enumerate(mod_ids):
        payload[f"publishedfileids[{i}]"] = m

    r = requests.post(STEAM_API, data=payload).json()

    mods = []

    for item in r["response"]["publishedfiledetails"]:
        name = item["title"]
        deps = []

        if "children" in item:
            for d in item["children"]:
                deps.append(str(d["publishedfileid"]))

        mods.append({
            "id": item["publishedfileid"],
            "name": name,
            "dependencies": deps
        })

    return mods