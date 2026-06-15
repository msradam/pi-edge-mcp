# pi-edge-mcp

Expose a Raspberry Pi's telemetry and GPIO to AI agents over the [Model Context
Protocol](https://modelcontextprotocol.io). Pure Python, no Rust.

A small MCP server for Raspberry Pi and other no-Rust hosts. It gives an MCP
client or agent read-only system telemetry (temperature, throttling, load,
memory, disk, processes) and gpiozero-backed hardware tools (ping, GPIO read,
GPIO drive), over HTTP or stdio. Built on
[AnodizeMCP](https://pypi.org/project/anodize-mcp/), so the install is pure
Python with no compiled extensions.

## Install

```sh
git clone https://github.com/msradam/pi-edge-mcp && cd pi-edge-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

Python 3.9+. The only dependencies are `anodize-mcp` and `uvicorn`, both pure
Python. (GPIO tools need one extra step — see [GPIO](#gpio-hardware-tools).)

## Quickstart

```sh
.venv/bin/pi-edge-mcp            # serves Streamable HTTP on 0.0.0.0:8080
curl http://localhost:8080/health
# {"status": "ok", "service": "pi-edge-mcp"}
```

Call a tool from any MCP client (here, the `anodize-mcp` client):

```python
import asyncio
from anodize_mcp import Client
from anodize_mcp.client.transports import StreamableHttpTransport

async def main():
    transport = StreamableHttpTransport("http://localhost:8080/mcp")
    async with Client(transport=transport) as c:
        print((await c.call_tool("cpu_temperature", {})).data)
        # {'celsius': 51.8, 'source': 'thermal_zone0'}

asyncio.run(main())
```

For a remote Pi behind a token, set `PI_EDGE_MCP_TOKEN` (below) and pass
`headers={"Authorization": "Bearer <token>"}` to the transport.

## Tools, resource, and prompt

Telemetry (standard library only):

- `host_info` — hostname, Pi model, architecture, OS, Python, uptime
- `cpu_temperature` — CPU temperature in Celsius
- `throttle_status` — under-voltage / throttling flags from `vcgencmd get_throttled`
- `load_average` — 1/5/15-minute load and CPU count
- `memory_usage` — RAM usage from `/proc/meminfo`
- `disk_usage(path="/")` — filesystem usage
- `top_processes(limit=5)` — processes by resident memory
- resource `telemetry://snapshot` — all of the above in one read
- prompt `diagnose` — asks the model to assess health from the snapshot

Hardware (via the [gpiozero](https://gpiozero.readthedocs.io) library):

- `ping_host(host)` — reachability check via gpiozero's `PingServer`
- `read_gpio(pin)` — read a GPIO input pin (BCM numbering)
- `set_gpio(pin, on)` — drive a GPIO output pin high/low (stays driven until set
  off; make sure nothing critical is wired to the pin)

Off-Pi, the Pi-specific readers return null/empty and the gpiozero tools report
`available: false` instead of failing, so the server also runs in local development.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PI_EDGE_MCP_TOKEN` | unset | Bearer token required on the HTTP transport. Unset = open (dev only). |
| `PI_EDGE_MCP_HOST` | `0.0.0.0` | HTTP bind address. |
| `PI_EDGE_MCP_PORT` | `8080` | HTTP bind port. |
| `PI_EDGE_MCP_TRANSPORT` | `http` | `http`, or `stdio` for a client that launches the process. |

## GPIO (hardware tools)

The GPIO tools need `gpiozero` and a backend. On a Pi the backend comes from
`apt` (it is C, packaged per-arch including ARMv6 — not Rust):

```sh
sudo apt install -y python3-lgpio
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e ".[pi]"
```

This is the point of the project. `gpiozero` is a real Python library, and it
plus `lgpio` are pure-Python / C, so they install on a Pi Zero (ARMv6) where
FastMCP's Rust `pydantic-core` cannot. pi-edge-mcp wraps that library as typed
MCP tools — with transports, sessions, and auth — without hand-rolling the
protocol.

## Why pure Python

The official MCP SDK and FastMCP depend on `pydantic-core` (compiled Rust). That
matters by platform:

- **ARMv6** (Pi Zero / Zero W / Pi 1): no `pydantic-core` wheel exists and a
  stock board has no Rust, so FastMCP cannot install. pi-edge-mcp can. This is
  the case with no workaround.
- **ARMv7 / aarch64** (Pi 2/3/4/5): `pydantic-core` ships wheels, so FastMCP
  installs too; here the benefit is a smaller, faster install.

The barrier is Rust specifically, not compiled code — C extensions like `lgpio`
build and install fine.

## Deploy on a Pi (systemd)

```sh
sudo mkdir -p /opt/pi-edge-mcp
sudo rsync -a --exclude .venv ./ /opt/pi-edge-mcp/
sudo python3 -m venv --system-site-packages /opt/pi-edge-mcp/.venv
sudo /opt/pi-edge-mcp/.venv/bin/pip install /opt/pi-edge-mcp

echo "PI_EDGE_MCP_TOKEN=$(openssl rand -hex 16)" | sudo tee /etc/pi-edge-mcp.env
sudo cp deploy/pi-edge-mcp.service /etc/systemd/system/
sudo systemctl enable --now pi-edge-mcp
```

Health check: `curl http://<pi>:8080/health`. The unit uses `ProtectSystem=full`
(not `strict`) so the lgpio GPIO backend can load; see comments in
[`deploy/pi-edge-mcp.service`](deploy/pi-edge-mcp.service).

TLS terminates at a reverse proxy; the server speaks plain HTTP behind it.

## Development

```sh
.venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests
uvx ruff check .
```

## License

MIT. See [LICENSE](LICENSE).
