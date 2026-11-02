"""Draw how the mouse is meant to move, from config.json: python3 make_flow.py -> flow.html"""
import json, html, os
here = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(here, "config.json")))
# physical row, left to right: Mac Studio stack (LG over VG248) | MacBook Retina | DELL
S = 0.13
box = {  # name: (x, y, w, h) in page units
    "LG FULL HD":             (60,  70, 1920*S, 1080*S),
    "VG248":                  (60,  70+1080*S+6, 1920*S, 1080*S),
    "Built-in Retina Display":(60+1920*S+70, 70+1080*S+6+ (1080-1117*0.9)*S, 1728*S*0.9, 1117*S*0.9),
    "DELL P2725H":            (60+1920*S+70+1728*S*0.9+70, 70+1080*S+6, 1920*S, 1080*S),
}
owner = {"LG FULL HD":"Mac Studio","VG248":"Mac Studio","Built-in Retina Display":"MacBook Pro","DELL P2725H":"MacBook Pro"}
W = int(max(x+w for x,y,w,h in box.values())+60); H = int(max(y+h for x,y,w,h in box.values())+150)
def pt(b, side):
    x,y,w,h = b
    return {"left":(x,y+h/2),"right":(x+w,y+h/2),"top":(x+w/2,y),"bottom":(x+w/2,y+h)}[side]
opp = {"left":"right","right":"left","top":"bottom","bottom":"top"}
svg=[f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,system-ui,sans-serif">',
     '<defs><marker id="g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#16a34a"/></marker>'
     '<marker id="b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#2563eb"/></marker>'
     '<marker id="o" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#ea580c"/></marker></defs>']
svg.append(f'<text x="60" y="40" font-size="20" font-weight="700" fill="#0f172a">How the mouse moves (from config.json)</text>')
for n,(x,y,w,h) in box.items():
    mac = owner[n]=="Mac Studio"
    svg.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="10" fill="{"#dbeafe" if mac else "#dcfce7"}" stroke="#1e3a8a" stroke-width="1.5"/>')
    svg.append(f'<text x="{x+w/2:.0f}" y="{y+h/2:.0f}" text-anchor="middle" font-size="15" font-weight="600" fill="#0f172a">{html.escape(n)}</text>')
    svg.append(f'<text x="{x+w/2:.0f}" y="{y+h/2+20:.0f}" text-anchor="middle" font-size="12" fill="#475569">{owner[n]}</text>')
# Mac Studio screens 1 and 2 share the same left and right edges; draw each link once per pair
seen=set(); k=0
for e in cfg["edges"]:
    a,b = e["from"]["display"], e["to"]["display"]; side=e["side"]
    key=(a if a!="LG FULL HD" else "VG248", side, b)
    if key in seen: continue
    seen.add(key)
    A,B = box[a], box[b]; p1=pt(A,side); p2=pt(B,opp[side])
    vertical = side in ("top","bottom"); wrap = (side=="left" and b=="DELL P2725H") or (side=="right" and a=="DELL P2725H")
    col,mk = ("#ea580c","o") if vertical else (("#2563eb","b") if wrap else ("#16a34a","g"))
    if wrap:   # loop around the outside, under the row
        yb = H-70; d=f"M{p1[0]:.0f},{p1[1]:.0f} C{p1[0]-80:.0f},{p1[1]:.0f} {p1[0]-80:.0f},{yb} {(p1[0]+p2[0])/2:.0f},{yb} S{p2[0]+80:.0f},{yb} {p2[0]+80:.0f},{p2[1]:.0f} S{p2[0]:.0f},{p2[1]:.0f} {p2[0]:.0f},{p2[1]:.0f}" if side=="left" else \
                 f"M{p1[0]:.0f},{p1[1]:.0f} C{p1[0]+80:.0f},{p1[1]:.0f} {p1[0]+80:.0f},{yb} {(p1[0]+p2[0])/2:.0f},{yb} S{p2[0]-80:.0f},{yb} {p2[0]-80:.0f},{p2[1]:.0f} S{p2[0]:.0f},{p2[1]:.0f} {p2[0]:.0f},{p2[1]:.0f}"
    elif vertical:   # loop around the left side of the stack
        xl = 25; d=f"M{p1[0]:.0f},{p1[1]:.0f} C{p1[0]:.0f},{p1[1]+40:.0f} {xl},{p1[1]+40:.0f} {xl},{(p1[1]+p2[1])/2:.0f} S{xl},{p2[1]-40:.0f} {p2[0]:.0f},{p2[1]:.0f}"
    else:
        d=f"M{p1[0]:.0f},{p1[1]+(-14 if side=='right' else 14):.0f} L{p2[0]:.0f},{p2[1]+(-14 if side=='right' else 14):.0f}"
    svg.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2.5" marker-end="url(#{mk})"/>')
    k+=1
leg=[("#16a34a","Next screen: push the mouse off the right edge of a Mac Studio screen, it comes in on the MacBook screen (and back by its left edge)"),
     ("#2563eb","Wrap: push off the LEFT edge of a Mac Studio screen, it comes in on the far right screen (DELL), and back off the DELL's right edge"),
     ("#ea580c","Vertical loop on the Mac Studio: off the bottom of VG248 into the top of LG FULL HD, and off the top of LG back into the bottom of VG248")]
for i,(c,t) in enumerate(leg):
    y=H-40+i*18-18
    svg.append(f'<rect x="60" y="{y-9}" width="22" height="4" fill="{c}"/><text x="90" y="{y-4}" font-size="12" fill="#0f172a">{html.escape(t)}</text>')
svg.append("</svg>")
page=f'<!doctype html><html><head><meta charset="utf-8"><title>screenflow: mouse flow</title><style>body{{margin:20px;background:#fff;max-width:1100px}}</style></head><body>{"".join(svg)}<p style="font:13px system-ui;color:#475569">Blue screens = Mac Studio (physical mouse). Green screens = MacBook Pro. Edges between the two Mac Studio screens and between the MacBook screens are handled by macOS itself.</p></body></html>'
open(os.path.join(here,"flow.html"),"w",encoding="utf-8").write(page); print("wrote flow.html")
