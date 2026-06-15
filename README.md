# pi-edge-mcp

A read-only Raspberry Pi telemetry server that speaks the [Model Context
Protocol](https://modelcontextprotocol.io). An MCP client or agent can query the
Pi's temperature, throttling state, load, memory, disk, and top processes over
HTTP or stdio.

Built on [AnodizeMCP](https://pypi.org/project/anodize-mcp/), so the whole
install is pure Python with no compiled extensions.

## Why pure Python here

The official MCP SDK and FastMCP depend on `pydantic-core`, which is compiled
Rust. On a 64-bit Pi (aarch64) that is a non-issue: a prebuilt `pydantic-core`
wheel exists and FastMCP installs fine. The pure-Python stack matters when:

- You run an **ARMv6** board (Pi Zero / Zero W / Pi 1). `pydantic-core` publishes
  no ARMv6 wheel (manylinux does not define ARMv6), so installing FastMCP there
  falls back to building `pydantic-core` with Rust, which a stock Pi Zero cannot
  do. AnodizeMCP installs with no build step. (A 32-bit ARMv7 board such as a Pi
  2/3/4 on a 32-bit OS *does* get a prebuilt `pydantic-core` wheel, so FastMCP
  installs there; ARMv6 is the case that has none.)
- You want a **small, fast install** on flash storage: one pure-Python
  dependency (`uvicorn`) instead of `pydantic` and its tree.

On a 64-bit or ARMv7 Pi the benefit is leanness; on ARMv6 it is the difference
between installing and not.

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
```

Requires Python 3.9+. The only third-party dependencies are `anodize-mcp` and
`uvicorn`, both pure Python.

For the GPIO/hardware tools, install the `pi` extra and a backend. On a Pi the
backend comes from `apt` (it is C, packaged per-arch including armv6):

```sh
sudo apt install -y python3-lgpio          # GPIO backend (C, not Rust)
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e ".[pi]"           # gpiozero (pure Python)
```

## Run

```sh
# HTTP on 0.0.0.0:8080 (default), no auth
pi-edge-mcp

# HTTP with a bearer token required
PI_EDGE_MCP_TOKEN=changeme pi-edge-mcp

# stdio (for a local MCP client that launches the process)
PI_EDGE_MCP_TRANSPORT=stdio pi-edge-mcp
```

Configuration (environment variables):

| Variable | Default | Purpose |
|---|---|---|
| `PI_EDGE_MCP_TOKEN` | unset | Bearer token required on the HTTP transport. Unset = open (dev only). |
| `PI_EDGE_MCP_HOST` | `0.0.0.0` | HTTP bind address. |
| `PI_EDGE_MCP_PORT` | `8080` | HTTP bind port. |
| `PI_EDGE_MCP_TRANSPORT` | `http` | `http` or `stdio`. |

## Tools, resource, and prompt

- `host_info` — hostname, Pi model, architecture, OS, Python, uptime
- `cpu_temperature` — CPU temperature in Celsius
- `throttle_status` — under-voltage / throttling flags from `vcgencmd get_throttled`
- `load_average` — 1/5/15-minute load and CPU count
- `memory_usage` — RAM usage from `/proc/meminfo`
- `disk_usage(path="/")` — filesystem usage
- `top_processes(limit=5)` — processes by resident memory
- resource `telemetry://snapshot` — all of the above in one read
- prompt `diagnose` — asks the model to assess health from the snapshot

The metric readers above use only the standard library. The hardware tools below
use the [gpiozero](https://gpiozero.readthedocs.io) library:

- `ping_host(host)` — reachability check via gpiozero's `PingServer`
- `read_gpio(pin)` — read a GPIO input pin (BCM numbering)
- `set_gpio(pin, on)` — drive a GPIO output pin high/low (the pin stays driven
  until set off; make sure nothing critical is wired to it)

Off-Pi, the Pi-specific readers return null/empty and the gpiozero tools report
`available: false` rather than failing, so the server runs in local development too.

## Why gpiozero is the point

A telemetry server reading `/proc` could be hand-written as raw JSON-RPC; it does
not justify a framework. The hardware tools do. `gpiozero` is a real, widely used
Python library, and it (with a backend like `lgpio`) is pure-Python / C, **not
Rust**, so it installs on a Pi Zero (armv6) via `apt install python3-gpiozero
python3-lgpio` where FastMCP's `pydantic-core` cannot. anodize lets you wrap that
library as typed MCP tools, with transports, sessions, and auth, without
hand-rolling the protocol. That is the niche: the Python library ecosystem plus
MCP framework ergonomics, on hardware the Rust-based MCP stack cannot reach.

## Deploy on a Pi (systemd)

```sh
sudo mkdir -p /opt/pi-edge-mcp
sudo rsync -a --exclude .venv ./ /opt/pi-edge-mcp/
sudo python3 -m venv /opt/pi-edge-mcp/.venv
sudo /opt/pi-edge-mcp/.venv/bin/pip install /opt/pi-edge-mcp

echo "PI_EDGE_MCP_TOKEN=$(openssl rand -hex 16)" | sudo tee /etc/pi-edge-mcp.env
sudo cp deploy/pi-edge-mcp.service /etc/systemd/system/
sudo systemctl enable --now pi-edge-mcp
```

Health check: `curl http://<pi>:8080/health`.

## Connect a client

Any MCP client that supports Streamable HTTP. With the `anodize-mcp` client:

```python
import asyncio
from anodize_mcp import Client
from anodize_mcp.client.transports import StreamableHttpTransport

async def main():
    transport = StreamableHttpTransport(
        "http://<pi>:8080/mcp",
        headers={"Authorization": "Bearer <token>"},
    )
    async with Client(transport=transport) as c:
        print((await c.call_tool("cpu_temperature", {})).data)

asyncio.run(main())
```

## Development

```sh
.venv/bin/pip install -e . ruff
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff check .
```

## License

MIT.
