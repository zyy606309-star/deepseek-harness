import asyncio
import tempfile
from pathlib import Path

from browser import BrowserManager


async def main():
    browser = BrowserManager()
    assert (await browser.replay_actions(actions=[]))["success"]
    assert (await browser.replay_and_capture(actions=[]))["success"]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "actions.json"
        await browser.start_action_recording()
        saved = await browser.stop_action_recording(str(path))
        assert saved["count"] == 0 and path.exists()
    diff = await browser.diff_requests(
        baseline=[{"method": "POST", "url": "/api", "type": "XHR", "postData": "a"}],
        current=[{"method": "POST", "url": "/api", "type": "XHR", "postData": "b"}],
    )
    assert diff["summary"]["changed"] == 1
    print("browser feature smoke tests passed")


if __name__ == "__main__":
    asyncio.run(main())
