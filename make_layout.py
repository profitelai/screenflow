"""Live view of screens and mouse links, drawn from the app's status file.
Run once:   python3 make_layout.py            (writes layout.html from config.status.json)
Keep live:  python3 make_layout.py --watch    (rewrites every second; the page auto-refreshes)
Other status file: python3 make_layout.py path/to/x.status.json"""
import json, html, os, sys, time

here = os.path.dirname(os.path.abspath(__file__))
status_path = next((a for a in sys.argv[1:] if a.endswith(".json")), os.path.join(here, "config.status.json"))
watch = "--watch" in sys.argv

def norm(displays):
    if not displays: return []
    mx = min(d["x"] for d in displays); my = min(d["y"] for d in displays)
    return [{**d, "x": d["x"] - mx, "y": d["y"] - my} for d in displays]

def panel(displays, ox, oy, pw, ph, fill):
    """Place normalized displays inside a panel, scaled to fit. Returns {name: (x,y,w,h)}."""
    if not displays: return {}
    tw = max(d["x"] + d["w"] for d in displays); th = max(d["y"] + d["h"] for d in displays)
    sc = min((pw - 40) / tw, (ph - 60) / th)
    return {d["name"]: (ox + 20 + d["x"] * sc, oy + 40 + d["y"] * sc, d["w"] * sc, d["h"] * sc) for d in displays}

def edge_point(box, side):
    x, y, w, h = box
    return {"left": (x, y + h / 2), "right": (x + w, y + h / 2), "top": (x + w / 2, y), "bottom": (x + w / 2, y + h)}[side]

def render():
    try: st = json.load(open(status_path))
    except Exception as e:
        return f"<p>No status yet ({html.escape(str(e))}). Start the app: ./screenflow config.json</p>"
    me, peer = st["self"], st.get("peer") or "other Mac"
    W, H = 980, 560; PW, PH = 440, 400
    boxes = {}
    # the other Mac on the left, this Mac on the right (links go left from VG248 into the other Mac)
    for name, box in panel(norm(st.get("peerDisplays", [])), 30, 100, PW, PH, "").items(): boxes[(peer, name)] = box
    for name, box in panel(norm(st.get("localDisplays", [])), 510, 100, PW, PH, "").items(): boxes[(me, name)] = box
    # placeholders for peer displays named in links but not reported yet
    if not st.get("peerDisplays"):
        names = []
        for l in st.get("links", []):
            for ref in (l["from"], l["to"]):
                m, n = ref.split("/", 1)
                if m != me and n not in names: names.append(n)
        for i, n in enumerate(names): boxes[(peer, n)] = (60 + (i % 2) * 210, 150 + (i // 2) * 150, 190, 120)
    conn = st.get("connected"); where = peer if st.get("onPeer") else me
    svg = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,system-ui,sans-serif">',
           '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#2563eb"/></marker></defs>']
    for ox, title, ok in ((30, f"{peer}" + ("" if conn else " (not connected)"), conn), (510, f"{me} (physical mouse)", True)):
        svg.append(f'<rect x="{ox}" y="70" width="{PW}" height="{PH+60}" rx="14" fill="#f8fafc" stroke="{"#16a34a" if ok else "#cbd5e1"}" stroke-width="{2 if ok else 1}"/>')
        svg.append(f'<text x="{ox+16}" y="96" font-size="15" font-weight="700" fill="#334155">{html.escape(title)}</text>')
    for (m, n), (x, y, w, h) in boxes.items():
        real = m == me or bool(st.get("peerDisplays"))
        fill = "#dbeafe" if m == me else ("#dcfce7" if real else "#f1f5f9")
        dash = "" if real else ' stroke-dasharray="6 4"'
        svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="8" fill="{fill}" stroke="#1e3a8a"{dash}/>')
        svg.append(f'<text x="{x+w/2:.1f}" y="{y+h/2+5:.1f}" text-anchor="middle" font-size="13" fill="#0f172a">{html.escape(n)}</text>')
    for i, l in enumerate(st.get("links", [])):
        fm, fn = l["from"].split("/", 1); tm, tn = l["to"].split("/", 1)
        fm = fm if fm == me else peer; tm = tm if tm == me else peer
        a, b = boxes.get((fm, fn)), boxes.get((tm, tn))
        if not a or not b: continue
        opp = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}[l["side"]]
        p1, p2 = edge_point(a, l["side"]), edge_point(b, opp)
        bend = 30 + 22 * i; mx = (p1[0] + p2[0]) / 2; my = (p1[1] + p2[1]) / 2 - bend
        svg.append(f'<path d="M{p1[0]:.1f},{p1[1]:.1f} Q{mx:.1f},{my:.1f} {p2[0]:.1f},{p2[1]:.1f}" fill="none" stroke="#2563eb" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#a)"/>')
    # cursor dot on this Mac when the mouse is here
    if not st.get("onPeer") and st.get("localDisplays"):
        loc = norm(st["localDisplays"]); c = st["cursor"]
        mx0 = min(d["x"] for d in st["localDisplays"]); my0 = min(d["y"] for d in st["localDisplays"])
        tw = max(d["x"] + d["w"] for d in loc); th = max(d["y"] + d["h"] for d in loc); sc = min((PW - 40) / tw, (PH - 60) / th)
        cx = 510 + 20 + (c["x"] - mx0) * sc; cy = 100 + 40 + (c["y"] - my0) * sc
        svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="#dc2626" stroke="#fff" stroke-width="2"/>')
    svg.append(f'<text x="30" y="40" font-size="18" font-weight="700" fill="#0f172a">screenflow, live</text>')
    svg.append(f'<text x="30" y="60" font-size="13" fill="#475569">link: {"connected to " + peer if conn else "waiting for the other Mac"} · cursor on: {where} · updated {html.escape(st.get("updated",""))}{" · DRY RUN" if st.get("dryRun") else ""}</text>')
    svg.append("</svg>")
    rows = "".join(f'<tr><td>{html.escape(l["from"])}</td><td>{l["side"]}</td><td>{html.escape(l["to"])}</td></tr>' for l in st.get("links", []))
    return "".join(svg) + f'<table><tr><th>Leaving</th><th>Edge</th><th>Cursor enters</th></tr>{rows}</table>'

def write():
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>screenflow live</title>{'<meta http-equiv="refresh" content="1">' if watch else ''}
<style>body{{font:15px -apple-system,system-ui,sans-serif;margin:20px;color:#0f172a;background:#fff;max-width:1000px}}
table{{border-collapse:collapse;margin-top:12px}}td,th{{border:1px solid #e2e8f0;padding:6px 10px;text-align:left}}
.note{{color:#475569;font-size:13px}}</style></head><body>{render()}
<p class="note">Green panel border = the other Mac is connected and its real display layout is shown. Dashed grey boxes = displays named in the config that the other Mac has not reported yet. Red dot = where the mouse is now.</p>
</body></html>"""
    open(os.path.join(here, "layout.html"), "w", encoding="utf-8").write(page)

write(); print("wrote layout.html from", status_path)
while watch:
    time.sleep(1); write()
