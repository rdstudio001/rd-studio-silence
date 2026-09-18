"""
RD Studio Auto Silence Remover — Main Application Launcher
Runs as a native Windows Desktop Application (via PyWebView / Edge WebView2)
or as a local network server with mobile access and PWA support.
Owner: Shahneel Khan | Website: rdstudio.online
"""

import os
import sys
import time
import socket
import argparse
import threading
import webbrowser

from api_server import run_server


def get_local_ip() -> str:
    """Finds the local network IP address (for Wi-Fi / mobile access)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def start_server_in_thread(host: str, port: int):
    t = threading.Thread(target=run_server, kwargs={"host": host, "port": port}, daemon=True)
    t.start()
    # Wait briefly for server socket to bind
    time.sleep(0.4)
    return t


def launch_desktop_window(url: str, title: str = "RD Studio — Auto Silence Remover"):
    """Attempts to launch native Windows desktop window via pywebview."""
    try:
        import webview
        window = webview.create_window(
            title=title,
            url=url,
            width=1380,
            height=880,
            min_size=(1100, 700),
            background_color='#0c0d12'
        )
        webview.start()
        return True
    except Exception as e:
        print(f"Native desktop window unavailable ({e}). Falling back to browser view.")
        return False


def main():
    parser = argparse.ArgumentParser(description="RD Studio Auto Silence Remover")
    parser.add_argument("--port", type=int, default=8080, help="Web server port (default 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Binding host (default 0.0.0.0)")
    parser.add_argument("--server", action="store_true", help="Run purely as network server (for mobile/studio team)")
    parser.add_argument("--browser", action="store_true", help="Launch in default system web browser")
    args = parser.parse_args()

    local_ip = get_local_ip()
    local_url = f"http://127.0.0.1:{args.port}"
    network_url = f"http://{local_ip}:{args.port}"

    print("=" * 65)
    print("      RD STUDIO — AUTO SILENCE REMOVER (v1.0.0)")
    print("      Owner: Shahneel Khan | https://rdstudio.online")
    print("=" * 65)
    print(f" Local Desktop Access:  {local_url}")
    print(f" Mobile / Wi-Fi Access: {network_url}")
    print("=" * 65)

    # Start background API server
    start_server_in_thread(host=args.host, port=args.port)

    if args.server:
        print(f"\n[INFO] Studio Server running on {network_url}")
        print("[INFO] Open this URL on your phone or laptop browser. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down server.")
            sys.exit(0)

    elif args.browser:
        print(f"Opening browser at {local_url}...")
        webbrowser.open(local_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

    else:
        # Default Desktop Mode: Try native window, fallback to browser
        opened = launch_desktop_window(local_url)
        if not opened:
            webbrowser.open(local_url)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                sys.exit(0)


if __name__ == "__main__":
    main()
