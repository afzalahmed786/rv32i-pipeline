#!/bin/bash
# Runs LibreLane inside its Docker container, from this directory.
# Usage:  ./flow.sh [librelane options] config.json
# Example: ./flow.sh --run-tag r1 --to OpenROAD.STAPrePNR config.json

IMAGE=ghcr.io/librelane/librelane:3.0.16
PDK_ROOT="$HOME/.ciel"
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"

CMD=(docker run --rm
     -u "$(id -u):$(id -g)" -e HOME=/tmp
     -v "$PROJECT:$PROJECT" -v "$PDK_ROOT:$PDK_ROOT"
     -w "$PROJECT/pnr"
     "$IMAGE" librelane --pdk-root "$PDK_ROOT" -j 8 "$@")

# Until you log out and back in, the docker group only works through sg.
if id -nG | grep -qw docker; then
    "${CMD[@]}"
else
    sg docker -c "$(printf '%q ' "${CMD[@]}")"
fi
