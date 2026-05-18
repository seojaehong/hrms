#!/usr/bin/env python3
import http.server
import socketserver
import urllib.request
import urllib.error

UPSTREAM = "http://127.0.0.1:8000"
FORCED_HOST = "hrms.localhost"
PORT = 18000
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _forward(self):
        target = f"{UPSTREAM}{self.path}"
        body = None
        if self.command in {"POST", "PUT", "PATCH"}:
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else None

        headers = {}
        for k, v in self.headers.items():
            if k.lower() in HOP_BY_HOP:
                continue
            if k.lower() == "host":
                continue
            headers[k] = v
        headers["Host"] = FORCED_HOST
        headers["X-Forwarded-Host"] = self.headers.get("Host", "")
        headers["X-Forwarded-Proto"] = "https"
        headers["X-Forwarded-For"] = self.client_address[0]

        req = urllib.request.Request(target, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    lk = k.lower()
                    if lk in HOP_BY_HOP:
                        continue
                    if lk == "content-length":
                        continue
                    self.send_header(k, v)
                data = resp.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            for k, v in e.headers.items():
                lk = k.lower()
                if lk in HOP_BY_HOP or lk == "content-length":
                    continue
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            data = f"Proxy error: {e}\n".encode()
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def do_GET(self): self._forward()
    def do_POST(self): self._forward()
    def do_PUT(self): self._forward()
    def do_PATCH(self): self._forward()
    def do_DELETE(self): self._forward()
    def do_HEAD(self): self._forward()

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - - [{self.log_date_time_string()}] {fmt % args}")

with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), ProxyHandler) as httpd:
    print(f"HRMS preview proxy on http://127.0.0.1:{PORT} -> {UPSTREAM} Host={FORCED_HOST}")
    httpd.serve_forever()
