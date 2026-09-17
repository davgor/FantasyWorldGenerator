# Unreal Editor MCP (UnrealWorldGen)

Unity MCP (`user-unityMCP` on port 8080) is the wrong engine. UnrealWorldGen needs its own editor bridge.

## Layout

- Plugin lives in sibling `UnrealWorldGen/Plugins/UnrealMCP` (from [chongdashu/unreal-mcp](https://github.com/chongdashu/unreal-mcp), MIT, experimental).
- Python MCP stdio server is `UnrealWorldGen/Tools/unreal-mcp-python` (`uv run unreal_mcp_server.py`).
- Cursor project config: FantasyWorldGenerator `.cursor/mcp.json` key `unrealMCP`.
- Plugin TCP is `localhost:55557` while the editor is open.

## Enable

1. Open `UnrealWorldGen.uproject` in Unreal 5.8 (first load compiles UnrealMCP).
2. Confirm **UnrealMCP** and **EditorScriptingUtilities** are enabled; restart if prompted.
3. Reload Cursor MCP so `unrealMCP` tools appear. They will not appear until the editor TCP server is listening.
4. Coordinator verifies health before any worker mutates the editor. One editor owner at a time.

This is tooling, not PK03/PK04 evidence.
