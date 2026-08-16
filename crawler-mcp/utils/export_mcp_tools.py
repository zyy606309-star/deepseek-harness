"""Export the MCP tool registry from server.py without starting the server."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def _literal_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def extract_tools(server_path: Path) -> list[dict[str, object]]:
    tree = ast.parse(server_path.read_text(encoding="utf-8"), filename=str(server_path))
    tools: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_tool" or not node.args:
            continue
        name = _literal_string(node.args[0])
        description = _literal_string(node.args[1]) if len(node.args) > 1 else None
        if name is None:
            continue
        required: list[str] = []
        if len(node.args) > 3 and isinstance(node.args[3], (ast.List, ast.Tuple)):
            required = [value for item in node.args[3].elts if (value := _literal_string(item))]
        tools.append({"name": name, "description": description or "", "required": required})
    return sorted({item["name"]: item for item in tools}.values(), key=lambda item: str(item["name"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, default=Path(__file__).resolve().parents[1] / "server.py")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    tools = extract_tools(args.server)
    if args.format == "markdown":
        print("# MCP 工具清单\n")
        print(f"> 来源: `{args.server}`\n")
        for tool in tools:
            required = ", ".join(tool["required"]) or "无"
            print(f"## `{tool['name']}`\n\n{tool['description']}\n\n- 必填参数: {required}\n")
    else:
        print(json.dumps(tools, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
