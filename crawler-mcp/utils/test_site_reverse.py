"""Offline regression checks for the PDD and X reverse case integrations."""

from __future__ import annotations

import base64
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
X_DIR = ROOT / "analysis" / "x"
sys.path.insert(0, str(X_DIR))

from x_client_transaction import XClientTransaction, decode_transaction_id


def test_x_transaction_round_trip() -> None:
    verification_bytes = bytes(range(48))
    verification = base64.b64encode(verification_bytes).decode("ascii")
    frame_path = "M00000000C10 20 30 40 50 60 70 80 90 100 110"
    frames = {frame_id: ["M0", frame_path] for frame_id in range(4)}
    transaction = XClientTransaction(
        verification=verification,
        frames=frames,
        row_index=0,
        key_indices=[1, 2, 3],
    )

    value = transaction.generate(
        method="GET",
        path="/i/api/graphql/test/SearchTimeline",
        time_now=123456,
        random_byte=0x5A,
    )
    decoded = decode_transaction_id(value)

    assert len(value) == 94
    assert decoded["random_byte"] == 0x5A
    assert decoded["verification_bytes"] == verification_bytes
    assert decoded["relative_time"] == 123456
    assert decoded["version"] == 3


def test_integrated_files() -> None:
    required = [
        ROOT / "analysis" / "pdd" / "pdd_anti_content_pure_node.js",
        ROOT / "analysis" / "pdd" / "pdd_fbez_logic_analyzer.js",
        ROOT / "analysis" / "x" / "search_timeline.py",
        ROOT / "skills" / "13_PDD_anti_content逆向.md",
        ROOT / "skills" / "14_X_transaction_search逆向.md",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    assert not missing, f"missing integrated files: {missing}"


def test_x_json_config() -> None:
    config = {
        "authorization": "Bearer test-value",
        "csrf_token": "test-ct0",
        "cookies": {"auth_token": "test-auth", "ct0": "test-ct0"},
        "proxy": "http://127.0.0.1:7897",
        "graphql_url": "https://x.com/i/api/graphql/test/SearchTimeline",
        "search": {
            "query": "config-query",
            "product": "Latest",
            "query_source": "typed_query",
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        previous = os.environ.get("X_CONFIG_FILE")
        os.environ["X_CONFIG_FILE"] = str(path)
        try:
            sys.modules.pop("search_timeline", None)
            module = importlib.import_module("search_timeline")
            assert module.headers["authorization"] == config["authorization"]
            assert module.headers["x-csrf-token"] == config["csrf_token"]
            assert module.cookies == config["cookies"]
            assert module.proxy_url == config["proxy"]
            assert module.url == config["graphql_url"]
            assert module.search_query == config["search"]["query"]
            assert module.search_product == config["search"]["product"]
        finally:
            sys.modules.pop("search_timeline", None)
            if previous is None:
                os.environ.pop("X_CONFIG_FILE", None)
            else:
                os.environ["X_CONFIG_FILE"] = previous


def main() -> None:
    test_x_transaction_round_trip()
    test_x_json_config()
    test_integrated_files()
    print("site reverse integration smoke tests passed")


if __name__ == "__main__":
    main()
