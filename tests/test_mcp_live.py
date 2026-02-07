"""Live MCP protocol test — verifies full handshake + tool calls."""

import asyncio
import json
import sys


async def send(proc, msg):
    """Send a JSON-RPC message and return parsed response."""
    raw = json.dumps(msg) + "\n"
    proc.stdin.write(raw.encode())
    await proc.stdin.drain()

    if msg.get("method") in ("initialized",):
        return None  # notification, no response

    line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
    return json.loads(line)


async def test_handshake():
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "ucw", "server",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        # 1. Initialize
        resp = await send(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            }
        })
        server_name = resp["result"]["serverInfo"]["name"]
        server_ver = resp["result"]["serverInfo"]["version"]
        assert server_name == "ucw", f"Expected ucw, got {server_name}"
        print(f"1/5 Handshake OK — {server_name} v{server_ver}")

        # 2. Initialized notification
        await send(proc, {"jsonrpc": "2.0", "method": "initialized"})
        print("2/5 Initialized notification sent")

        # 3. Tools list
        resp = await send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert len(tools) == 7, f"Expected 7 tools, got {len(tools)}"
        print(f"3/5 Tools registered ({len(tools)}):")
        for t in tools:
            n = t["name"]
            d = t["description"][:55]
            print(f"    {n}: {d}...")

        # 4. Call ucw_capture_stats
        resp = await send(proc, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "ucw_capture_stats", "arguments": {}}
        })
        content = resp["result"]["content"][0]["text"]
        print(f"4/5 ucw_capture_stats OK — {len(content)} chars")

        # 5. Call coherence_status (no SBERT needed)
        resp = await send(proc, {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "coherence_status", "arguments": {}}
        })
        content = resp["result"]["content"][0]["text"]
        print(f"5/5 coherence_status OK — {len(content)} chars")

        print()
        print("=" * 45)
        print("ALL MCP PROTOCOL TESTS PASSED")
        print("=" * 45)

    except asyncio.TimeoutError:
        print("TIMEOUT waiting for response")
        try:
            stderr_data = await asyncio.wait_for(proc.stderr.read(4096), timeout=2)
            if stderr_data:
                print("STDERR:", stderr_data.decode()[-500:])
        except asyncio.TimeoutError:
            pass
    except Exception as exc:
        print(f"ERROR: {exc}")
        import traceback
        traceback.print_exc()
    finally:
        proc.stdin.close()
        proc.terminate()
        await proc.wait()


if __name__ == "__main__":
    asyncio.run(test_handshake())
