#!/data/data/com.termux/files/usr/bin/sh
# One-shot connectivity diagnostic for the Termux-hosted reference backend.
#
# Exists because troubleshooting this by hand meant retyping a new command
# on a TV remote every round -- this collapses the whole checklist into one
# short command, typed once:
#
#   curl -sL https://raw.githubusercontent.com/Deegan4/KodiCum/main/tools/diag.sh | sh
#
# Checks, in order: is the backend process alive; does it answer over
# loopback; does it answer over the box's own network-facing IP (the same
# path a remote device's request takes, without involving Tailscale or any
# other device at all); is sshd listening. Each result narrows down where a
# "can't reach the dashboard" problem actually is.

PORT="${CUMNATION_PORT:-8765}"

detect_ip() {
    addrs=$(ip addr show 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1 | grep -v '^127\.')
    tailscale_addr=$(echo "$addrs" | grep '^100\.' | head -1)
    if [ -n "$tailscale_addr" ]; then
        echo "$tailscale_addr"
    else
        echo "$addrs" | head -1
    fi
}

echo "=== Cumnation diagnostic ==="

echo
echo "-- Backend process --"
if pgrep -f "resources/lib/mock_server.py" >/dev/null 2>&1; then
    echo "OK: mock_server.py is running (pid $(pgrep -f 'resources/lib/mock_server.py' | tr '\n' ' '))"
else
    echo "FAIL: mock_server.py is NOT running."
    echo "      Fix: re-run tools/termux_bootstrap.sh"
fi

echo
echo "-- Loopback (127.0.0.1) --"
if curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/status | grep -q 200; then
    echo "OK: backend answers on loopback."
else
    echo "FAIL: backend does not answer even on loopback."
    echo "      The process check above tells you whether it's running at all."
fi

ip=$(detect_ip)
echo
echo "-- Own network IP ($ip) --"
if [ -z "$ip" ]; then
    echo "SKIPPED: could not detect an IP."
elif curl -s -m 5 -o /dev/null -w '%{http_code}' http://$ip:$PORT/status | grep -q 200; then
    echo "OK: backend answers over $ip -- the network path a remote device"
    echo "    would use works. If a remote device still can't reach it,"
    echo "    the problem is between that device and this one (Tailscale"
    echo "    connectivity on either end), not the backend."
else
    echo "FAIL: backend answers on loopback but NOT on $ip."
    echo "      This means Android is not accepting incoming connections"
    echo "      to this app's port on the real network interface -- a"
    echo "      remote device could never reach it either, regardless of"
    echo "      Tailscale. Likely fix: Termux app -> Battery -> Unrestricted,"
    echo "      then force-close and reopen Termux."
fi

echo
echo "-- SSH (port 8022) --"
if pgrep -x sshd >/dev/null 2>&1; then
    echo "OK: sshd is running."
else
    echo "FAIL: sshd is not running. Fix: run 'sshd'"
fi

echo
echo "=== end diagnostic ==="
