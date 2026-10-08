#!/usr/bin/env python3
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from submission_store import ConflictError, StaleUpdateError, SubmissionStore


class SubmissionServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, database):
        self.database = database
        super().__init__(address, SubmissionHandler)


class SubmissionHandler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length))

    def do_POST(self):
        store = SubmissionStore(self.server.database)
        try:
            data = self._body()
            if self.path == "/submissions":
                existing = store.find(data["wallet"], data["bounty"])
                row = store.submit(
                    data["wallet"], data["bounty"],
                    data["idempotency_key"], data["content"],
                )
                self._send(200 if existing else 201, row)
                return
            if self.path.startswith("/submissions/") and self.path.endswith("/review"):
                submission_id = self.path.split("/")[2]
                row = store.review(submission_id, data["status"], data["expected_version"])
                self._send(200, row)
                return
            self._send(404, {"error": "not_found"})
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": "invalid_request", "detail": str(exc)})
        except StaleUpdateError as exc:
            self._send(409, {"error": "stale_update", "detail": str(exc)})
        except ConflictError as exc:
            self._send(409, {"error": "conflict", "detail": str(exc)})
        finally:
            store.close()

    def log_message(self, _format, *_args):
        pass


def create_server(host, port, database):
    return SubmissionServer((host, port), str(database))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--database", default="submissions.db")
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.database)
    print(f"listening on http://{args.host}:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
