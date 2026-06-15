"""Hardware tools backed by the gpiozero Python library.

This module is the point of the project: gpiozero is a real, widely used Python
library, and it (with a backend such as lgpio) is pure-Python / C, not Rust. So
it installs on a Pi Zero (armv6) -- `apt install python3-gpiozero python3-lgpio`,
or a C source build -- where FastMCP's Rust-based pydantic-core cannot. anodize
lets you wrap that library as MCP tools without hand-rolling JSON-RPC.

Imports are lazy and guarded so the server still runs where gpiozero is absent
(local development, or any non-Pi host); the tools just report unavailable.
"""

from dataclasses import dataclass
from typing import Optional

_UNAVAILABLE = (
    "gpiozero not available; install the 'pi' extra and a backend "
    "(e.g. `apt install python3-lgpio`) on a Raspberry Pi"
)

# Output pins are held open across calls so a pin stays driven until set back.
_outputs: dict[int, object] = {}


@dataclass
class PingResult:
    host: str
    reachable: Optional[bool]
    available: bool
    detail: str


@dataclass
class GpioReading:
    pin: int
    value: Optional[int]
    available: bool
    detail: str


@dataclass
class GpioWrite:
    pin: int
    state: Optional[bool]
    available: bool
    detail: str


def ping_host(host: str) -> PingResult:
    try:
        from gpiozero import PingServer
    except Exception:
        return PingResult(host, None, False, _UNAVAILABLE)
    try:
        server = PingServer(host)
        try:
            return PingResult(host, bool(server.value), True, "ok")
        finally:
            server.close()
    except Exception as exc:  # noqa: BLE001 - report any backend error to the caller
        return PingResult(host, None, True, f"{type(exc).__name__}: {exc}")


def read_gpio(pin: int) -> GpioReading:
    try:
        from gpiozero import DigitalInputDevice
    except Exception:
        return GpioReading(pin, None, False, _UNAVAILABLE)
    try:
        device = DigitalInputDevice(pin)
        try:
            return GpioReading(pin, int(device.value), True, "ok")
        finally:
            device.close()
    except Exception as exc:  # noqa: BLE001
        return GpioReading(pin, None, True, f"{type(exc).__name__}: {exc}")


def set_gpio(pin: int, on: bool) -> GpioWrite:
    try:
        from gpiozero import DigitalOutputDevice
    except Exception:
        return GpioWrite(pin, None, False, _UNAVAILABLE)
    try:
        device = _outputs.get(pin)
        if device is None:
            device = DigitalOutputDevice(pin)
            _outputs[pin] = device
        device.value = 1 if on else 0
        return GpioWrite(pin, bool(device.value), True, "ok")
    except Exception as exc:  # noqa: BLE001
        return GpioWrite(pin, None, True, f"{type(exc).__name__}: {exc}")
