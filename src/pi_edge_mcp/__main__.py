"""Run the Pi telemetry server.

Configuration is read from the environment:

- ``PI_EDGE_MCP_TOKEN``     bearer token required on the HTTP transport (unset = open)
- ``PI_EDGE_MCP_HOST``      bind address (default 0.0.0.0)
- ``PI_EDGE_MCP_PORT``      bind port (default 8080)
- ``PI_EDGE_MCP_TRANSPORT`` "http" (default) or "stdio"
"""

import os

from .server import build_server


def main() -> None:
    token = os.environ.get("PI_EDGE_MCP_TOKEN")
    transport = os.environ.get("PI_EDGE_MCP_TRANSPORT", "http")
    server = build_server(token=token)

    if transport == "stdio":
        server.run("stdio")
        return

    host = os.environ.get("PI_EDGE_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("PI_EDGE_MCP_PORT", "8080"))
    # Bearer auth is the access gate; allow any Origin so non-browser MCP clients
    # on the network are not blocked. Put it behind your own network controls.
    server.run("http", host=host, port=port, stateless_http=True, allowed_origins={"*"})


if __name__ == "__main__":
    main()
