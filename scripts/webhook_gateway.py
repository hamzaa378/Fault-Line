"""Webhook-only localhost ingress for use behind a temporary HTTPS tunnel.

Unlike tunnelling port 8000, this gateway exposes ONLY the single webhook
endpoint for one project. No app login or database routes are forwarded.
Not a production DDoS mitigation system; use only for a short-lived demo.

Usage: python scripts/webhook_gateway.py --project-id YOUR_UUID
Tunnel: ngrok http 8765 (or equivalent)
"""
import argparse
import http.client
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UUID_RE = re.compile(r"^[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}$")
MAX_SIZE = 1048576


def make_handler(project_id: str, backend_port: int):
    expected = f"/api/webhooks/github/{project_id}"

    class Gateway(BaseHTTPRequestHandler):
        def respond(self, status: int, body: bytes = b"Not allowed"):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.respond(405)

        def do_POST(self):
            if self.path != expected:
                return self.respond(404)
            try:
                size = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                return self.respond(400)
            if not 0 <= size <= MAX_SIZE:
                return self.respond(413)
            body = self.rfile.read(size)
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
            for k in ("X-Hub-Signature-256", "X-GitHub-Event", "X-GitHub-Delivery"):
                if self.headers.get(k):
                    headers[k] = self.headers[k]
            try:
                conn = http.client.HTTPConnection("127.0.0.1", backend_port, timeout=10)
                try:
                    conn.request("POST", expected, body, headers)
                    response = conn.getresponse()
                    content = response.read(MAX_SIZE)
                    self.respond(response.status, content)
                finally:
                    conn.close()
            except OSError:
                self.respond(502)

    return Gateway


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", required=True)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--backend-port", type=int, default=8000)
    args = p.parse_args()
    if not UUID_RE.fullmatch(args.project_id):
        p.error("--project-id must be a UUID")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.project_id, args.backend_port))
    print(f"Webhook-only gateway running on 127.0.0.1:{args.port}; forwarding POST to {args.project_id}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping gateway", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
