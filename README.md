# MacBook Mouse Screen Flow Manager (screenflow)

One mouse across two Macs and all their screens, arranged the way they stand on your desk.
Push the cursor off the edge of one display and it comes in on the next one, even when that display belongs to the other Mac,
and loop from the last screen back to the first. No Synergy, no Universal Control, no cloud: a small native app on each Mac,
talking over your own network, and a local web page to draw the flows.

![Setup app: arrange the screens and draw the mouse flows](docs/setup.png)

## What it does
- **Two Macs, one mouse.** The Mac with the physical mouse (here a Mac Studio with two monitors) forwards mouse movement,
  clicks and scrolling to the other Mac (a MacBook Pro with its built-in display and an external monitor) when the cursor
  crosses a linked edge. Push back against the edge to return.
- **Screen wrap.** Leave the left-most screen by its left edge and arrive on the right-most screen, or loop a stacked pair
  top to bottom. Each flow is "leave this edge of screen A, arrive on this edge of screen B", in any direction.
- **Desk-true layout.** The setup page shows every display both Macs report, with their real sizes. Drag them to match the
  desk, draw flows between edges, press *Save & apply*.
- **Live view.** The page shows whether the other Mac is connected and a red dot where the mouse is.

![How the mouse moves, generated from the saved flows](docs/flow.png)

## Install (both Macs, about five minutes)
On each Mac, in Terminal:
```
cd ~ && curl -L https://github.com/profitelai/screenflow/archive/refs/heads/main.zip -o screenflow.zip \
  && unzip -q screenflow.zip && cd screenflow-main && ./install.sh
```
`install.sh` builds from source when the Swift compiler is present, otherwise uses the committed binary; it asks once for the
shared secret (the same string on both Macs, kept in `secret.txt`, never in git) and prints the displays it sees.

Then grant the permission macOS requires:
- **Both Macs:** System Settings > Privacy & Security > *Accessibility*: add Terminal (or whatever launches the app), switch it on,
  quit and reopen Terminal.
- **The Mac with the mouse only:** also *Input Monitoring*.

Start the follower first, then the mouse owner:
```
./screenflow config-daniel.json     # the Mac that follows (MacBook Pro)
./screenflow config.json            # the Mac that owns the mouse (Mac Studio)
```
Both print `connected to <other machine>, displays: [...]`.

## Set up the flows
On the Mac that owns the mouse:
```
python3 server.py          # then open http://127.0.0.1:8777/
```
- Drag each screen to where it stands on the desk.
- Click the small circle on the edge the mouse **leaves**, then click the screen it should **arrive on**
  (it enters on the opposite edge), or click that screen's edge circle to choose the exact arrival edge.
- Click an arrow or a table row to select it; *Delete* removes it. *Auto-link touching edges* draws the flows between the two
  Macs where screens touch; the *wrap* buttons add the loop-arounds.
- **Save & apply** writes `config.json`, restarts the app, and the other Mac receives the new flows when it reconnects (a few seconds).
Only `config.json` on the mouse-owner Mac matters; the follower gets its links over the connection.

## Safety and limits
- **Escape pressed three times** within 1.5 s on the mouse owner's keyboard always brings the mouse back.
- The mouse is only handed over when the other Mac is connected, authenticated with the shared secret, and has reported the target display.
- Keyboard input is never forwarded. Transport is plain TCP on the local network with a shared secret: home or office LAN only.
- Each app refuses to connect to a copy of itself on the same computer.
- Turn off macOS **Universal Control** between the two Macs (Displays > Advanced), or both will try to move the cursor.
- `./screenflow <config> --check` prints the displays and links; `--dry-run` logs instead of moving anything.

## Files
`main.swift` (the app, one file) · `screenflow` (prebuilt) · `config.json` / `config-daniel.json` · `install.sh` ·
`server.py` + `setup.html` (the setup page) · `make_flow.py` (flow picture) · `make_layout.py --watch` (live layout page).
