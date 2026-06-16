#!/bin/sh
# NetRunner Docker test host startup
# Waits for the shared SSH public key, installs it, then starts sshd.

set -e

KEY_FILE="/keys/id_ed25519.pub"
AUTH_KEYS="/home/admin/.ssh/authorized_keys"

echo "[host-startup] Installing SSH server and user..."
apk add --no-cache openssh-server sudo python3
ssh-keygen -A

adduser -D -s /bin/sh admin || true
echo 'admin:admin' | chpasswd
echo 'admin ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/admin
chmod 440 /etc/sudoers.d/admin

mkdir -p /home/admin/.ssh
chmod 700 /home/admin/.ssh
chown -R admin:admin /home/admin/.ssh

sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

echo "[host-startup] Waiting for shared public key at ${KEY_FILE}..."
for i in $(seq 1 60); do
    if [ -f "${KEY_FILE}" ]; then
        break
    fi
    sleep 1
done

if [ ! -f "${KEY_FILE}" ]; then
    echo "[host-startup] ERROR: public key not found after 60 seconds"
    exit 1
fi

cp "${KEY_FILE}" "${AUTH_KEYS}"
chmod 600 "${AUTH_KEYS}"
chown admin:admin "${AUTH_KEYS}"

echo "[host-startup] Starting sshd..."
exec /usr/sbin/sshd -D
