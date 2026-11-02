#!/bin/bash
# Launch screenflow on this Mac. Picks the right role from the computer name.
#   ./start.sh          start the mouse app (keep this window open; Ctrl+C stops it)
#   ./start.sh --setup  on the mouse-owner Mac: also start the setup page and open it
cd "$(dirname "$0")"
case "$(scutil --get LocalHostName 2>/dev/null)" in
  Danimasters-Mac-Studio) CFG=config.json; ROLE="mouse owner (Mac Studio)" ;;
  *)                      CFG=config-daniel.json; ROLE="follower (MacBook Pro)" ;;
esac
[ -x screenflow ] || { echo "screenflow binary missing or not executable: run ./install.sh first"; exit 1; }
[ -s secret.txt ]  || { echo "secret.txt missing: run ./install.sh first"; exit 1; }
if [ "$1" = "--setup" ]; then
  pkill -f "python3 server.py" 2>/dev/null; nohup python3 server.py > server.log 2>&1 &
  sleep 1; T=$(cat .setup-token 2>/dev/null); open "http://127.0.0.1:8777/?token=$T" 2>/dev/null; echo "setup page: http://127.0.0.1:8777/?token=$T"
fi
echo "This Mac: $ROLE, config $CFG"
echo "Expected within a few seconds: 'connected to <other machine>, displays: [...]'. Ctrl+C stops."
exec ./screenflow "$CFG"
