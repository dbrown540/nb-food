# NB Food Index

A working repository of every restaurant, cafe, and grocery store around
North Beach, SF — with walk times from 371 Columbus Ave, price ratings,
health-fit ratings, and hand-verified notes (Apple Pay, cash-only, laptop
policy, best orders).

## Layout

- `data/osm_raw.json` — raw OpenStreetMap POIs for the North Beach bbox
- `data/curated.json` — the hand-verified overlay (edit THIS file):
  - `overrides`: keyed by place name, merged onto OSM entries.
    Fields: `price` (1=$…4=$$$$), `health` (`strong`/`ok`/`trap`),
    `applePay`, `laptops`, `notes`, `menu`, `verified` (date)
  - `extras`: places OSM doesn't have yet (needs `lat`/`lon`)
- `data/places.json` — build output: merged, deduped, walk-annotated
- `docs/index.html` — self-contained browsable viewer (open in a browser;
  search, category/health filters, "curated only" toggle)
- `menus/` — saved menu PDFs, referenced from curated `menu` fields
- `scripts/fetch.sh` — refresh OSM data and rebuild
- `scripts/build.py` — merge + emit places.json and the viewer

## Usage

```sh
python3 scripts/build.py   # rebuild after editing data/curated.json
./scripts/fetch.sh         # refresh OSM data too (network)
open docs/index.html       # browse
```

Add a verdict after visiting a place: put an entry in
`data/curated.json` → `overrides` (key = the place's name, roughly as
OSM spells it; matching is case/accent/punctuation-insensitive), rebuild.

Walk times are straight-line at 80 m/min — treat as a floor.
