KEY_NAME="id_ed25519_2"
KEY_PATH="keys"
PASSPHRASE="123"
PASSWORD=",ehtdtcnybr"

import json
with open('./hosts.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
HOSTS = data["ips"]
