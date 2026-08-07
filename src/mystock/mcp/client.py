"""Bare MCP client for the mystock warehouse — no LLM involved, just a thin CLI over
the same 8 read-only tools the server exposes (see server.py). Spawns the server as a
stdio subprocess, same as any MCP host would, so this exercises the real protocol path.

Fully offline: everything the server touches (local Postgres, cached embedding models)
works without network access — see server.py's module docstring for why.

Usage:
    python -m mystock.mcp.client                                    # interactive REPL
    python -m mystock.mcp.client list_tables
    python -m mystock.mcp.client describe_table schema=main table=fact_daily_prices
    python -m mystock.mcp.client get_stock_history symbol=RELIANCE from_date=2026-08-01
    python -m mystock.mcp.client run_sql query="SELECT count(*) FROM main.dim_security"
"""
import sys

import anyio

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

SERVER_PARAMS = StdioServerParameters(command=sys.executable, args=["-m", "mystock.mcp.server"])


def parse_arg_value(raw):
    for cast in (int, float):
        try:
            return cast(raw)
        except ValueError:
            pass
    return raw


def parse_kwargs(pairs):
    kwargs = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        if not _:
            raise ValueError(f"expected key=value, got {pair!r}")
        kwargs[key] = parse_arg_value(value)
    return kwargs


def print_result(result):
    if result.is_error:
        print("ERROR:", file=sys.stderr)
    for block in result.content:
        print(getattr(block, "text", block))


async def call_tool(session, name, kwargs):
    result = await session.call_tool(name, kwargs)
    print_result(result)


async def list_tools(session):
    listed = await session.list_tools()
    for tool in listed.tools:
        print(f"{tool.name}: {tool.description.splitlines()[0] if tool.description else ''}")


async def repl(session):
    tools = {t.name for t in (await session.list_tools()).tools}
    print("mystock MCP client — type a tool name + key=value args, 'tools' to list, 'quit' to exit")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("quit", "exit"):
            break
        if line == "tools":
            await list_tools(session)
            continue
        name, *rest = line.split()
        if name not in tools:
            print(f"unknown tool {name!r} — type 'tools' to list available tools", file=sys.stderr)
            continue
        try:
            kwargs = parse_kwargs(rest)
        except ValueError as e:
            print(f"bad argument: {e}", file=sys.stderr)
            continue
        await call_tool(session, name, kwargs)


async def main():
    async with stdio_client(SERVER_PARAMS) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            args = sys.argv[1:]
            if not args:
                await repl(session)
            elif args == ["list_tools"] or args == ["tools"]:
                await list_tools(session)
            else:
                name, *rest = args
                kwargs = parse_kwargs(rest)
                await call_tool(session, name, kwargs)


if __name__ == "__main__":
    anyio.run(main)
