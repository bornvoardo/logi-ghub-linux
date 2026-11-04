#!/bin/sh
# Install logi-ghub-linux for the current user.
#   ./scripts/install.sh            app, launchers, desktop entry, user service (not enabled)
#   ./scripts/install.sh --udev     also install the udev rule (asks for sudo)
#   ./scripts/install.sh --uninstall
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
PREFIX="$HOME/.local"
VENV="$PREFIX/share/logi-ghub-linux/venv"
BIN="$PREFIX/bin"
APPS="$PREFIX/share/applications"
DATA="$PREFIX/share/logi-ghub-linux"
UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
DESKTOP=io.github.theo_antonescu.LogiGhubLinux.desktop

if [ "${1:-}" = "--uninstall" ]; then
    systemctl --user disable --now logi-ghubd.service 2>/dev/null || true
    rm -f "$BIN/logi-ghub" "$BIN/logi-ghub-cli" "$BIN/logi-ghubd" "$BIN/logi-ghub-tray" "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/logi-ghub-tray.desktop" "$APPS/$DESKTOP" "$UNITS/logi-ghubd.service"
    rm -f "$DATA/kwin/logi-ghub-focus.js"
    rm -rf "$VENV"
    echo "Removed. Profiles and backups are kept in ~/.config/logi-ghub-linux and ~/.local/share/logi-ghub-linux."
    exit 0
fi

# The GUI needs GTK 4 + libadwaita through the system's PyGObject.
if ! /usr/bin/python3 -c 'import gi; gi.require_version("Gtk","4.0"); gi.require_version("Adw","1")' 2>/dev/null; then
    cat >&2 <<'EOF'
Missing GTK 4 / libadwaita Python bindings. Install them for your distribution:
    Fedora:         sudo dnf install python3-gobject gtk4 libadwaita
    Ubuntu/Debian:  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
    Arch:           sudo pacman -S python-gobject gtk4 libadwaita
EOF
    exit 1
fi

/usr/bin/python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/pip" install --quiet --no-build-isolation --upgrade "$REPO" 2>/dev/null || "$VENV/bin/pip" install --quiet --upgrade "$REPO"

mkdir -p "$BIN" "$APPS" "$UNITS"
for exe in logi-ghub logi-ghub-cli logi-ghubd logi-ghub-tray; do
    ln -sf "$VENV/bin/$exe" "$BIN/$exe"
done
sed "s|^Exec=logi-ghub|Exec=$BIN/logi-ghub|" "$REPO/data/$DESKTOP" > "$APPS/$DESKTOP"
install -m 644 "$REPO/data/systemd/logi-ghubd.service" "$UNITS/"
install -d "$DATA/kwin"
install -m 644 "$REPO/data/kwin/logi-ghub-focus.js" "$DATA/kwin/"
systemctl --user daemon-reload 2>/dev/null || true

if [ "${1:-}" = "--udev" ]; then
    sudo install -m 644 "$REPO/data/udev/70-logi-ghub-linux.rules" /etc/udev/rules.d/
    sudo udevadm control --reload
    sudo udevadm trigger --action=add --subsystem-match=hidraw
    sudo udevadm trigger --action=add --subsystem-match=misc --sysname-match=uinput
    sudo udevadm trigger --action=change --subsystem-match=input --sysname-match='event*'
fi

echo "Installed. Start \"Logitech G devices\" from the app menu, or run logi-ghub / logi-ghub-cli."
echo "For host-mode profiles (macros beyond on-board memory, software lighting) enable the service:"
echo "    systemctl --user enable --now logi-ghubd"
[ -e /etc/udev/rules.d/70-logi-ghub-linux.rules ] || echo "Device access: re-run with --udev to install the udev rule."

# The commands live in ~/.local/bin, which many shells do not search.
case ":$PATH:" in
    *":$BIN:"*) ;;
    *)
        shell_rc=""
        case "$(basename "${SHELL:-sh}")" in
            zsh)  shell_rc="$HOME/.zshrc" ;;
            bash) shell_rc="$HOME/.bashrc" ;;
            fish) shell_rc="$HOME/.config/fish/config.fish" ;;
        esac
        echo ""
        echo "$BIN is not in your PATH, so the commands cannot be found yet."
        if [ "$(basename "${SHELL:-sh}")" = "fish" ]; then
            echo "Add this line to $shell_rc:"
            echo "    fish_add_path $BIN"
        elif [ -n "$shell_rc" ]; then
            echo "Add this line to $shell_rc:"
            echo "    export PATH=\"$BIN:\$PATH\""
        else
            echo "Add $BIN to your PATH."
        fi
        echo "Or use the full path for now: $BIN/logi-ghub-cli list"
        ;;
esac
