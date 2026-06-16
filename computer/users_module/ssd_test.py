from computer import Computer
from config import HOSTS
from . import UserModules


class UserModule:
    LOG_PATH = "/var/tmp/netrunner_ssd_test.log"
    PID_PATH = "/var/tmp/netrunner_ssd_test.pid"
    SCRIPT_PATH = "/var/tmp/netrunner_ssd_test_worker.sh"
    MOUNT_ROOT = "/mnt/netrunner_ssd_test"

    def __init__(self):
        self.title = "SSD тест (dd, фон, лог)."
        self.description = """
1 - запустить тест
2 - статус
3 - tail лога
4 - весь лог
5 - summary по всем хостам

Лог: /var/tmp/netrunner_ssd_test.log
PID : /var/tmp/netrunner_ssd_test.pid
        """.strip()

    def exec(self):
        try:
            print(
                "1 - запустить тест\n"
                "2 - статус\n"
                "3 - tail лога\n"
                "4 - весь лог\n"
            )
            action = input("Выберите действие: ").strip()

            if action == "1":
                self._start_flow()
            elif action == "2":
                self._status_flow()
            elif action == "3":
                self._tail_flow()
            elif action == "4":
                self._full_log_flow()
            elif action == "5":
                self._summary_flow()
            else:
                print("Неизвестное действие.")
        except KeyboardInterrupt:
            print("\nОстановлено...")

    def _start_flow(self):
        targets = self._pick_targets()
        if not targets:
            print("Хосты не выбраны.")
            return

        raw_size = input("Размер тестового файла в MiB [1024]: ").strip()
        size_mb = 1024
        if raw_size:
            if not raw_size.isdigit() or int(raw_size) <= 0:
                print("Размер должен быть положительным числом.")
                return
            size_mb = int(raw_size)

        selector_mode, exact_device = self._pick_disk_selector()
        if selector_mode is None:
            print("Тип диска не выбран.")
            return

        command = self._build_start_command(
            size_mb=size_mb,
            selector_mode=selector_mode,
            exact_device=exact_device or "",
        )

        for host in targets:
            result = Computer(host).executor_ssh(command)
            print(f"\n=== {host} ===\n{result}\n")

    def _status_flow(self):
        targets = self._pick_targets()
        if not targets:
            print("Хосты не выбраны.")
            return

        command = (
            f'echo "LOG: {self.LOG_PATH}"; '
            f'echo "PID: {self.PID_PATH}"; '
            f'pid=""; '
            f'test -f "{self.PID_PATH}" && pid="$(cat "{self.PID_PATH}" 2>/dev/null)"; '
            f'if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then '
            f'  echo "[RUNNING] pid=$pid"; '
            f'else '
            f'  echo "[NOT RUNNING]"; '
            f'fi; '
            f'echo; '
            f'if [ -f "{self.LOG_PATH}" ]; then '
            f'  echo "--- last 20 lines ---"; '
            f'  tail -n 20 "{self.LOG_PATH}"; '
            f'else '
            f'  echo "[NO LOG FILE]"; '
            f'fi'
        )

        for host in targets:
            result = Computer(host).executor_ssh(command)
            print(f"\n=== {host} ===\n{result}\n")

    def _tail_flow(self):
        targets = self._pick_targets()
        if not targets:
            print("Хосты не выбраны.")
            return

        raw_lines = input("Сколько строк показать [40]: ").strip()
        lines = 40
        if raw_lines:
            if not raw_lines.isdigit() or int(raw_lines) <= 0:
                print("Количество строк должно быть положительным числом.")
                return
            lines = int(raw_lines)

        command = (
            f'if [ -f "{self.LOG_PATH}" ]; then '
            f'  tail -n {lines} "{self.LOG_PATH}"; '
            f'else '
            f'  echo "[NO LOG FILE] {self.LOG_PATH}"; '
            f'fi'
        )

        for host in targets:
            result = Computer(host).executor_ssh(command)
            print(f"\n=== {host} ===\n{result}\n")

    def _full_log_flow(self):
        targets = self._pick_targets()
        if not targets:
            print("Хосты не выбраны.")
            return

        command = (
            f'if [ -f "{self.LOG_PATH}" ]; then '
            f'  cat "{self.LOG_PATH}"; '
            f'else '
            f'  echo "[NO LOG FILE] {self.LOG_PATH}"; '
            f'fi'
        )

        for host in targets:
            result = Computer(host).executor_ssh(command)
            print(f"\n=== {host} ===\n{result}\n")

    def _summary_flow(self):
        print("host | device | automount | write | read | status")
        print("-" * 90)

        command = fr'''pid=""
[ -f "{self.PID_PATH}" ] && pid="$(cat "{self.PID_PATH}" 2>/dev/null)"
running="0"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    running="1"
fi

if [ ! -f "{self.LOG_PATH}" ]; then
    if [ "$running" = "1" ]; then
        printf '%s' '-|-|-|-|RUNNING'
    else
        printf '%s' '-|-|-|-|NO_LOG'
    fi
else
    device="$(grep -m1 '^\[INFO\] BASE_DEV:' "{self.LOG_PATH}" | sed 's/^\[INFO\] BASE_DEV: //')"
    if [ -z "$device" ]; then
        device="$(grep -m1 '^\[INFO\] SOURCE_DEV:' "{self.LOG_PATH}" | sed 's/^\[INFO\] SOURCE_DEV: //')"
    fi
    [ -z "$device" ] && device='-'

    automount="$(grep -m1 '^\[INFO\] AUTO_MOUNTED:' "{self.LOG_PATH}" | sed 's/^\[INFO\] AUTO_MOUNTED: //')"
    [ -z "$automount" ] && automount='-'

    write_speed="$(awk '/\[WRITE\] start/{{flag=1; next}} flag && /\/s$/{{print $(NF-1), $NF; exit}}' "{self.LOG_PATH}")"
    [ -z "$write_speed" ] && write_speed='-'

    read_speed="$(awk '/\[READ\] start/{{flag=1; next}} flag && /\/s$/{{print $(NF-1), $NF; exit}}' "{self.LOG_PATH}")"
    [ -z "$read_speed" ] && read_speed='-'

    status='UNKNOWN'
    if [ "$running" = "1" ]; then
        status='RUNNING'
    elif grep -q '^=== SSD TEST END ' "{self.LOG_PATH}"; then
        status='OK'
    elif grep -q '^\[NO MATCH\]' "{self.LOG_PATH}"; then
        status='NO_MATCH'
    elif grep -q 'mount failed' "{self.LOG_PATH}"; then
        status='MOUNT_FAIL'
    elif grep -q '^\[WARN\]' "{self.LOG_PATH}"; then
        status='WARN'
    fi

    printf '%s|%s|%s|%s|%s' "$device" "$automount" "$write_speed" "$read_speed" "$status"
fi
'''.strip()

        for host in HOSTS:
            result = Computer(host).executor_ssh(command).strip()
            if result.startswith("[ERROR]"):
                print(f"{host} | - | - | - | - | SSH_ERROR")
                continue

            parts = result.split("|", 4)
            if len(parts) != 5:
                print(f"{host} | - | - | - | - | PARSE_ERROR")
                continue

            device, automount, write_speed, read_speed, status = [p.strip() or "-" for p in parts]
            print(f"{host} | {device} | {automount} | {write_speed} | {read_speed} | {status}")

    def _pick_targets(self):
        mode = input("1 - один хост, 2 - все хосты: ").strip()

        if mode == "2":
            return HOSTS

        print("Доступные компьютеры:")
        for i, host in enumerate(HOSTS, start=1):
            print(f"{i}. {host}")

        raw = input("Выберите номер компьютера: ").strip()
        if not raw.isdigit():
            return []

        idx = int(raw) - 1
        if idx < 0 or idx >= len(HOSTS):
            return []

        return [HOSTS[idx]]

    def _pick_disk_selector(self):
        print(
            "\nТип диска для теста:\n"
            "1 - любой SSD\n"
            "2 - только /dev/sd*\n"
            "3 - только /dev/nvme*\n"
            "4 - конкретное базовое устройство (например sda или nvme0n1)\n"
        )

        choice = input("Выберите тип диска: ").strip()

        if choice == "1":
            return "any", None
        if choice == "2":
            return "sd", None
        if choice == "3":
            return "nvme", None
        if choice == "4":
            exact = input("Введите базовое устройство: ").strip()
            if not exact:
                return None, None

            allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            if any(ch not in allowed for ch in exact):
                print("Недопустимое имя устройства.")
                return None, None

            return "exact", exact

        return None, None

    def _build_start_command(self, size_mb: int, selector_mode: str, exact_device: str):
        script = r'''
cat > "__SCRIPT_PATH__" <<'SSDTESTEOF'
#!/bin/sh

LOG_PATH="__LOG_PATH__"
PID_PATH="__PID_PATH__"
SIZE_MB="__SIZE_MB__"
SELECTOR_MODE="__SELECTOR_MODE__"
EXACT_DEVICE="__EXACT_DEVICE__"
MOUNT_ROOT="__MOUNT_ROOT__"

AUTO_MOUNTED=0
TARGET_MOUNT=""
SOURCE_DEV=""
FSTYPE=""
BASE_DEV=""
MODEL=""
ROTA=""
TEST_DIR=""
TEST_FILE=""

run_root() {
    sudo -n "$@"
}

cleanup() {
    if [ -n "$TEST_FILE" ]; then
        rm -f "$TEST_FILE" 2>/dev/null || run_root rm -f "$TEST_FILE" 2>/dev/null || true
    fi

    if [ "$AUTO_MOUNTED" = "1" ] && [ -n "$TARGET_MOUNT" ]; then
        run_root umount "$TARGET_MOUNT" >/dev/null 2>&1 || true
        run_root rmdir "$TARGET_MOUNT" >/dev/null 2>&1 || true
    fi

    rm -f "$PID_PATH"
}

trap cleanup EXIT INT TERM

device_class() {
    case "$1" in
        nvme*) echo "nvme" ;;
        sd*)   echo "sd" ;;
        *)     echo "other" ;;
    esac
}

match_selector() {
    base="$1"

    case "$SELECTOR_MODE" in
        any)
            return 0
            ;;
        sd)
            [ "$(device_class "$base")" = "sd" ]
            return $?
            ;;
        nvme)
            [ "$(device_class "$base")" = "nvme" ]
            return $?
            ;;
        exact)
            [ "$base" = "$EXACT_DEVICE" ]
            return $?
            ;;
        *)
            return 1
            ;;
    esac
}

prepare_test_dir() {
    mount_point="$1"
    test_dir="$mount_point/.netrunner_ssd_test"

    if ! run_root mkdir -p "$test_dir" 2>/dev/null; then
        mkdir -p "$test_dir" 2>/dev/null || return 1
    fi

    run_root chown "$(id -u):$(id -g)" "$test_dir" 2>/dev/null || true

    if ! touch "$test_dir/.writecheck" 2>/dev/null; then
        if ! run_root touch "$test_dir/.writecheck" 2>/dev/null; then
            echo "[DEBUG] write check failed: $test_dir"
            return 1
        fi
        run_root chown "$(id -u):$(id -g)" "$test_dir/.writecheck" 2>/dev/null || true
    fi

    rm -f "$test_dir/.writecheck" 2>/dev/null || run_root rm -f "$test_dir/.writecheck" 2>/dev/null || true

    printf '%s\n' "$test_dir"
    return 0
}

select_largest_partition() {
    best_size=0
    best_name=""
    best_fstype=""
    best_mount=""
    best_base=""
    best_model=""

    for base in $(lsblk -dn -o NAME,TYPE,ROTA 2>/dev/null | awk '$2=="disk" && $3=="0" {print $1}'); do
        match_selector "$base" || continue

        model="$(lsblk -dn -o MODEL "/dev/$base" 2>/dev/null | sed 's/^ *//; s/ *$//')"
        echo "[INFO] disk candidate: /dev/$base model=${model:-unknown}"

        while read -r name ptype pfstype psize pmount; do
            [ -n "$name" ] || continue
            [ "$ptype" = "part" ] || continue
            [ -n "$pfstype" ] || continue
            [ -n "$psize" ] || continue

            echo "[INFO] partition candidate: /dev/$name fstype=$pfstype size_bytes=$psize mount=${pmount:-<empty>}"

            if [ "$psize" -gt "$best_size" ]; then
                best_size="$psize"
                best_name="$name"
                best_fstype="$pfstype"
                best_mount="$pmount"
                best_base="$base"
                best_model="$model"
            fi
        done <<EOF
$(lsblk -lnb -o NAME,TYPE,FSTYPE,SIZE,MOUNTPOINT "/dev/$base" 2>/dev/null)
EOF
    done

    if [ -z "$best_name" ]; then
        return 1
    fi

    SOURCE_DEV="/dev/$best_name"
    FSTYPE="$best_fstype"
    TARGET_MOUNT="$best_mount"
    BASE_DEV="$best_base"
    MODEL="$best_model"
    ROTA="0"

    echo "[INFO] selected largest partition: $SOURCE_DEV"
    echo "[INFO] selected base disk: /dev/$BASE_DEV"
    echo "[INFO] selected size_bytes: $best_size"

    return 0
}

use_selected_partition() {
    if [ -z "$SOURCE_DEV" ]; then
        echo "[DEBUG] SOURCE_DEV is empty"
        return 1
    fi

    if [ -n "$TARGET_MOUNT" ] && [ "$TARGET_MOUNT" != "-" ]; then
        echo "[INFO] using existing mountpoint: $TARGET_MOUNT"
        AUTO_MOUNTED=0
        TEST_DIR="$(prepare_test_dir "$TARGET_MOUNT")" || {
            echo "[DEBUG] prepare_test_dir failed on mounted path: $TARGET_MOUNT"
            return 1
        }
        return 0
    fi

    TARGET_MOUNT="${MOUNT_ROOT}_$(basename "$SOURCE_DEV")"
    echo "[INFO] attempting auto-mount: $SOURCE_DEV -> $TARGET_MOUNT"

    if ! run_root mkdir -p "$TARGET_MOUNT" 2>/dev/null; then
        echo "[DEBUG] mkdir failed for mountpoint: $TARGET_MOUNT"
        return 1
    fi

    mount_err="$(run_root mount "$SOURCE_DEV" "$TARGET_MOUNT" 2>&1)"
    mount_rc=$?

    if [ $mount_rc -ne 0 ]; then
        echo "[DEBUG] mount failed: $SOURCE_DEV -> $TARGET_MOUNT"
        echo "[DEBUG] mount rc: $mount_rc"
        echo "[DEBUG] mount stderr: $mount_err"
        return 1
    fi

    AUTO_MOUNTED=1
    echo "[INFO] mounted OK: $SOURCE_DEV -> $TARGET_MOUNT"

    TEST_DIR="$(prepare_test_dir "$TARGET_MOUNT")" || {
        echo "[DEBUG] prepare_test_dir failed on auto-mounted path: $TARGET_MOUNT"
        run_root umount "$TARGET_MOUNT" >/dev/null 2>&1 || true
        run_root rmdir "$TARGET_MOUNT" >/dev/null 2>&1 || true
        AUTO_MOUNTED=0
        return 1
    }

    return 0
}

: > "$LOG_PATH"
exec >> "$LOG_PATH" 2>&1

echo "=== SSD TEST START $(date '+%F %T') ==="
echo "HOST: $(hostname)"
echo "USER: $(whoami)"
echo "SIZE_MB: $SIZE_MB"
echo "SELECTOR_MODE: $SELECTOR_MODE"
echo "EXACT_DEVICE: $EXACT_DEVICE"
echo

echo "[INFO] sudo check:"
if run_root true 2>/dev/null; then
    echo "[INFO] sudo -n OK"
else
    echo "[WARN] sudo -n is not available"
fi
echo

echo "[INFO] lsblk -f:"
lsblk -f 2>/dev/null || true
echo

echo "[INFO] findmnt:"
findmnt -rn -o TARGET,SOURCE,FSTYPE 2>/dev/null || true
echo

if ! select_largest_partition; then
    echo "[NO MATCH] Не найден подходящий раздел для теста."
    echo "[INFO] Причины:"
    echo " - нет SSD нужного типа;"
    echo " - на подходящем диске нет раздела с файловой системой."
    exit 0
fi

if ! use_selected_partition; then
    echo "[NO MATCH] Не удалось подготовить выбранный раздел для теста."
    echo "[INFO] Причины:"
    echo " - mount не удался;"
    echo " - нет прав на mount/запись;"
    echo " - файловая система требует проверки."
    exit 0
fi

TEST_FILE="$TEST_DIR/dd_test.bin"

echo "[INFO] SELECTED_MOUNT: $TARGET_MOUNT"
echo "[INFO] SOURCE_DEV: $SOURCE_DEV"
echo "[INFO] BASE_DEV: /dev/$BASE_DEV"
echo "[INFO] MODEL: $MODEL"
echo "[INFO] FSTYPE: $FSTYPE"
echo "[INFO] ROTA: $ROTA"
echo "[INFO] AUTO_MOUNTED: $AUTO_MOUNTED"
echo "[INFO] TEST_DIR: $TEST_DIR"
echo "[INFO] TEST_FILE: $TEST_FILE"
echo

rm -f "$TEST_FILE" 2>/dev/null || run_root rm -f "$TEST_FILE" 2>/dev/null || true

echo "[WRITE] start $(date '+%F %T')"
if run_root dd if=/dev/zero of="$TEST_FILE" bs=1M count="$SIZE_MB" oflag=direct conv=fdatasync 2>&1; then
    echo "[WRITE] direct OK"
else
    echo "[WARN] direct write failed, fallback to buffered write"
    run_root dd if=/dev/zero of="$TEST_FILE" bs=1M count="$SIZE_MB" conv=fdatasync 2>&1 || exit 1
fi

sync

echo
echo "[READ] start $(date '+%F %T')"
if run_root dd if="$TEST_FILE" of=/dev/null bs=1M iflag=direct 2>&1; then
    echo "[READ] direct OK"
else
    echo "[WARN] direct read failed, fallback to buffered read"
    run_root dd if="$TEST_FILE" of=/dev/null bs=1M 2>&1 || exit 1
fi

echo
echo "=== SSD TEST END $(date '+%F %T') ==="
SSDTESTEOF

chmod +x "__SCRIPT_PATH__"
nohup sh "__SCRIPT_PATH__" >/dev/null 2>&1 < /dev/null &
pid=$!
echo "$pid" > "__PID_PATH__"
echo "[STARTED] pid=$pid"
echo "LOG: __LOG_PATH__"
echo "SCRIPT: __SCRIPT_PATH__"
'''.strip()

        return (
            script
            .replace("__LOG_PATH__", self.LOG_PATH)
            .replace("__PID_PATH__", self.PID_PATH)
            .replace("__SCRIPT_PATH__", self.SCRIPT_PATH)
            .replace("__SIZE_MB__", str(size_mb))
            .replace("__SELECTOR_MODE__", selector_mode)
            .replace("__EXACT_DEVICE__", exact_device)
            .replace("__MOUNT_ROOT__", self.MOUNT_ROOT)
        )


CustomModule = UserModule()
UserModules.add_update("ssd_test", CustomModule)
