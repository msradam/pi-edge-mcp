"""A read-only Raspberry Pi telemetry MCP server, built on AnodizeMCP."""

from dataclasses import asdict
from typing import Optional

from anodize_mcp import AnodizeMCP, StaticTokenVerifier

from . import gpio, metrics


def build_server(token: Optional[str] = None) -> AnodizeMCP:
    """Build the telemetry server.

    When ``token`` is set, the HTTP transport requires ``Authorization: Bearer
    <token>``; otherwise the server runs unauthenticated (local/dev only).
    """
    auth = None
    if token:
        auth = StaticTokenVerifier({token: {"client_id": "pi-edge", "scopes": ["telemetry"]}})

    mcp = AnodizeMCP(
        "pi-edge",
        instructions="Read-only Raspberry Pi system telemetry (temperature, throttling, "
        "load, memory, disk, processes).",
        auth=auth,
    )

    @mcp.tool
    def host_info() -> metrics.HostInfo:
        "Hostname, Pi model, CPU architecture, OS, Python version, and uptime."
        return metrics.host_info()

    @mcp.tool
    def cpu_temperature() -> metrics.CpuTemperature:
        "Current CPU temperature in degrees Celsius."
        return metrics.cpu_temperature()

    @mcp.tool
    def throttle_status() -> metrics.ThrottleStatus:
        "Under-voltage and throttling flags from `vcgencmd get_throttled`."
        return metrics.throttle_status()

    @mcp.tool
    def load_average() -> metrics.LoadAverage:
        "System load average over 1, 5, and 15 minutes, plus CPU count."
        return metrics.load_average()

    @mcp.tool
    def memory_usage() -> metrics.MemoryUsage:
        "RAM usage derived from /proc/meminfo."
        return metrics.memory_usage()

    @mcp.tool
    def disk_usage(path: str = "/") -> metrics.DiskUsage:
        "Disk usage for the filesystem containing `path`."
        return metrics.disk_usage(path)

    @mcp.tool
    def top_processes(limit: int = 5) -> list[metrics.Process]:
        "The `limit` processes using the most resident memory (RSS)."
        return metrics.top_processes_by_memory(limit)

    # Hardware tools backed by the gpiozero Python library. They report
    # `available: false` where gpiozero is not installed (e.g. local dev).
    @mcp.tool
    def ping_host(host: str) -> gpio.PingResult:
        "Check whether a host is reachable, via gpiozero's PingServer."
        return gpio.ping_host(host)

    @mcp.tool
    def read_gpio(pin: int) -> gpio.GpioReading:
        "Read the digital value of a GPIO pin (BCM numbering), via gpiozero."
        return gpio.read_gpio(pin)

    @mcp.tool
    def set_gpio(pin: int, on: bool) -> gpio.GpioWrite:
        "Drive a GPIO output pin (BCM numbering) high or low, via gpiozero."
        "Ensure nothing critical is wired to the pin; the pin stays driven until set off."
        return gpio.set_gpio(pin, on)

    @mcp.resource("telemetry://snapshot")
    def snapshot() -> dict:
        "A full telemetry snapshot in a single read."
        return {
            "host": asdict(metrics.host_info()),
            "cpu_temperature": asdict(metrics.cpu_temperature()),
            "throttle": asdict(metrics.throttle_status()),
            "load": asdict(metrics.load_average()),
            "memory": asdict(metrics.memory_usage()),
            "disk_root": asdict(metrics.disk_usage("/")),
        }

    @mcp.prompt
    def diagnose() -> str:
        "Ask the model to assess the Pi's health from a telemetry snapshot."
        return (
            "Read the telemetry://snapshot resource and assess whether this Raspberry Pi "
            "is healthy. Flag any active throttling or under-voltage, CPU temperature above "
            "80C, low available memory, or filesystems above 90% full, and recommend actions."
        )

    @mcp.custom_route("/health", methods=["GET"])
    def health(request):
        return {"status": "ok", "service": "pi-edge-mcp"}

    return mcp
