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

- You run a **32-bit Pi OS** or an older **ARMv6** board (Pi Zero / Zero W /
  Pi 1). `pydantic-core` ships no wheel for ARMv6, and building it with Rust on
  that hardware is slow and fragile. AnodizeMCP installs with no build step.
- You want a **small, fast install** on flash storage: one pure-Python
  dependency (`uvicorn`) instead of `pydantic` and its tree.

On this hardware the benefit is leanness; on ARMv6 it is the difference between
installing and not.

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
```

Requires Python 3.9+. The only third-party dependencies are `anodize-mcp` and
`uvicorn`, both pure Python.

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

Off-Pi, the Pi-specific readers return null/empty rather than failing, so the
server runs in local development too.

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
