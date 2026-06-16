# SSH Security Fixes

## Summary of Changes

This patch addresses the SSH security issues reported in the code review by
replacing silent host-key trust with strict verification, removing hardcoded
credentials, sanitizing command construction, and preventing storage of private
key material in the database.

## Host-Key Verification

- Replaced `-o StrictHostKeyChecking=no` and `-o UserKnownHostsFile=/dev/null`
  with a configurable policy in every SSH/SCP call.
- New default is `StrictHostKeyChecking=yes`. The operator can explicitly opt in
  to a less strict mode (e.g. `accept-new`) via the
  `NETRUNNER_SSH_STRICT_HOST_KEY_CHECKING` environment variable.
- Added `NETRUNNER_SSH_KNOWN_HOSTS_FILE` so operators can point to an explicit
  known-hosts file. Unknown hosts are never silently trusted.
- Affected files:
  - `computer/module/executor_ssh.py` (common options helper)
  - `computer/module/executor_scp.py`
  - `computer/module/hard_drive_check.py`
  - `computer/module/folder_swipe.py`
  - `computer/module/installer.py`
  - `webui/server.py` (`ssh-copy-id` provisioning)

## Hardcoded Credentials

- Removed hardcoded `PASSWORD` and `PASSPHRASE` from `config_docker.py`.
- Created `config.py` with environment-variable-driven configuration and no
  hardcoded secrets.
- Updated `computer/module/installer.py` so packages and the sudo password are
  read from the `INSTALL_PACKAGES` and `INSTALL_SUDO_PASSWORD` environment
  variables, instead of using a hardcoded `PASSWORD` value.
- Removed the fake `PASSWORD` and `PASSPHRASE` values from the temporary config
  in `tests_async_cancel.py`.

## Command Injection Hardening

- Converted all SSH/SCP helper modules to use `subprocess.run` with list-style
  arguments instead of `shell=True` with formatted strings.
- User-provided values (remote command, package list, directory path) are passed
  as separate arguments or quoted with `shlex.quote` before being sent to the
  remote shell.
- `webui/server.py` `_provision_ssh_key` now passes the provisioning password
  to `sshpass` via the `SSHPASS` environment variable instead of the `-p`
  command-line flag, so the password no longer appears in the process list.

## Private Key Handling

- Generated SSH keys are still written to disk (encrypted when a passphrase is
  provided), but the plaintext private key is no longer stored in the
  `ssh_keys.private_key` database column.
- The `/api/keys/generate` endpoint already returned only public metadata; the
  database backing it no longer retains the private PEM.
- No SSH code logs private keys or key material; only command outputs are
  returned.

## Public Key Storage in Database

- The `ssh_keys` table stores the public key string, key type, and SHA-256 fingerprint for generated keys. This is intentional and safe: public keys can be shared freely.
- The `private_key` column is kept in the schema for compatibility with uploaded legacy keys, but generated keys intentionally leave it `NULL` and store only the encrypted (or unencrypted) PEM file on disk.

## Additional Code Fixes Found During the Security Pass

- `computer/module/folder_swipe.py` incorrectly used `result.stderr == 0` to judge success; fixed to use `result.returncode == 0`.
- `computer/module/hard_drive_check.py` returned the raw `subprocess.CompletedProcess` object; fixed to capture output and return a formatted string or error message.

## Configuration Reference

| Environment Variable | Default | Purpose |
|---|---|---|
| `NETRUNNER_KEY_NAME` | `id_ed25519` | Name of the SSH private key file |
| `NETRUNNER_KEY_PATH` | `keys` (or `/app/keys` in Docker) | Directory containing the key |
| `NETRUNNER_SSH_STRICT_HOST_KEY_CHECKING` | `yes` | Host-key verification policy |
| `NETRUNNER_SSH_KNOWN_HOSTS_FILE` | unset (uses `~/.ssh/known_hosts`) | Explicit known-hosts file |
| `NETRUNNER_SSH_CHECK_HOST_IP` | unset | OpenSSH `CheckHostIP` option |
| `INSTALL_PACKAGES` | unset | Package list for the installer module |
| `INSTALL_SUDO_PASSWORD` | unset | Sudo password for the installer module |

## Backwards Compatibility

- Public method signatures of `Computer`, `executor_ssh`, `async_main`,
  `executor_scp`, `hard_drive_check`, and `folder_swipe` are unchanged.
- The default host-key policy is now strict, so deployments that previously
  relied on `StrictHostKeyChecking=no` must either populate a known-hosts file or
  explicitly set `NETRUNNER_SSH_STRICT_HOST_KEY_CHECKING` to a looser policy.
