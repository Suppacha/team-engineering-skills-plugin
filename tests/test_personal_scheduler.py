import plistlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from team_updater.scheduler import Scheduler, launch_agent, windows_task


class SchedulerDefinitionTests(unittest.TestCase):
    def test_launch_agent_interval_and_arguments(self):
        data = plistlib.loads(launch_agent(["/path with space/python", "/team/update.py", "check"]))
        self.assertEqual(data["StartInterval"], 14400)
        self.assertTrue(data["RunAtLoad"])
        self.assertEqual(data["ProgramArguments"],
                         ["/path with space/python", "/team/update.py", "check"])
        self.assertNotIn("UserName", data)

    def test_windows_task_is_least_privilege_interactive_and_quotes_arguments(self):
        root = ET.fromstring(windows_task([
            r"C:\Program Files\Python\python.exe", r"C:\Team Updater\team-update.py", "check"
        ], r"DOMAIN\person"))
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        self.assertEqual(root.findtext(".//t:LogonType", namespaces=ns), "InteractiveToken")
        self.assertEqual(root.findtext(".//t:RunLevel", namespaces=ns), "LeastPrivilege")
        self.assertEqual(root.findtext(".//t:MultipleInstancesPolicy", namespaces=ns), "IgnoreNew")
        self.assertEqual(root.findtext(".//t:Interval", namespaces=ns), "PT4H")
        self.assertEqual(root.findtext(".//t:Command", namespaces=ns),
                         r"C:\Program Files\Python\python.exe")
        self.assertEqual(root.findtext(".//t:Arguments", namespaces=ns),
                         subprocess.list2cmdline([r"C:\Team Updater\team-update.py", "check"]))

    def test_definitions_reject_xml_control_characters(self):
        with self.assertRaisesRegex(ValueError, "invalid-scheduler-value"):
            windows_task([r"C:\Python\python.exe", "bad\x01path", "check"], "user")


class FakeMacRunner:
    def __init__(self):
        self.loaded = False
        self.loaded_argv = None
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if command[1:3] == ["print", "gui/501/com.suppacha.team-engineering-skills-updater"]:
            if not self.loaded:
                return subprocess.CompletedProcess(command, 1, b"", b"")
            lines = ["program = " + self.loaded_argv[0], "arguments = {"]
            lines.extend("\t" + value for value in self.loaded_argv)
            lines.append("}")
            return subprocess.CompletedProcess(command, 0, ("\n".join(lines) + "\n").encode(), b"")
        if command[1] == "bootstrap":
            self.loaded = True
            self.loaded_argv = plistlib.loads(Path(command[-1]).read_bytes())["ProgramArguments"]
            return subprocess.CompletedProcess(command, 0, b"", b"")
        if command[1] == "bootout":
            self.loaded = False
            self.loaded_argv = None
            return subprocess.CompletedProcess(command, 0, b"", b"")
        raise AssertionError(command)


class SchedulerLifecycleTests(unittest.TestCase):
    def test_macos_enable_reads_back_and_disable_removes_only_owned_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / "python"
            entry = root / "team-update.py"
            python.write_text("")
            entry.write_text("")
            runner = FakeMacRunner()
            runner.loaded = True  # same label may still point at an older argv
            agents = root / "LaunchAgents"
            agents.mkdir()
            scheduler = Scheduler(root, python, entry, run=runner,
                                  platform="darwin", uid=501,
                                  launch_agents=agents)
            definition = root / "LaunchAgents/com.suppacha.team-engineering-skills-updater.plist"
            definition.write_bytes(launch_agent(scheduler.argv))
            runner.loaded_argv = scheduler.argv
            scheduler.enable()
            self.assertTrue(scheduler.status())
            self.assertIn(["launchctl", "bootout", "gui/501", str(definition)], runner.calls)
            self.assertIn(["launchctl", "bootstrap", "gui/501", str(definition)], runner.calls)
            self.assertTrue(definition.is_file())
            definition.write_bytes(launch_agent([str(python), str(entry), "different"]))
            with self.assertRaisesRegex(RuntimeError, "scheduler-collision"):
                scheduler.disable()
            self.assertTrue(definition.exists())

    def test_macos_loaded_label_without_owned_definition_is_not_booted_out(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / "python"
            entry = root / "team-update.py"
            python.write_text("")
            entry.write_text("")
            runner = FakeMacRunner()
            runner.loaded = True
            runner.loaded_argv = [str(python), str(entry), "foreign"]
            scheduler = Scheduler(root, python, entry, run=runner,
                                  platform="darwin", uid=501,
                                  launch_agents=root / "LaunchAgents")
            with self.assertRaisesRegex(RuntimeError, "scheduler-collision"):
                scheduler.enable()
            self.assertFalse(any(command[1] == "bootout" for command in runner.calls))

    def test_macos_owned_plist_does_not_authorize_bootout_of_different_loaded_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / "python"
            entry = root / "team-update.py"
            python.write_text("")
            entry.write_text("")
            agents = root / "LaunchAgents"
            agents.mkdir()
            runner = FakeMacRunner()
            runner.loaded = True
            runner.loaded_argv = [str(python), "/foreign/update.py", "check"]
            scheduler = Scheduler(root, python, entry, run=runner,
                                  platform="darwin", uid=501, launch_agents=agents)
            scheduler.plist_path.write_bytes(launch_agent(scheduler.argv))
            with self.assertRaisesRegex(RuntimeError, "scheduler-collision"):
                scheduler.enable()
            self.assertFalse(any(command[1] == "bootout" for command in runner.calls))

    def test_enable_refuses_an_unowned_existing_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / "python"
            entry = root / "team-update.py"
            python.write_text("")
            entry.write_text("")
            agents = root / "LaunchAgents"
            agents.mkdir()
            path = agents / "com.suppacha.team-engineering-skills-updater.plist"
            path.write_bytes(launch_agent([str(python), str(entry), "other-state"]))
            scheduler = Scheduler(root, python, entry, run=FakeMacRunner(),
                                  platform="darwin", uid=501, launch_agents=agents)
            with self.assertRaisesRegex(RuntimeError, "scheduler-collision"):
                scheduler.enable()
            self.assertTrue(path.exists())

    def test_windows_create_uses_xml_file_then_requires_owned_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / "python.exe"
            entry = root / "team-update.py"
            python.write_text("")
            entry.write_text("")
            installed = {"xml": None}
            calls = []

            def runner(command, **kwargs):
                calls.append(command)
                if "/Query" in command:
                    if "/TN" not in command:
                        return subprocess.CompletedProcess(command, 0, b"", b"")
                    if installed["xml"] is None:
                        return subprocess.CompletedProcess(command, 1, b"", b"")
                    return subprocess.CompletedProcess(command, 0, installed["xml"], b"")
                if "/Create" in command:
                    xml_path = Path(command[command.index("/XML") + 1])
                    self.assertTrue(xml_path.is_file())
                    installed["xml"] = xml_path.read_bytes()
                    return subprocess.CompletedProcess(command, 0, b"", b"")
                raise AssertionError(command)

            scheduler = Scheduler(root, python, entry, run=runner,
                                  platform="win32", user_id=r"DOMAIN\person")
            self.assertFalse(scheduler.status())
            scheduler.enable()
            self.assertTrue(scheduler.status())
            create = next(command for command in calls if "/Create" in command)
            self.assertNotEqual(create[create.index("/XML") + 1], "-")
            self.assertNotIn("/F", create)

    def test_windows_query_failure_never_authorizes_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / "python.exe"
            entry = root / "team-update.py"
            python.write_text("")
            entry.write_text("")
            calls = []

            def runner(command, **kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(command, 5, b"", b"")

            scheduler = Scheduler(root, python, entry, run=runner,
                                  platform="win32", user_id=r"DOMAIN\person")
            with self.assertRaisesRegex(RuntimeError, "scheduler-status-unknown"):
                scheduler.enable()
            self.assertFalse(any("/Create" in command for command in calls))

    def test_windows_successful_malformed_inventory_is_not_absence_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / "python.exe"
            entry = root / "team-update.py"
            python.write_text("")
            entry.write_text("")

            def runner(command, **kwargs):
                if "/TN" in command:
                    return subprocess.CompletedProcess(command, 1, b"", b"")
                return subprocess.CompletedProcess(command, 0, b"unexpected informational output\n", b"")

            scheduler = Scheduler(root, python, entry, run=runner,
                                  platform="win32", user_id=r"DOMAIN\person")
            with self.assertRaisesRegex(RuntimeError, "scheduler-status-unknown"):
                scheduler.status()


if __name__ == "__main__":
    unittest.main()
