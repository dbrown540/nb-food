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

## Citywide base + street risk (added 2026-09-09)

- `data/sf_places.json` — every OSM restaurant / cafe / fast_food and
  grocery-type shop (supermarket, greengrocer, convenience, grocery,
  health_food, butcher, seafood, bakery, deli) in San Francisco, one row per
  OSM element (`osm_type` + `osm_id`; node+way duplicates are NOT merged).
  `data/sf.db` table `places` holds the same rows stamped `fetched_at` +
  `source` (append-only: each pull adds a snapshot). `data/sf_osm_raw.json`
  is the raw Overpass response with provenance (mirror, timing, quadrants).
  `scripts/fetch_sf_pois.py` reproduces it (`--cached` re-normalizes the
  saved raw); query template in `scripts/overpass_sf_query.txt`.
- `data/crime/poi_street_risk.json` — for each of the 374 North Beach places,
  SFPD incidents within 150 m over the trailing 365 days, split into
  violent / property / drug-disorder, with `per_month`, a percentile rank
  within the set, `nearest_incident_m`, `source`, `window`, `as_of`.
  Built from ONE bulk DataSF pull (`data/crime/nb_incidents_365d.json`,
  dataset `wg3w-h783` on data.sf.gov, NB bbox padded 200 m) by
  `scripts/street_risk.py` (`--cached` recomputes without network).
  Caveat: SFPD geocodes to intersections, so a `total` of 0 with
  `nearest_incident_m` > 150 is a geocoding gap, not a calm block.
