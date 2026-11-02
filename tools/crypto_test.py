"""End-to-end test of the sealed transport against a dry-run owner on 127.0.0.1:24802."""
import socket, json, os, base64, time, sys
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
PORT = 24802
def key_for(secret, cn, sn):
    return HKDF(algorithm=SHA256(), length=32, salt=cn + sn, info=b"screenflow-v2").derive(secret.encode())
class Peer:
    def __init__(self, secret):
        self.s = socket.create_connection(("127.0.0.1", PORT), timeout=5); self.buf = b""; self.n = 0; self.rn = 0
        self.cn = os.urandom(16); self.send_plain({"t": "hi", "nonce": base64.b64encode(self.cn).decode()})
        hi = self.recv_plain(); self.sn = base64.b64decode(hi["nonce"]); self.key = key_for(secret, self.cn, self.sn)
        self.aead = ChaCha20Poly1305(self.key)
    def send_plain(self, d): self.s.sendall((json.dumps(d) + "\n").encode())
    def seal(self, d):
        self.n += 1; d = dict(d, n=self.n); nonce = os.urandom(12)
        return base64.b64encode(nonce + self.aead.encrypt(nonce, json.dumps(d).encode(), None)) + b"\n"
    def send(self, d): self.s.sendall(self.seal(d))
    def line(self, timeout=3):
        self.s.settimeout(timeout)
        try:
            while b"\n" not in self.buf:
                ch = self.s.recv(4096)
                if not ch: return None
                self.buf += ch
        except socket.timeout: return None
        l, self.buf = self.buf.split(b"\n", 1); return l
    def recv_plain(self): return json.loads(self.line())
    def recv(self):
        l = self.line()
        if l is None: return None
        raw = base64.b64decode(l); return json.loads(self.aead.decrypt(raw[:12], raw[12:], None)), l
secret = open("secret.txt").read().strip()
displays = [{"name": "Built-in Retina Display", "x": -1728, "y": 0, "w": 1728, "h": 1117}, {"name": "DELL P2725H", "x": 0, "y": 0, "w": 1920, "h": 1080}]
results = {}
# 1. wrong secret: our sealed hello cannot be opened -> owner closes the link
p = Peer("not-the-secret"); p.send({"t": "hello", "machine": "daniel", "host": "fake-host", "displays": displays})
results["wrong secret rejected"] = p.line() is None
p.s.close(); time.sleep(0.3)
# 2. right secret: sealed hello both ways, owner's hello decrypts and carries displays + edges; wire shows no plaintext
p = Peer(secret); p.send({"t": "hello", "machine": "daniel", "host": "fake-host", "displays": displays})
msg, rawline = p.recv()
results["owner hello decrypts"] = msg["t"] == "hello" and [d["name"] for d in msg["displays"]] == ["VG248", "LG FULL HD"] and len(msg.get("edges", [])) == 8
results["wire is not readable"] = b"VG248" not in rawline and secret.encode() not in rawline and b"hello" not in rawline
# 3. a live message works; a replayed line (same bytes again) kills the link
sealed = p.seal({"t": "stop"}); p.s.sendall(sealed); time.sleep(0.2); p.s.sendall(sealed); time.sleep(0.3)
results["replay closes the link"] = p.line(2) is None
p.s.close(); time.sleep(0.3)
# 4. plaintext after the handshake is refused
p = Peer(secret); p.send({"t": "hello", "machine": "daniel", "host": "fake-host", "displays": displays}); p.recv()
p.send_plain({"t": "stop"}); time.sleep(0.3)
results["plaintext after handshake refused"] = p.line(2) is None
p.s.close()
for k, v in results.items(): print(("PASS " if v else "FAIL ") + k)
sys.exit(0 if all(results.values()) else 1)
