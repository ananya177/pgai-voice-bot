"""Start a Cloudflare Quick Tunnel and the Flask webhook server."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import threading
from queue import Queue, Empty

from dotenv import load_dotenv

load_dotenv()

URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def install_hint() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "Install cloudflared with: brew install cloudflared"
    if system == "windows":
        return "Install cloudflared with: winget install --id Cloudflare.cloudflared"
    return "Install cloudflared from Cloudflare's package repository or release page."


def start_tunnel(port: int) -> tuple[subprocess.Popen[str], str]:
    executable = shutil.which("cloudflared")
    if not executable:
        raise FileNotFoundError(install_hint())

    process = subprocess.Popen(
        [executable, "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: Queue[str] = Queue()

    def reader() -> None:
        assert process.stdout is not None
        for output_line in process.stdout:
            print(f"[cloudflared] {output_line.rstrip()}")
            lines.put(output_line)

    threading.Thread(target=reader, daemon=True, name="cloudflared-output").start()

    for _ in range(60):
        try:
            line = lines.get(timeout=1)
        except Empty:
            if process.poll() is not None:
                raise RuntimeError("cloudflared exited before creating a public URL.")
            continue
        match = URL_PATTERN.search(line)
        if match:
            return process, match.group(0)
    process.terminate()
    raise RuntimeError("Timed out while waiting for a Cloudflare Quick Tunnel URL.")


def main() -> int:
    port = int(os.getenv("PORT", "5000"))
    skip_tunnel = truthy(os.getenv("SKIP_TUNNEL"))
    tunnel_process: subprocess.Popen[str] | None = None

    if skip_tunnel:
        public_url = os.getenv("BASE_URL", "").rstrip("/")
        if not public_url.startswith("https://"):
            print("SKIP_TUNNEL=1 requires BASE_URL to be a public HTTPS URL.")
            return 1
    else:
        try:
            tunnel_process, public_url = start_tunnel(port)
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"Unable to start tunnel: {exc}")
            return 1

    os.environ["BASE_URL"] = public_url
    print("\n" + "=" * 72)
    print("PGAI Voice Bot")
    print(f"Public webhook URL: {public_url}")
    print(f"Local server:        http://localhost:{port}")
    print("Run in another terminal:")
    print("  python run_calls.py --health")
    print("  python run_calls.py --scenario SCN-01")
    print("=" * 72 + "\n")

    try:
        from config import reload_settings
        from app import create_app

        settings = reload_settings()
        flask_app = create_app(settings=settings)
        flask_app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        if tunnel_process and tunnel_process.poll() is None:
            tunnel_process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
