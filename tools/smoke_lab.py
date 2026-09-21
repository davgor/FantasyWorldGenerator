"""Launch the standalone lab server and verify its browser document over HTTP.

Two launches, because the server has two ways of answering `/` and they fail
differently. The default serves the committed sample, so a missing or unreadable
fixture is a startup error rather than a blank page. `--fresh` generates from the
CLI settings on every request, which is the path a parameter sweep uses and the
only one that still proves `generate` runs under the server.
"""

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


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def document(arguments: list, output: str) -> str:
    """Start the lab with `arguments`, return the document it serves at `/`."""
    port = free_port()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "Sim")
    process = subprocess.Popen(
        [sys.executable, "tools/terrain_lab.py", "--serve", "--size", "17", "--phase", "1",
         "--port", str(port), "--output", output, *arguments],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        # The sample is read and parsed before the socket opens, so the window here
        # covers a 50 MB file as well as a bare process start.
        deadline = time.monotonic() + 60
        last_error = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("lab server exited early: " + (process.stdout.read() if process.stdout else ""))
            try:
                with urlopen(f"http://127.0.0.1:{port}/", timeout=30) as response:
                    body = response.read().decode("utf-8")
            except OSError as exc:
                last_error = exc
                time.sleep(0.1)
                continue
            if response.status != 200 or "<title>Terrain math lab</title>" not in body:
                raise RuntimeError("lab server returned an unexpected browser document")
            return body
        raise RuntimeError(f"lab server did not become ready: {last_error}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> int:
    with tempfile.TemporaryDirectory() as output:
        served = document([], output)
        if "const sample=true" not in served:
            raise RuntimeError("the default lab server did not serve the prebuilt sample")
        if '"build_stages"' not in served:
            raise RuntimeError("the served sample carries no build stages, so the lab's "
                               "stage inspector has nothing to show")
        fresh = document(["--fresh"], output)
        if "const sample=false" not in fresh:
            raise RuntimeError("--fresh still served the prebuilt sample")
    print(f"Lab server smoke test passed: sample document {len(served)/1e6:.1f} MB, "
          f"freshly generated document {len(fresh)/1e6:.1f} MB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
