# screenflow

One mouse across two Macs, Synergy-style, including the wrap from the first screen back to the last.
The **Mac Studio** owns the physical mouse (`config.json`); the **MacBook Pro** follows (`config-daniel.json`).

## Install or update (both Macs)
Private repo, so on a new Mac either `gh auth login` first, or download the ZIP from the GitHub page while signed in, unzip, then:
```
./install.sh
```
It builds from source when `swiftc` exists (Xcode Command Line Tools), otherwise uses the committed `screenflow` binary,
asks once for the shared secret (never in git: `secret.txt`), picks the right config for this Mac, and prints the display check.

Then: System Settings > Privacy & Security > **Accessibility**: add Terminal, switch it on, reopen Terminal.
The Mac Studio also needs **Input Monitoring** (it runs the event tap). Start the MacBook side first, then the Mac Studio:
```
./screenflow config-daniel.json     # MacBook Pro
./screenflow config.json            # Mac Studio
```
Expected on both: `connected to <other machine>, displays: [...]`.

## Links (edit only on the Mac Studio; it pushes them to the MacBook at connect time)
- Mac Studio right edge (VG248 or LG FULL HD) -> MacBook **Built-in Retina Display**; its left edge comes back to VG248.
- **Wrap:** Mac Studio left edge -> **DELL P2725H** right edge, and the DELL's right edge comes back to VG248 (screen 1 <-> screen 3).
- Display names must match what `./screenflow <config> --check` prints on that Mac.

## Safety
- Escape pressed 3 times within 1.5 s (Mac Studio keyboard) always returns the mouse.
- The mouse is only handed over when the other Mac is connected, authenticated, and has reported the target display.
- Keyboard is never forwarded. Plain TCP on the home LAN with a shared secret; do not use across the internet.
- `--dry-run` logs instead of moving anything; `make_layout.py --watch` draws the live layout to `layout.html`.
- If macOS **Universal Control** is on between these Macs, the two will fight: turn it off in Displays > Advanced.
