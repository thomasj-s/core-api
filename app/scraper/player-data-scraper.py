import requests
import time
import json
import csv
import pandas as pd

params = {
    "platform": "console",
    "gamemode": "competitive"
}

usernames = []


with open("app/scraper/usernames.csv", mode = "r", newline = "") as file:
    reader = csv.reader(file)
    for row in reader:
        usernames.append("".join(row).replace(" ", ""))

def get_player(player_id):
    url = f"https://overfast-api.tekrop.fr/players/{player_id}/stats/summary"
    response = requests.get(url, params = params)
    return response.json()

def build_player_data(usernames):
    player_data = {}
    count = 0
    for username in usernames:
        profile = get_player(username)
        if profile == {} or 'error' in profile.keys():
            continue
        player_data[username] = profile
        if count % 10 == 0 and count > 0:
            print(f"Fetched {count} player data entries...")
            if count % 10 == 0:
                try:
                    base = pd.read_csv("/home/thomas/projects/core-api/app/scraper/player_data.csv")
                except pd.errors.EmptyDataError:
                    base = pd.DataFrame()
                df = pd.json_normalize([{'username': k, **v} for k, v in player_data.items()])
                new = pd.concat([base, df], axis = 0, ignore_index = True)
                new.to_csv("/home/thomas/projects/core-api/app/scraper/player_data.csv", mode = "w", header = True, index = False)
                player_data = {}
        time.sleep(0.1)
        count += 1
    return 

build_player_data(usernames)