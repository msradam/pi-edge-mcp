import asyncio
import unittest

from anodize_mcp import Client

from pi_edge_mcp.server import build_server

_EXPECTED_TOOLS = {
    "host_info",
    "cpu_temperature",
    "throttle_status",
    "load_average",
    "memory_usage",
    "disk_usage",
    "top_processes",
}


class PiEdgeServerTest(unittest.TestCase):
    def test_tools_resource_and_prompt_are_registered(self):
        async def go():
            async with Client(build_server()) as client:
                tool_names = {t["name"] for t in await client.list_tools()}
                self.assertGreaterEqual(tool_names, _EXPECTED_TOOLS)
                resources = {r["uri"] for r in await client.list_resources()}
                self.assertIn("telemetry://snapshot", resources)
                prompts = {p["name"] for p in await client.list_prompts()}
                self.assertIn("diagnose", prompts)

        asyncio.run(go())

    def test_cross_platform_tools_return_real_data(self):
        async def go():
            async with Client(build_server()) as client:
                disk = (await client.call_tool("disk_usage", {"path": "/"})).data
                self.assertGreater(disk["total_bytes"], 0)
                self.assertEqual(disk["path"], "/")

                load = (await client.call_tool("load_average", {})).data
                self.assertIn("one", load)
                self.assertTrue(load["cpu_count"] is None or load["cpu_count"] >= 1)

        asyncio.run(go())

    def test_auth_required_when_token_set(self):
        mcp = build_server(token="secret-token")
        self.assertIsNotNone(mcp.auth)

    def test_pi_specific_tools_degrade_gracefully(self):
        # Off-Pi these return null/empty without raising; on the device they carry real values.
        async def go():
            async with Client(build_server()) as client:
                temp = (await client.call_tool("cpu_temperature", {})).data
                self.assertIn("source", temp)
                throttle = (await client.call_tool("throttle_status", {})).data
                self.assertIn("healthy", throttle)

        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
