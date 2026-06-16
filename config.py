"""NetRunner configuration.

All deployment-specific values are loaded from environment variables with
secure defaults. No credentials or passphrases are hardcoded here.
"""

import os

# SSH private key location.
KEY_NAME = os.environ.get("NETRUNNER_KEY_NAME", "id_ed25519")
KEY_PATH = os.environ.get("NETRUNNER_KEY_PATH", "keys")

# Host-key verification policy.
# Default is strict ("yes") to prevent MITM attacks.
# Allowed values: "yes", "accept-new", "no", "ask".
# Set to "accept-new" only if you want to automatically trust new hosts on
# first use and store them in the configured known-hosts file.
SSH_STRICT_HOST_KEY_CHECKING = os.environ.get(
    "NETRUNNER_SSH_STRICT_HOST_KEY_CHECKING", "yes"
)

# Explicit known-hosts file. If not set, OpenSSH uses the default
# ~/.ssh/known_hosts. When using "accept-new", this file will be used to
# persist newly accepted host keys.
SSH_KNOWN_HOSTS_FILE = os.environ.get("NETRUNNER_SSH_KNOWN_HOSTS_FILE")

# Host IP address checking. OpenSSH default is "yes"; set to "no" if hosts
# are behind NAT and the recorded IP does not match the hostname.
SSH_CHECK_HOST_IP = os.environ.get("NETRUNNER_SSH_CHECK_HOST_IP")

# Legacy hosts list used by the interactive mass-SSH module.
HOSTS = []
