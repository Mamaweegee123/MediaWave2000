#!/usr/bin/env bash
# Build fresh, testable MediaWave app bundles for local development.
#
# Output:  Dev Testing/MediaWave.app
#          Dev Testing/MediaWave Converter.app
#
# This script only ever writes inside "Dev Testing/". It never touches
# release/ — release packaging still goes through
# scripts/assemble_mac_release.py and friends.
#
# Usage:
#   ./build_dev.sh          build only
#   ./build_dev.sh --open   build, then open MediaWave.app when done

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

DEV_DIR="$REPO_ROOT/Dev Testing"
RELEASE_DIR="$REPO_ROOT/release"
DIST_DIR="$REPO_ROOT/dist"

OPEN_AFTER_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --open)
            OPEN_AFTER_BUILD=true
            ;;
        *)
            echo "Unknown option: $arg" >&2
            echo "Usage: $0 [--open]" >&2
            exit 1
            ;;
    esac
done

if [[ "$(uname)" != "Darwin" ]]; then
    echo "build_dev.sh builds macOS .app bundles and only runs on macOS." >&2
    exit 1
fi

# Safety net: refuse to run if "Dev Testing" somehow resolves inside release/.
case "$DEV_DIR" in
    "$RELEASE_DIR"*)
        echo "Refusing to continue: Dev Testing path resolves inside release/." >&2
        exit 1
        ;;
esac

echo "== MediaWave Dev Build =="
echo "Repo:       $REPO_ROOT"
echo "Dev output: $DEV_DIR"
echo "(release/ is never touched by this script)"
echo

if [[ -f "$REPO_ROOT/venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$REPO_ROOT/venv/bin/activate"
elif [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.venv/bin/activate"
else
    echo "ERROR: no venv/ or .venv/ found. Set up the project virtualenv first." >&2
    exit 1
fi

if ! command -v pyinstaller >/dev/null 2>&1; then
    echo "ERROR: pyinstaller not found on PATH inside the active virtualenv." >&2
    exit 1
fi

echo "Step 1: Cleaning old Dev Testing output..."
rm -rf "$DEV_DIR"
mkdir -p "$DEV_DIR"
echo "  Cleaned: $DEV_DIR"

echo
echo "Step 2: Rebuilding MediaWave.app (channelsurfer2000.py)..."
pyinstaller --noconfirm dev/MediaWave2000.spec

echo
echo "Step 3: Rebuilding MediaWave Converter.app (mediawave_converter.py)..."
pyinstaller --noconfirm dev/MediaWaveConverter.spec

echo
echo "Step 4: Copying built bundles into Dev Testing/..."
if [[ ! -d "$DIST_DIR/MediaWave2000.app" ]]; then
    echo "ERROR: $DIST_DIR/MediaWave2000.app not found after build." >&2
    exit 1
fi
if [[ ! -d "$DIST_DIR/MediaWaveConverter.app" ]]; then
    echo "ERROR: $DIST_DIR/MediaWaveConverter.app not found after build." >&2
    exit 1
fi
cp -R "$DIST_DIR/MediaWave2000.app" "$DEV_DIR/MediaWave.app"
cp -R "$DIST_DIR/MediaWaveConverter.app" "$DEV_DIR/MediaWave Converter.app"
echo "  Copied MediaWave2000.app -> Dev Testing/MediaWave.app"
echo "  Copied MediaWaveConverter.app -> Dev Testing/MediaWave Converter.app"

echo
echo "Step 5: Copying supporting resources..."
if [[ -d "$REPO_ROOT/bin" ]]; then
    cp -R "$REPO_ROOT/bin" "$DEV_DIR/bin"
    echo "  Copied bin/ (yt-dlp / ffmpeg helpers) alongside the dev bundles."
else
    echo "  No bin/ folder found — skipping (apps still check PATH for yt-dlp/ffmpeg)."
fi

echo
echo "Step 6: Verifying app bundles..."
for app in "MediaWave.app" "MediaWave Converter.app"; do
    if [[ ! -d "$DEV_DIR/$app" ]]; then
        echo "ERROR: $DEV_DIR/$app is missing after build." >&2
        exit 1
    fi
    echo "  OK: $DEV_DIR/$app"
done

echo
echo "Step 7: Confirming release/ is untouched..."
echo "  release/ left as-is at: $RELEASE_DIR"

echo
echo "== Dev build complete =="
echo "MediaWave.app:           $DEV_DIR/MediaWave.app"
echo "MediaWave Converter.app: $DEV_DIR/MediaWave Converter.app"

if [[ "$OPEN_AFTER_BUILD" == true ]]; then
    echo
    echo "Opening MediaWave.app..."
    open "$DEV_DIR/MediaWave.app"
fi
