"""Pure-standard-library readers for Raspberry Pi / Linux system telemetry.

Every reader degrades gracefully off-Pi (and off-Linux): a source that is not
present yields ``None``/empty rather than raising, so the same code runs in
local development and on the device.
"""

import contextlib
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_VCGENCMD = shutil.which("vcgencmd")

# Bit positions reported by `vcgencmd get_throttled`.
# https://www.raspberrypi.com/documentation/computers/os.html#get_throttled
_THROTTLE_BITS = {
    0: "under_voltage_now",
    1: "arm_frequency_capped_now",
    2: "throttled_now",
    3: "soft_temp_limit_now",
    16: "under_voltage_occurred",
    17: "arm_frequency_capped_occurred",
    18: "throttled_occurred",
    19: "soft_temp_limit_occurred",
}


def _run(cmd: list[str]) -> Optional[str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


@dataclass
class HostInfo:
    hostname: str
    model: Optional[str]
    machine: str
    system: str
    release: str
    python_version: str
    uptime_seconds: Optional[float]


@dataclass
class CpuTemperature:
    celsius: Optional[float]
    source: str


@dataclass
class ThrottleStatus:
    raw: Optional[str]
    active_flags: list[str]
    healthy: bool


@dataclass
class LoadAverage:
    one: float
    five: float
    fifteen: float
    cpu_count: Optional[int]


@dataclass
class MemoryUsage:
    total_kb: Optional[int]
    available_kb: Optional[int]
    used_kb: Optional[int]
    used_percent: Optional[float]


@dataclass
class DiskUsage:
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float


@dataclass
class Process:
    pid: int
    name: str
    rss_kb: int


def uptime_seconds() -> Optional[float]:
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def host_info() -> HostInfo:
    model = None
    with contextlib.suppress(OSError):
        model = Path("/proc/device-tree/model").read_text().rstrip("\x00").strip()
    return HostInfo(
        hostname=platform.node(),
        model=model,
        machine=platform.machine(),
        system=platform.system(),
        release=platform.release(),
        python_version=platform.python_version(),
        uptime_seconds=uptime_seconds(),
    )


def cpu_temperature() -> CpuTemperature:
    try:
        millidegrees = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip())
        return CpuTemperature(celsius=round(millidegrees / 1000.0, 1), source="thermal_zone0")
    except (OSError, ValueError):
        pass
    if _VCGENCMD:
        out = _run([_VCGENCMD, "measure_temp"])  # "temp=49.4'C"
        if out and "=" in out:
            try:
                return CpuTemperature(
                    celsius=float(out.split("=")[1].split("'")[0]), source="vcgencmd"
                )
            except (ValueError, IndexError):
                pass
    return CpuTemperature(celsius=None, source="unavailable")


def throttle_status() -> ThrottleStatus:
    if not _VCGENCMD:
        return ThrottleStatus(raw=None, active_flags=[], healthy=True)
    out = _run([_VCGENCMD, "get_throttled"])  # "throttled=0x0"
    if not out or "=" not in out:
        return ThrottleStatus(raw=out, active_flags=[], healthy=True)
    try:
        value = int(out.split("=")[1], 16)
    except (ValueError, IndexError):
        return ThrottleStatus(raw=out, active_flags=[], healthy=True)
    flags = [name for bit, name in _THROTTLE_BITS.items() if value & (1 << bit)]
    healthy = not any(name.endswith("_now") for name in flags)
    return ThrottleStatus(raw=hex(value), active_flags=flags, healthy=healthy)


def load_average() -> LoadAverage:
    one, five, fifteen = os.getloadavg()
    return LoadAverage(round(one, 2), round(five, 2), round(fifteen, 2), os.cpu_count())


def memory_usage() -> MemoryUsage:
    try:
        lines = Path("/proc/meminfo").read_text().splitlines()
    except OSError:
        return MemoryUsage(None, None, None, None)
    info: dict[str, int] = {}
    for line in lines:
        key, _, rest = line.partition(":")
        try:
            info[key.strip()] = int(rest.strip().split()[0])
        except (ValueError, IndexError):
            continue
    total, available = info.get("MemTotal"), info.get("MemAvailable")
    if total is None or available is None or total == 0:
        return MemoryUsage(total, available, None, None)
    used = total - available
    return MemoryUsage(total, available, used, round(used / total * 100, 1))


def disk_usage(path: str = "/") -> DiskUsage:
    usage = shutil.disk_usage(path)
    used_percent = round(usage.used / usage.total * 100, 1) if usage.total else 0.0
    return DiskUsage(path, usage.total, usage.used, usage.free, used_percent)


def top_processes_by_memory(limit: int = 5) -> list[Process]:
    proc = Path("/proc")
    if not proc.exists():
        return []
    processes: list[Process] = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text()
        except OSError:
            continue  # process exited between listing and read
        name, rss = "?", None
        for line in status.splitlines():
            if line.startswith("Name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("VmRSS:"):
                with contextlib.suppress(ValueError, IndexError):
                    rss = int(line.split()[1])
        if rss is not None:
            processes.append(Process(int(entry.name), name, rss))
    processes.sort(key=lambda p: p.rss_kb, reverse=True)
    return processes[: max(1, limit)]
