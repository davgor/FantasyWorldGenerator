"""Launch the standalone lab server and verify its browser document over HTTP."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "Sim")
    with tempfile.TemporaryDirectory() as output:
        process = subprocess.Popen(
            [sys.executable, "tools/terrain_lab.py", "--serve", "--size", "17", "--phase", "1", "--port", str(port), "--output", output],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline = time.monotonic() + 20
            last_error = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("lab server exited early: " + (process.stdout.read() if process.stdout else ""))
                try:
                    with urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                        body = response.read().decode("utf-8")
                    if response.status != 200 or "<title>Terrain math lab</title>" not in body:
                        raise RuntimeError("lab server returned an unexpected browser document")
                    print(f"Lab server smoke test passed on loopback port {port}.")
                    return 0
                except OSError as exc:
                    last_error = exc
                    time.sleep(0.1)
            raise RuntimeError(f"lab server did not become ready: {last_error}")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())

