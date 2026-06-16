import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from computer.module.apt_package_manager import UserModule


class DummyHost:
    def __init__(self, name, address, port=22, username="admin"):
        self.id = 1
        self.name = name
        self.address = address
        self.port = port
        self.username = username


class DummyContext:
    task_run_id = 42

    class Logger:
        def info(self, *args, **kwargs):
            pass

    logger = Logger()

    def to_computer(self, host):
        from computer import Computer

        return Computer(host=f"{host.username}@{host.address}", port=str(host.port))


class TestAptPackageManager(unittest.TestCase):
    def test_build_command_install(self):
        mod = UserModule()
        cmd = mod._build_command("install", ["htop", "curl"])
        self.assertIn("apt-get install -y", cmd)
        self.assertIn("htop", cmd)
        self.assertIn("curl", cmd)
        self.assertNotIn(";", cmd)

    def test_build_command_remove_requires_packages(self):
        mod = UserModule()
        with self.assertRaises(ValueError):
            mod._build_command("remove", [])

    def test_parse_packages(self):
        mod = UserModule()
        self.assertEqual(mod._parse_packages("a b c"), ["a", "b", "c"])
        self.assertEqual(mod._parse_packages(["a", "", "b"]), ["a", "b"])
        self.assertEqual(mod._parse_packages(None), [])

    def test_detect_changed_install(self):
        mod = UserModule()
        stdout = "The following NEW packages will be installed:\n  htop curl\n0 upgraded, 2 newly installed"
        changed = mod._detect_changed("install", stdout, "")
        self.assertIn("htop", changed)
        self.assertIn("curl", changed)


async def run_mocked_apt():
    mod = UserModule()
    host = DummyHost("host-1", "host-1")

    async def fake_run_apt(computer, command, sudo_password=None):
        return "stdout-data", "stderr-data", 0

    mod._run_apt = fake_run_apt

    ctx = DummyContext()
    result = await mod.run_for_host(ctx, host, action="install", packages="htop")
    assert result["action"] == "install"
    assert result["packages"] == ["htop"]
    assert result["returncode"] == 0
    assert result["status"] == "success"
    print("mocked apt OK:", result["status"])


if __name__ == "__main__":
    unittest.main(exit=False)
    asyncio.run(run_mocked_apt())
