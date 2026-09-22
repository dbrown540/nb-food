# NB Food Index

A working repository of every restaurant, cafe, and grocery store around
North Beach, SF — with walk times from 371 Columbus Ave, price ratings,
health-fit ratings, and hand-verified notes (Apple Pay, cash-only, laptop
policy, best orders).

## Enrichment layers (merged into places.json by build.py, by POI `key`)

Every place carries `neighborhood` and `key`. `key` == `name` unless several
places share a name (chains), then `"Name (address)"`; the layers below are
keyed by it. Coverage numbers per neighborhood are in
`docs/nb-food-coverage-report.md` (2026-09-22).

- **Neighborhoods** — `data/neighborhoods.geojson` (`scripts/fetch_neighborhoods.py`): the DataSF Analysis Neighborhood polygons around 371 Columbus plus the Bay Street centerline from OSM. The city's 41-neighborhood set folds Fisherman's Wharf into North Beach / Russian Hill, so a POI in either polygon north of Bay Street is labeled Fisherman's Wharf (the one non-official boundary here).
- **Street risk** — `data/crime/poi_street_risk.json` (`scripts/street_risk.py`): SFPD incidents within 150 m over the trailing 365 days per POI, split violent / property / drug, with a percentile across the whole set. The pull bbox is the POI set's bbox + 200 m. Caveat: SFPD snaps incidents to intersections, so a POI 160+ m from any intersection point reads artificially low (`nearest_incident_m`); Pier 39 and the piers read 0 for this reason.
- **DPH inspections** — `data/inspections/poi_inspections.json` (`scripts/fetch_inspections.py`, `scripts/inspections.py`): three SF DPH open datasets — numeric scores 2016–2019, and placard results (Pass / Conditional Pass / Closure + violation counts) for 2020–2023 and 2024–present (monthly). Match confidence per POI is `name+address`, `name-only` or `none`. Current data lags the city's lookup tool by months for some businesses.
- **Menus** — `data/menus/*.json` (`scripts/menus_report.py`, `scripts/menus_index.py`): item/price extractions from restaurants' own sites, PDFs, menu images or their own ordering pages, each with `source` + `as_of` + `status` (ok / partial / not_found / skipped). `index.json` is DERIVED from the files by `menus_index.py` (`--check` in a pre-commit step keeps it current); never hand-edit it. A file's `name` must equal the POI `key`.
- **Citywide base** — `data/sf_places.json` / `data/sf.db` (`scripts/fetch_sf_pois.py`): all 3,932 restaurants, cafes and grocery shops in SF from OSM. `build.py` pulls the rows whose polygon is in `EXPANSION` (North Beach, Chinatown, Fisherman's Wharf, Russian Hill) into the index, deduplicating against the North Beach bbox set by normalized name within 150 m.
- **Publish gate** — `scripts/check_public.py`: exits 1 if any layer file or report mentions personal-context terms (this repo is public and describes restaurants and public datasets only). Run it before every commit.

## Layout

- `data/osm_raw.json` — raw OpenStreetMap POIs for the North Beach bbox
- `data/curated.json` — the hand-verified overlay (edit THIS file):
  - `overrides`: keyed by place name, merged onto OSM entries.
    Fields: `price` (1=$…4=$$$$), `health` (`strong`/`ok`/`trap`),
    `applePay`, `laptops`, `notes`, `menu`, `verified` (date)
  - `extras`: places OSM doesn't have yet (needs `lat`/`lon`)
- `data/places.json` — build output: merged, deduped, walk-annotated, with
  `neighborhood` + `key` on every row
- `data/neighborhoods.geojson` — the polygons + Bay Street line used for
  `neighborhood` (`scripts/fetch_neighborhoods.py`)
- `docs/index.html` — self-contained browsable viewer (open in a browser;
  search, category/health filters, "curated only" toggle)
- `menus/` — saved menu PDFs, referenced from curated `menu` fields
- `data/menus/<slug>.json` — extracted menus (items, prices, short
  descriptions) per restaurant/cafe, each with `source` + `as_of`;
  `data/menus/index.json` is the manifest (status ok/partial/not_found/skipped)
- `scripts/menus_report.py` — menu coverage report
- `scripts/menus_index.py` — regenerate `data/menus/index.json` from the files
- `scripts/check_public.py` — publish gate (see Enrichment layers)
- `scripts/fetch.sh` — refresh OSM data and rebuild
- `scripts/build.py` — merge + emit places.json and the viewer

## Usage

```sh
python3 scripts/build.py            # rebuild after editing data/curated.json
./scripts/fetch.sh                  # refresh OSM data too (network)
python3 scripts/menus_index.py      # after adding/editing data/menus/<slug>.json
python3 scripts/street_risk.py      # refresh SFPD pull (network); --cached recomputes
python3 scripts/inspections.py      # re-match DPH data (after fetch_inspections.py)
python3 scripts/check_public.py     # publish gate; must exit 0 before committing
open docs/index.html                # browse
```

Refresh order after a POI-set change: `build.py` (POIs + keys) → `street_risk.py`
→ `inspections.py` → `menus_index.py` → `build.py` again (merges the layers).

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
- `data/crime/poi_street_risk.json` — for every place in the index,
  SFPD incidents within 150 m over the trailing 365 days, split into
  violent / property / drug-disorder, with `per_month`, a percentile rank
  within the set, `nearest_incident_m`, `source`, `window`, `as_of`.
  Built from ONE bulk DataSF pull (`data/crime/nb_incidents_365d.json`,
  dataset `wg3w-h783` on data.sf.gov, POI bbox padded 200 m) by
  `scripts/street_risk.py` (`--cached` recomputes without network and refuses
  a cached pull whose bbox no longer covers the POI set).
  Caveat: SFPD geocodes to intersections, so a `total` of 0 with
  `nearest_incident_m` > 150 is a geocoding gap, not a calm block.
