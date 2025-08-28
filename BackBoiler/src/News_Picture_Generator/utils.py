import json
from pathlib import Path

CONFIG_PATH = Path("/home/anews/PS/gan/config.json")

def read_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def write_config(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
