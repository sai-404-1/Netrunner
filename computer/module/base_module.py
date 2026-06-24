from __future__ import annotations

import shlex


class CommandModule:
    """Base for simple SSH-command modules with $variable substitution.

    Subclasses only need to define:
        slug, title, description, command, schema

    run_for_host is provided automatically and runs the substituted command
    via async SSH. Override it only if you need custom logic.

    Schema format:
        {"placeholders": [
            [name, label, default, type],           # text / textarea / password
            [name, label, default, "select", opts],  # opts: ["val"] or [["val","label"]]
        ]}
    """

    slug: str = ""
    command: str = ""
    schema: dict = {"placeholders": []}

    def exec(self) -> None:
        print("Этот модуль запускается через систему задач.")

    def _build_command(self, kwargs: dict) -> str:
        entries = sorted(
            self.schema.get("placeholders", []),
            key=lambda e: -len(e[0]),  # длинные имена первыми — нет частичных совпадений
        )
        cmd = self.command
        for entry in entries:
            name = entry[0]
            default = entry[2] if len(entry) > 2 else ""
            value = kwargs.get(name, default)
            cmd = cmd.replace(f"${name}", shlex.quote(str(value)))
        return cmd

    async def run_for_host(self, context, host, **kwargs):
        cmd = self._build_command(kwargs)

        to_computer = getattr(context, "to_computer", None)
        if callable(to_computer):
            try:
                computer = to_computer(host)
            except Exception:
                computer = None
        else:
            computer = None

        if computer is None:
            from computer import Computer
            computer = Computer(
                host=f"{host.username}@{host.address}",
                port=str(host.port),
            )

        output = await computer.async_executor_ssh(cmd)
        return {
            "host_id": host.id,
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "username": host.username,
            "output": output,
        }
