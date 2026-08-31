#!/bin/sh
# Refresh OSM data for the North Beach bbox, then rebuild.
set -e
cd "$(dirname "$0")/.."
curl -s --max-time 120 -X POST -d @scripts/overpass_query.txt \
  https://overpass-api.de/api/interpreter -o data/osm_raw.json
python3 scripts/build.py
