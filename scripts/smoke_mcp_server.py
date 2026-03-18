#!/usr/bin/env python3
import argparse
import asyncio
import json
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the Omnishot MCP server over stdio.")
    parser.add_argument(
        "--python-bin",
        default=str(ROOT_DIR / ".venv/bin/python"),
    )
    parser.add_argument(
        "--server-module",
        default="app.mcp_server",
    )
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8000",
    )
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> int:
    server = StdioServerParameters(
        command=args.python_bin,
        args=[
            "-m",
            args.server_module,
            "--transport",
            "stdio",
            "--api-base-url",
            args.api_base_url,
        ],
        cwd=str(ROOT_DIR),
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            health = await session.call_tool("health", {})
            if health.structuredContent is not None:
                health_payload = health.structuredContent
            else:
                health_payload = [getattr(item, "text", str(item)) for item in health.content]
            print("tools:", [tool.name for tool in tools.tools])
            print("resources:", [resource.uri for resource in resources.resources])
            print("health:", json.dumps(health_payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
