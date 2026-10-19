#!/bin/sh
# Installs a verified, unprivileged PHP runtime on Debian cloud machines when
# PHP is unavailable. Existing system PHP is preferred. No Composer required.
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RUNTIME_DIR=${VELA_RUNTIME_DIR:-/workspace/.runtime}
if command -v php >/dev/null 2>&1; then
    exec php "$APP_DIR/scripts/check.php"
fi
if [ -x "$RUNTIME_DIR/php/bin/php" ]; then
    exec "$RUNTIME_DIR/php/bin/php" "$APP_DIR/scripts/check.php"
fi
if [ ! -f /etc/debian_version ] || ! command -v dpkg-deb >/dev/null 2>&1; then
    echo 'Install PHP 8.2+ with PDO SQLite using your operating system package manager.' >&2
    exit 1
fi
mkdir -p "$RUNTIME_DIR/apt/lists/partial" "$RUNTIME_DIR/apt/cache/archives/partial" "$RUNTIME_DIR/php/bin"
cat > "$RUNTIME_DIR/apt/sources.list" <<'SOURCES'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://security.debian.org/debian-security trixie-security main
SOURCES
apt-get -o Debug::NoLocking=1 -o Dir::Etc::sourcelist="$RUNTIME_DIR/apt/sources.list" -o Dir::Etc::sourceparts=- -o Dir::State::lists="$RUNTIME_DIR/apt/lists" -o Dir::Cache="$RUNTIME_DIR/apt/cache" update
apt-get -o Debug::NoLocking=1 -o Dir::Etc::sourcelist="$RUNTIME_DIR/apt/sources.list" -o Dir::Etc::sourceparts=- -o Dir::State::lists="$RUNTIME_DIR/apt/lists" -o Dir::Cache="$RUNTIME_DIR/apt/cache" --download-only -y install php8.4-cli php8.4-sqlite3
for package in "$RUNTIME_DIR"/apt/cache/archives/*.deb; do
    case "$(basename "$package")" in
        php*|libargon2*) dpkg-deb -x "$package" "$RUNTIME_DIR/php" ;;
    esac
done
EXTENSION_DIR=$(find "$RUNTIME_DIR/php/usr/lib/php" -type f -name pdo_sqlite.so -exec dirname {} \;)
LIBRARY_DIR="$RUNTIME_DIR/php/usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)"
LOADER=$(ldd "$RUNTIME_DIR/php/usr/bin/php8.4" | awk '/ld-linux/ {print $1; exit}')
cat > "$RUNTIME_DIR/php/bin/php" <<WRAPPER
#!/bin/sh
exec "$LOADER" --library-path "$LIBRARY_DIR" "$RUNTIME_DIR/php/usr/bin/php8.4" -n -d extension_dir="$EXTENSION_DIR" -d extension=pdo -d extension=pdo_sqlite -d extension=sqlite3 -d session.save_path=/tmp "\$@"
WRAPPER
chmod +x "$RUNTIME_DIR/php/bin/php"
exec "$RUNTIME_DIR/php/bin/php" "$APP_DIR/scripts/check.php"
