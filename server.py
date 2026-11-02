#!/usr/bin/env python3
"""screenflow setup app: http://127.0.0.1:8777  (localhost only).
Arrange the screens as they stand on the desk, draw mouse flows, save: config.json is written and the app restarted."""
import json, os, subprocess, signal, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "config.json"); CFG_PEER = os.path.join(HERE, "config-daniel.json")
STATUS = os.path.join(HERE, "config.status.json"); PORT = 8777

def load(p, default=None):
    try: return json.load(open(p, encoding="utf8"))
    except Exception: return default

def state():
    cfg = load(CFG, {}); st = load(STATUS, {})
    return {"config": cfg, "status": st}

def restart_app():
    subprocess.run(["pkill", "-f", "screenflow config.json"], check=False)
    log = open(os.path.join(HERE, "run.log"), "ab")
    subprocess.Popen([os.path.join(HERE, "screenflow"), "config.json"], cwd=HERE, stdout=log, stderr=log,
                     stdin=subprocess.DEVNULL, start_new_session=True)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path.startswith("/api/state"): return self.send(200, state())
        page = {"/": "setup.html", "/setup.html": "setup.html", "/flow.html": "flow.html", "/layout.html": "layout.html"}.get(self.path.split("?")[0])
        if not page: return self.send(404, {"error": "not found"})
        try: return self.send(200, open(os.path.join(HERE, page), "rb").read(), "text/html; charset=utf-8")
        except FileNotFoundError: return self.send(404, {"error": f"{page} missing (run make_flow.py / make_layout.py)"})
    def do_POST(self):
        if self.path != "/api/save": return self.send(404, {"error": "not found"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or b"{}"))
        edges, layout = body.get("edges", []), body.get("layout", {})
        for e in edges:
            if e.get("side") not in ("left", "right", "top", "bottom") or not e.get("from") or not e.get("to"):
                return self.send(400, {"error": f"bad link: {e}"})
            if e.get("enter") not in (None, "left", "right", "top", "bottom"):
                return self.send(400, {"error": f"bad arrival edge: {e}"})
        for p in (CFG, CFG_PEER):
            c = load(p, {}); c["edges"] = edges; c["layout"] = layout
            json.dump(c, open(p, "w", encoding="utf8"), indent=2, ensure_ascii=False)
        restart_app()
        return self.send(200, {"ok": True, "links": len(edges)})

if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"screenflow setup: http://127.0.0.1:{PORT}  (Ctrl+C to stop)"); sys.stdout.flush()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
