"""Модуль перенастройки сети через netplan.

Переписывает конфигурацию на целевом хосте: основной IP/маска/шлюз,
второй IP/маска и DNS. Использует существующий netplan-файл, кроме
`01-network-manager-all.yaml` / `01-network-manager-all.yml`.

Важно: модуль намеренно затирает старые значения `addresses`, `gateway4`
и `nameservers.addresses`.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from . import Modules


class UserModule:
    slug = "network_reconfigure"
    title = "Перенастройка IP"
    description = (
        "Переписывает netplan-конфигурацию: основной IP, маска, шлюз, второй IP, "
        "вторая маска и DNS. Старые сетевые значения затираются."
    )
    web_ui_visible = True
    schema = {
        "placeholders": [
            ["interface", "Сетевой интерфейс", "eth0", "text"],
            ["ip_address", "Основной IP", "192.168.1.10", "text"],
            ["subnet_mask", "Маска подсети", "24", "text"],
            ["gateway", "Шлюз", "192.168.1.1", "text"],
            ["secondary_ip", "Второй IP", "192.168.1.11", "text"],
            ["secondary_mask", "Маска второго IP", "24", "text"],
            ["dns_addresses", "DNS-серверы (через запятую)", "1.1.1.1,8.8.8.8", "text"],
        ]
    }

    def exec(self):
        print("Этот модуль запускается через систему задач.")

    def _make_computer(self, context, host):
        to_computer = getattr(context, "to_computer", None)
        if callable(to_computer):
            try:
                return to_computer(host)
            except Exception:
                pass
        from computer import Computer
        return Computer(host=f"{host.username}@{host.address}", port=str(host.port))

    def _build_remote_script(self, **kwargs) -> str:
        interface = str(kwargs.get("interface") or "").strip()
        ip_address = str(kwargs.get("ip_address") or "").strip()
        subnet_mask = str(kwargs.get("subnet_mask") or "").strip()
        gateway = str(kwargs.get("gateway") or "").strip()
        secondary_ip = str(kwargs.get("secondary_ip") or "").strip()
        secondary_mask = str(kwargs.get("secondary_mask") or "").strip()
        dns_addresses = str(kwargs.get("dns_addresses") or "").strip()

        if not interface:
            raise ValueError("Не указан сетевой интерфейс")
        if not ip_address:
            raise ValueError("Не указан основной IP")
        if not subnet_mask:
            raise ValueError("Не указана маска подсети")
        if not gateway:
            raise ValueError("Не указан шлюз")
        if not secondary_ip:
            raise ValueError("Не указан второй IP")
        if not secondary_mask:
            raise ValueError("Не указана маска второго IP")

        dns_list = [d.strip() for d in dns_addresses.split(",") if d.strip()]
        dns_yaml = "\n".join(f"          - {shlex.quote(d)}" for d in dns_list)
        if not dns_yaml:
            dns_yaml = "          - 1.1.1.1"

        primary_cidr = f"{ip_address}/{subnet_mask}"
        secondary_cidr = f"{secondary_ip}/{secondary_mask}"
        interface_q = shlex.quote(interface)
        primary_q = shlex.quote(primary_cidr)
        secondary_q = shlex.quote(secondary_cidr)
        gateway_q = shlex.quote(gateway)

        return f"""set -e
NETPLAN_DIR=/etc/netplan
TARGET_FILE=""
for f in "$NETPLAN_DIR"/*.yaml "$NETPLAN_DIR"/*.yml; do
  [ -e "$f" ] || continue
  base=$(basename "$f")
  case "$base" in
    01-network-manager-all.yaml|01-network-manager-all.yml)
      continue
      ;;
  esac
  TARGET_FILE="$f"
  break
done

if [ -z "$TARGET_FILE" ]; then
  echo "[ERROR] Не найден netplan-файл, кроме 01-network-manager-all.*"
  exit 1
fi

sudo tee "$TARGET_FILE" > /dev/null <<'YAML_EOF'
network:
  version: 2
  renderer: NetworkManager
  ethernets:
    {interface_q}:
      dhcp4: false
      addresses:
        - {primary_q}
        - {secondary_q}
      routes:
        - to: default
          via: {gateway_q}
      nameservers:
        addresses:
{dns_yaml}
YAML_EOF

sudo netplan generate
sudo netplan apply

echo "[OK] Перенастроен netplan-файл: $TARGET_FILE"
echo "[OK] Интерфейс: {interface}"
echo "[OK] Адреса: {ip_address}/{subnet_mask}, {secondary_ip}/{secondary_mask}"
echo "[OK] Шлюз: {gateway}"
echo "[OK] DNS: {dns_addresses or '1.1.1.1'}"
"""

    async def run_for_host(self, context, host, **kwargs):
        base = {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
        }

        try:
            remote_script = self._build_remote_script(**kwargs)
        except ValueError as exc:
            return {**base, "status": "error", "output": f"[ERROR] {exc}"}

        computer = self._make_computer(context, host)
        output = await getattr(computer, "async_executor_ssh")(remote_script)
        status = "error" if output.startswith("[ERROR]") else "success"
        return {**base, "status": status, "output": output}


CustomModule = UserModule()
Modules.add_update(CustomModule.title, CustomModule)
