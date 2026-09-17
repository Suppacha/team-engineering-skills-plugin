"""Per-user native scheduler definitions and ownership-safe lifecycle."""

from __future__ import annotations

import getpass
import hashlib
import csv
import io
import locale
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


LABEL = "com.suppacha.team-engineering-skills-updater"
TASK_NAMESPACE = r"\TeamEngineeringSkillsUpdater"
INTERVAL_SECONDS = 4 * 60 * 60
XML_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
MAX_OUTPUT = 256 * 1024
_UNKNOWN = object()


def _valid_text(value: str) -> bool:
    return (isinstance(value, str) and bool(value)
            and all(character in "\t\n\r" or ord(character) >= 32 for character in value))


def _validate(values) -> None:
    if not values or not all(_valid_text(value) for value in values):
        raise ValueError("invalid-scheduler-value")


def launch_agent(argv: list[str]) -> bytes:
    """Return one deterministic, user-scoped LaunchAgent plist."""
    _validate(argv)
    return plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": list(argv),
        "RunAtLoad": True,
        "StartInterval": INTERVAL_SECONDS,
        "ProcessType": "Background",
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
    }, fmt=plistlib.FMT_XML, sort_keys=True)


def windows_task(argv: list[str], user_id: str) -> bytes:
    """Return Task Scheduler XML for logon plus a four-hour periodic trigger."""
    _validate([*argv, user_id])
    ET.register_namespace("", XML_NS)
    task = ET.Element(f"{{{XML_NS}}}Task", {"version": "1.4"})
    registration = ET.SubElement(task, f"{{{XML_NS}}}RegistrationInfo")
    ET.SubElement(registration, f"{{{XML_NS}}}Description").text = \
        "Team-managed Codex personal plugin updater"
    triggers = ET.SubElement(task, f"{{{XML_NS}}}Triggers")
    logon = ET.SubElement(triggers, f"{{{XML_NS}}}LogonTrigger")
    ET.SubElement(logon, f"{{{XML_NS}}}Enabled").text = "true"
    ET.SubElement(logon, f"{{{XML_NS}}}UserId").text = user_id
    timer = ET.SubElement(triggers, f"{{{XML_NS}}}TimeTrigger")
    repetition = ET.SubElement(timer, f"{{{XML_NS}}}Repetition")
    ET.SubElement(repetition, f"{{{XML_NS}}}Interval").text = "PT4H"
    ET.SubElement(repetition, f"{{{XML_NS}}}StopAtDurationEnd").text = "false"
    ET.SubElement(timer, f"{{{XML_NS}}}StartBoundary").text = "2000-01-01T00:00:00"
    ET.SubElement(timer, f"{{{XML_NS}}}Enabled").text = "true"
    principals = ET.SubElement(task, f"{{{XML_NS}}}Principals")
    principal = ET.SubElement(principals, f"{{{XML_NS}}}Principal", {"id": "Author"})
    ET.SubElement(principal, f"{{{XML_NS}}}UserId").text = user_id
    ET.SubElement(principal, f"{{{XML_NS}}}LogonType").text = "InteractiveToken"
    ET.SubElement(principal, f"{{{XML_NS}}}RunLevel").text = "LeastPrivilege"
    settings = ET.SubElement(task, f"{{{XML_NS}}}Settings")
    ET.SubElement(settings, f"{{{XML_NS}}}MultipleInstancesPolicy").text = "IgnoreNew"
    ET.SubElement(settings, f"{{{XML_NS}}}DisallowStartIfOnBatteries").text = "false"
    ET.SubElement(settings, f"{{{XML_NS}}}StopIfGoingOnBatteries").text = "false"
    ET.SubElement(settings, f"{{{XML_NS}}}AllowHardTerminate").text = "true"
    ET.SubElement(settings, f"{{{XML_NS}}}StartWhenAvailable").text = "true"
    ET.SubElement(settings, f"{{{XML_NS}}}Enabled").text = "true"
    actions = ET.SubElement(task, f"{{{XML_NS}}}Actions", {"Context": "Author"})
    execute = ET.SubElement(actions, f"{{{XML_NS}}}Exec")
    ET.SubElement(execute, f"{{{XML_NS}}}Command").text = argv[0]
    ET.SubElement(execute, f"{{{XML_NS}}}Arguments").text = subprocess.list2cmdline(argv[1:])
    return ET.tostring(task, encoding="utf-8", xml_declaration=True)


class Scheduler:
    def __init__(self, root: Path, python: Path, entry: Path, run=None, *,
                 platform=None, uid=None, launch_agents=None, user_id=None):
        _validate([str(root), str(python), str(entry)])
        if not all(isinstance(value, Path) and value.is_absolute()
                   for value in (root, python, entry)):
            raise ValueError("invalid-scheduler-path")
        self.root = root
        self.python = python
        self.entry = entry
        self._run = run or subprocess.run
        self.platform = platform or sys.platform
        self.uid = os.getuid() if uid is None and hasattr(os, "getuid") else uid
        self.launch_agents = launch_agents or Path.home() / "Library/LaunchAgents"
        self.user_id = user_id or self._os_user_id()

    @staticmethod
    def _os_user_id():
        name = getpass.getuser()
        domain = os.environ.get("USERDOMAIN")
        return domain + "\\" + name if domain else name

    @property
    def argv(self):
        return [str(self.python), str(self.entry), "check", "--state-dir", str(self.root)]

    @property
    def plist_path(self):
        return self.launch_agents / (LABEL + ".plist")

    @property
    def task_name(self):
        digest = hashlib.sha256(self.user_id.encode("utf-8")).hexdigest()[:16]
        return TASK_NAMESPACE + "\\" + digest

    def _call(self, command, *, input_data=None):
        try:
            result = self._run(command, input=input_data, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=30, check=False)
        except (OSError, subprocess.SubprocessError):
            raise RuntimeError("scheduler-command-failed") from None
        if len(result.stdout or b"") > MAX_OUTPUT or len(result.stderr or b"") > MAX_OUTPUT:
            raise RuntimeError("scheduler-command-failed")
        return result

    def _mac_owned(self):
        path = self.plist_path
        if not path.exists():
            return False
        try:
            return path.is_file() and not path.is_symlink() and path.read_bytes() == launch_agent(self.argv)
        except OSError:
            raise RuntimeError("scheduler-readback-failed") from None

    def _mac_loaded_argv(self):
        result = self._call(["launchctl", "print", f"gui/{self.uid}/{LABEL}"])
        if result.returncode != 0:
            return None
        try:
            raw = result.stdout or b""
            text = raw if isinstance(raw, str) else raw.decode("utf-8", "strict")
            lines = text.splitlines()
            programs = [line.strip()[len("program = "):] for line in lines
                        if line.strip().startswith("program = ")]
            start = [index for index, line in enumerate(lines)
                     if line.strip() == "arguments = {"]
            if len(programs) != 1 or len(start) != 1:
                raise ValueError
            arguments = []
            for line in lines[start[0] + 1:]:
                if line.strip() == "}":
                    break
                arguments.append(line.strip())
            else:
                raise ValueError
            if not arguments or arguments[0] != programs[0]:
                raise ValueError
            return arguments
        except (UnicodeError, ValueError):
            raise RuntimeError("scheduler-collision") from None

    def _windows_read(self):
        result = self._call(["schtasks.exe", "/Query", "/TN", self.task_name, "/XML"])
        if result.returncode == 0:
            return result.stdout
        inventory = self._call(["schtasks.exe", "/Query", "/FO", "CSV", "/NH"])
        if inventory.returncode != 0:
            return _UNKNOWN
        try:
            raw = inventory.stdout or b""
            text = raw if isinstance(raw, str) else raw.decode(locale.getpreferredencoding(False), "strict")
            rows = [row for row in csv.reader(io.StringIO(text)) if row]
            if any(len(row) != 3 or not row[0].startswith("\\")
                   or any(ord(character) < 32 for character in row[0]) for row in rows):
                return _UNKNOWN
            names = {row[0].casefold() for row in rows}
        except (UnicodeError, csv.Error, TypeError):
            return _UNKNOWN
        # Successful read-only inventory is the locale-independent absence
        # proof: only the task-name column is inspected, never error prose.
        return _UNKNOWN if self.task_name.casefold() in names else None

    def _owned(self):
        if self.platform == "darwin":
            return self._mac_owned()
        if self.platform == "win32":
            existing = self._windows_read()
            if existing is _UNKNOWN:
                raise RuntimeError("scheduler-status-unknown")
            if existing is None:
                return False
            return self._windows_matches(existing, windows_task(self.argv, self.user_id))
        raise RuntimeError("unsupported-platform")

    @staticmethod
    def _canonical_xml(raw):
        try:
            root = ET.fromstring(raw)
            prefix = "{" + XML_NS + "}"
            defaults = {"Priority": "7", "AllowStartOnDemand": "true",
                        "RunOnlyIfIdle": "false", "WakeToRun": "false",
                        "RunOnlyIfNetworkAvailable": "false", "ExecutionTimeLimit": "PT72H"}
            def semantic(node, parent=""):
                tag = node.tag.removeprefix(prefix)
                text = (node.text or "").strip()
                # Only leaf values with documented harmless scheduler defaults
                # may disappear. Unknown fields and duplicate nodes still differ.
                if (parent == "Settings" and not node.attrib and not list(node)
                        and defaults.get(tag) == text):
                    return None
                if parent == "RegistrationInfo" and tag in {"Date", "Author", "URI"}:
                    return None
                if tag == "UserId":
                    text = text.casefold()
                children = [value for child in node if (value := semantic(child, tag)) is not None]
                return (node.tag, tuple(sorted(node.attrib.items())), text, tuple(sorted(children)))
            return semantic(root)
        except (ET.ParseError, ValueError):
            raise RuntimeError("scheduler-collision") from None

    def _windows_matches(self, existing, expected):
        if self._canonical_xml(existing) == self._canonical_xml(expected):
            return True
        # Task Scheduler may serialize an account name as its SID. Resolve
        # both identities through Windows, never equate names heuristically.
        if os.name != "nt":
            return False
        try:
            roots = [ET.fromstring(raw) for raw in (existing, expected)]
            for root in roots:
                for user in root.iter("{" + XML_NS + "}UserId"):
                    user.text = self._sid(user.text)
            return self._canonical_xml(ET.tostring(roots[0])) == self._canonical_xml(ET.tostring(roots[1]))
        except (ET.ParseError, ValueError, OSError):
            return False

    @staticmethod
    def _sid(account):
        import ctypes
        from ctypes import wintypes
        if account and account.upper().startswith("S-1-"):
            return account.upper()
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        lookup = advapi.LookupAccountNameW
        lookup.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID,
                           ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR,
                           ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
        lookup.restype = wintypes.BOOL
        size, domain_size, kind = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
        lookup(None, account, None, ctypes.byref(size), None, ctypes.byref(domain_size), ctypes.byref(kind))
        if not 0 < size.value <= 1024 or domain_size.value > 32768:
            raise ValueError("scheduler-collision")
        sid, domain = ctypes.create_string_buffer(size.value), ctypes.create_unicode_buffer(domain_size.value)
        if not lookup(None, account, sid, ctypes.byref(size), domain, ctypes.byref(domain_size), ctypes.byref(kind)):
            raise ValueError("scheduler-collision")
        convert = advapi.ConvertSidToStringSidW
        convert.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]
        convert.restype = wintypes.BOOL
        result = wintypes.LPWSTR()
        if not convert(sid, ctypes.byref(result)):
            raise ValueError("scheduler-collision")
        try:
            return result.value
        finally:
            free = ctypes.WinDLL("kernel32").LocalFree
            free.argtypes = [wintypes.HLOCAL]
            free.restype = wintypes.HLOCAL
            free(ctypes.cast(result, wintypes.HLOCAL))

    def status(self) -> bool:
        if not self._owned():
            return False
        if self.platform == "darwin":
            return self._mac_loaded_argv() == self.argv
        return True

    def enable(self) -> None:
        if self.platform == "darwin":
            if self.plist_path.exists() and not self._mac_owned():
                raise RuntimeError("scheduler-collision")
            loaded = self._mac_loaded_argv()
            if ((not self.plist_path.exists() and loaded is not None)
                    or (loaded is not None and loaded != self.argv)):
                raise RuntimeError("scheduler-collision")
            self.launch_agents.mkdir(mode=0o700, parents=True, exist_ok=True)
            raw = launch_agent(self.argv)
            descriptor, temporary = tempfile.mkstemp(prefix="." + LABEL, dir=self.launch_agents)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(raw)
                os.chmod(temporary, 0o600)
                os.replace(temporary, self.plist_path)
            finally:
                try: os.unlink(temporary)
                except FileNotFoundError: pass
            # Never trust label presence as proof of the loaded argv.  Once the
            # exact owned plist is on disk, replace any stale same-label job and
            # prove that this bootstrap is the one now visible.
            if loaded is not None:
                result = self._call(["launchctl", "bootout", f"gui/{self.uid}", str(self.plist_path)])
                if result.returncode != 0:
                    raise RuntimeError("scheduler-command-failed")
            result = self._call(["launchctl", "bootstrap", f"gui/{self.uid}", str(self.plist_path)])
            if result.returncode != 0 or self._mac_loaded_argv() != self.argv:
                raise RuntimeError("scheduler-readback-failed")
            return
        if self.platform == "win32":
            existing = self._windows_read()
            expected = windows_task(self.argv, self.user_id)
            if existing is _UNKNOWN:
                raise RuntimeError("scheduler-status-unknown")
            if existing is not None and not self._windows_matches(existing, expected):
                raise RuntimeError("scheduler-collision")
            if existing is None:
                descriptor, temporary = tempfile.mkstemp(prefix=".task-", suffix=".xml",
                                                          dir=self.root)
                try:
                    with os.fdopen(descriptor, "wb") as handle:
                        descriptor = -1
                        handle.write(expected)
                    os.chmod(temporary, 0o600)
                    result = self._call(["schtasks.exe", "/Create", "/TN", self.task_name,
                                         "/XML", temporary])
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
                    try: os.unlink(temporary)
                    except FileNotFoundError: pass
                if result.returncode != 0:
                    raise RuntimeError("scheduler-status-unknown")
            if not self.status():
                raise RuntimeError("scheduler-readback-failed")
            return
        raise RuntimeError("unsupported-platform")

    def disable(self) -> None:
        existing = None if self.platform == "darwin" else self._windows_read()
        if existing is _UNKNOWN:
            raise RuntimeError("scheduler-status-unknown")
        exists = self.plist_path.exists() if self.platform == "darwin" else existing is not None
        if not exists:
            return
        if not self._owned():
            raise RuntimeError("scheduler-collision")
        if self.platform == "darwin":
            loaded = self._mac_loaded_argv()
            if loaded is not None and loaded != self.argv:
                raise RuntimeError("scheduler-collision")
            if loaded is not None:
                result = self._call(["launchctl", "bootout", f"gui/{self.uid}", str(self.plist_path)])
                if result.returncode != 0:
                    raise RuntimeError("scheduler-command-failed")
            self.plist_path.unlink()
            if self.status():
                raise RuntimeError("scheduler-readback-failed")
        else:
            result = self._call(["schtasks.exe", "/Delete", "/TN", self.task_name, "/F"])
            if result.returncode != 0 or self._windows_read() is not None:
                raise RuntimeError("scheduler-readback-failed")
