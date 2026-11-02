#!/bin/bash
# screenflow installer for either Mac. Run from the unzipped/cloned folder, or anywhere (it clones to ~/screenflow).
set -e
REPO="https://github.com/profitelai/screenflow.git"
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HERE/main.swift" ]; then DIR="$HERE"; else
  DIR="$HOME/screenflow"
  if [ -d "$DIR/.git" ]; then git -C "$DIR" pull --ff-only; else git clone "$REPO" "$DIR"; fi
fi
cd "$DIR"
if command -v swiftc >/dev/null 2>&1; then swiftc -O main.swift -o screenflow && echo "built from source"; else echo "no swiftc on this Mac: using the prebuilt binary"; fi
chmod +x screenflow
if [ ! -s secret.txt ]; then
  echo "Type the shared secret (read it on the Mac Studio with: cat ~/bizlocal/screen-flow/secret.txt), then Enter:"
  read -r S; printf '%s\n' "$S" > secret.txt; chmod 600 secret.txt
fi
case "$(scutil --get LocalHostName 2>/dev/null)" in
  Danimasters-Mac-Studio) CFG=config.json ;;
  *) CFG=config-daniel.json ;;
esac
echo "config for this Mac: $CFG"; ./screenflow "$CFG" --check
echo; echo "Grant Accessibility to Terminal (Privacy & Security), reopen Terminal, then run:"
echo "  cd $DIR && ./screenflow $CFG"
