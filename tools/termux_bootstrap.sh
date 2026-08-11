#!/data/data/com.termux/files/usr/bin/sh
# Bootstrap the Cumnation reference backend (mock_server.py) in Termux,
# supervised so it survives Doze and restarts on crash, and start sshd so the
# box can be administered remotely afterwards.
#
# Safe to re-run: every step here is idempotent.
#
# Usage (typed once, on the device itself):
#   pkg install -y curl && curl -sL \
#     https://raw.githubusercontent.com/Deegan4/KodiCum/main/tools/termux_bootstrap.sh | sh
#
# After it finishes, run `passwd` to set an SSH password -- that step can't
# be scripted without putting a plaintext password in this file.

set -u

REPO_DIR="$HOME/KodiCum"
PORT="${CUMNATION_PORT:-8765}"

echo "==> Installing packages"
pkg install -y python git curl openssh termux-services

echo "==> Fetching KodiCum"
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull
else
    git clone https://github.com/Deegan4/KodiCum.git "$REPO_DIR"
fi

echo "==> Installing the cumnation service (port $PORT)"
mkdir -p "$PREFIX/var/service/cumnation"
cat > "$PREFIX/var/service/cumnation/run" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
exec python "$REPO_DIR/plugin.video.cumnation/resources/lib/mock_server.py" $PORT 2>&1
EOF
chmod +x "$PREFIX/var/service/cumnation/run"
sv-enable cumnation
sv up cumnation

echo "==> Starting sshd (port 8022)"
sshd

echo
echo "Done."
echo "  - Backend:   sv status cumnation   (dashboard at http://<this-device-ip>:$PORT/)"
echo "  - SSH login: run 'passwd' now to set a password, then connect with"
echo "               ssh -p 8022 $(whoami)@<this-device-ip>"
