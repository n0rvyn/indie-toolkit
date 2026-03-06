#!/usr/bin/env python3
"""
LLM Router Proxy — transparent API proxy that routes requests
to different model providers based on model ID.

Usage:
    python3 proxy.py                # Start proxy on configured port
    python3 proxy.py --test         # Test all configured routes
    python3 proxy.py --port 8765    # Override port

Environment variables (set per route in routes.json):
    DASHSCOPE_API_KEY               # For qwen/glm via DashScope
"""

import argparse
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

CONFIG_PATH = Path(__file__).parent / "routes.json"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


class ProxyHandler(BaseHTTPRequestHandler):
    config = None

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON request body")
            return

        model = data.get("model", "")
        route = self._find_route(model)

        if route:
            target_base = route["endpoint"].rstrip("/")
            api_key = os.environ.get(route["api_key_env"], "")
            route_name = route["name"]
            if not api_key:
                self._send_error(
                    500,
                    f"Environment variable '{route['api_key_env']}' not set",
                )
                return
        else:
            target_base = "https://api.anthropic.com"
            api_key = self.headers.get("x-api-key", "")
            route_name = "anthropic"

        target_url = target_base + self.path

        # Forward relevant headers
        headers = {
            "content-type": "application/json",
            "x-api-key": api_key,
        }
        for key in self.headers:
            lk = key.lower()
            if lk.startswith("anthropic-"):
                headers[key] = self.headers[key]

        self._log(f"{model} -> {route_name}")

        try:
            req = Request(target_url, data=body, headers=headers, method="POST")
            resp = urlopen(req, timeout=300)

            self.send_response(resp.status)
            for key, value in resp.getheaders():
                if key.lower() not in (
                    "transfer-encoding",
                    "connection",
                    "keep-alive",
                ):
                    self.send_header(key, value)
            self.end_headers()

            # Forward response body (works for both streaming and non-streaming)
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()

            resp.close()

        except HTTPError as e:
            error_body = e.read()
            self.send_response(e.code)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(error_body)
            self._log(f"  HTTP {e.code}")
        except Exception as e:
            self._send_error(502, str(e))
            self._log(f"  ERROR: {e}")

    def _find_route(self, model):
        for route in self.config.get("routes", []):
            if model in route.get("models", []):
                return route
            for prefix in route.get("model_prefixes", []):
                if model.startswith(prefix):
                    return route
        return None

    def _send_error(self, code, message):
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.end_headers()
        body = json.dumps({"error": {"type": "proxy_error", "message": message}})
        self.wfile.write(body.encode())

    def _log(self, msg):
        sys.stderr.write(f"[proxy] {msg}\n")
        sys.stderr.flush()

    def log_message(self, format, *args):
        pass  # Suppress default access logs


def test_routes(config):
    """Test all configured routes with a minimal API call."""
    print("Testing routes...\n")

    for route in config.get("routes", []):
        api_key = os.environ.get(route["api_key_env"], "")
        if not api_key:
            print(f"  SKIP  {route['name']}: {route['api_key_env']} not set")
            continue

        endpoint = route["endpoint"].rstrip("/") + "/v1/messages"

        # Test first 2 models in the list
        for model in route.get("models", [])[:2]:
            payload = json.dumps(
                {
                    "model": model,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "say ok"}],
                }
            ).encode()

            headers = {
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }

            try:
                req = Request(endpoint, data=payload, headers=headers, method="POST")
                with urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                    text = next(
                        (
                            b["text"]
                            for b in data.get("content", [])
                            if b.get("type") == "text"
                        ),
                        "(no text)",
                    )
                    print(f"  OK    {route['name']}/{model}: {text[:50]}")
            except Exception as e:
                print(f"  FAIL  {route['name']}/{model}: {e}")

    # Test Anthropic passthrough
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        try:
            payload = json.dumps(
                {
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "say ok"}],
                }
            ).encode()
            req = Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "content-type": "application/json",
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                text = next(
                    (
                        b["text"]
                        for b in data.get("content", [])
                        if b.get("type") == "text"
                    ),
                    "(no text)",
                )
                print(f"  OK    anthropic/haiku: {text[:50]}")
        except Exception as e:
            print(f"  FAIL  anthropic/haiku: {e}")
    else:
        print(f"  SKIP  anthropic: ANTHROPIC_API_KEY not set")


def main():
    parser = argparse.ArgumentParser(description="LLM Router Proxy")
    parser.add_argument("--port", type=int, help="Override port from config")
    parser.add_argument("--test", action="store_true", help="Test all routes")
    args = parser.parse_args()

    config = load_config()

    if args.test:
        test_routes(config)
        return

    port = args.port or config.get("port", 8765)
    ProxyHandler.config = config

    # Check env vars
    for route in config.get("routes", []):
        key_env = route["api_key_env"]
        if os.environ.get(key_env):
            print(f"  {route['name']}: {key_env} set")
        else:
            print(f"  {route['name']}: {key_env} NOT SET (requests will fail)")

    server = HTTPServer(("127.0.0.1", port), ProxyHandler)
    print(f"\nLLM Router Proxy on http://127.0.0.1:{port}")
    print(f"Routes: {[r['name'] for r in config.get('routes', [])]}")
    print(f"Default: anthropic (passthrough)\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
