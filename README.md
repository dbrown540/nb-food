# NB Food Index

A working repository of every restaurant, cafe, and grocery store around
North Beach, SF — with walk times from 371 Columbus Ave, price ratings,
a go-to / fine / occasional verdict, and hand-verified notes (Apple Pay,
cash-only, laptop policy, best orders).

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
- **Products** — `data/products/<store-slug>.json`: a store's packaged food and drink with price and pack size, from the store's own product feed (Trader Joe's, 401 Bay St: `scripts/tj_products.py`).
- **Gates** — `scripts/check_public.py` exits 1 if any tracked file mentions personal-context terms (this repo is public and describes restaurants and public datasets only; the city's DPH text and raw OSM data are exempt from the topic patterns, never from the owner patterns). `scripts/check_data.py` exits 1 on integrity problems in the built data (duplicate keys, layer entries that match no place, a stale menus index). Both run from `.githooks/pre-commit`; enable it once per clone with `git config core.hooksPath .githooks`.

## Interfaces (consumers pin a commit)

Everything below is derived and gated; read it at a pinned commit, never at a
moving branch. A schema version changes only when a field is removed, renamed or
changes meaning; added fields keep the version.

### Item table: `data/menu_items.json` (schema_version 1)

`scripts/menu_items.py` derives it from `data/menus/*.json` and
`data/products/*.json`; `--check` (run by `check_data.py`) fails on any hand edit.
`{"schema_version": 1, "rows": [...]}`, one row per line, sorted by `id`:

| field | meaning |
|---|---|
| `id` | stable: slug(place key) + `--` + slug(item name); a name repeated at one place gets `-2`, `-3`… in (section, description, size, price) order |
| `place` | the place's `key` in `data/places.json` |
| `kind` | `menu` (a restaurant or cafe menu) or `product` (a store's packaged product) |
| `section` | the menu section, or the store's category path joined with ` / ` |
| `name`, `description` | the source's own words (`description` is `""` when there are none) |
| `size` | pack size for a product (`"16 Oz"`), `""` for a menu item |
| `price` | USD as listed, or `null` when the source lists none |
| `source`, `as_of` | where and when the list was read |
| `status` | the list's status: `ok` (full, priced) or `partial` |

### Store product lists: `data/products/<store-slug>.json`

`{name (place key), addr, source_url, source, as_of, status, extraction, products: [...]}`,
written by a pull script (`scripts/tj_products.py` for Trader Joe's, food and
drink only), never by hand. Each product: `section`, `name`, `description`,
`size` (as the store prints it), `price` (USD), and what the size means
(`scripts/packages.py`):

| field | meaning |
|---|---|
| `sold_by` | `weight` (oz, lb), `volume` (fl oz, mL, L, pint, quart), `each` (priced per piece: "Bananas (1 Each)"), `count` (a dozen, a box of 20 tea bags) |
| `package_g` | package weight in grams when `sold_by` is `weight` ("1 Lb" = 453.6), else null |
| `package_ml` | package volume in millilitres when `sold_by` is `volume`, else null |
| `units` | pieces in the package when `sold_by` is `each` or `count` (1 Doz = 12), else null |

**Coverage (checked 2026-09-23).** The list is Trader Joe's online product
catalog (its product API), filtered to what the catalog marks available at the
401 Bay St store, food and drink departments only. The catalog is one list of
2,520 products for all stores; 1,820 were marked available at this store (1,818
at the pull), and dropping the non-food departments (Everything Else, Flowers &
Plants) leaves the 1,700 here. The catalog is not a record of the shelves: some
items the store sells are not in it at all. A search of the whole catalog
(available or not) found no liquid egg whites in a carton and no frozen cooked
jasmine rice (only dry jasmine rice, 3 lb). Applesauce pouches are listed, as
"Organic Apple … Fruit Sauce Crushers" (four flavors), and plain sliced
sourdough as "Sourdough Bread Sliced" and "Sourdough Sandwich Bread" (24 oz).
Treat an item missing here as unknown, not as not sold.

### Attribute tags: `data/item_tags.json` (schema_version 1)

`scripts/tag_items.py` derives it from the item table, the pinned readings in
`data/tag_pins.jsonl` and the route rule; `--check` fails on any hand edit.
Vocabulary and definitions: `data/attributes.json` (fried, spicy, acidic, nuts,
seeds, raw, fiber_high, sodium_high, sugar_high).

- `basis`: `model`, `battery` (content hash of the question battery + vocabulary),
  `sampling`, and `hash` (the basis id the pins are keyed by).
- `rule`: readings per item (`samples`) and the agreement needed for yes (`agreeYes`) and no (`agreeNo`).
- `rows`: `{id, text_hash, tags: {<attribute>: {answer, agree, words?}}}`, where
  `answer` is `yes` / `no` / `unknown`; `agree` is how many readings back it;
  `words` are the item's own words behind a yes (always present) or a no (when quoted).
  **unknown means the item's words cannot settle it. It never means no.**
- `untagged`: `{id, text_hash, reason}` for items with no pinned readings under the current basis.

Readings are pinned by (item text hash, basis): rebuilding never calls the
model, and only new or changed item text is read (`--run`). The basis names
the transport: `claude-code-cli` (headless Claude Code on the signed-in plan)
or the Anthropic API; readings from the two are never mixed.

### USDA records: `data/usda/<fdcId>.json` (schema_version 1)

A dated copy of one USDA FoodData Central record, fetched once by
`scripts/usda.py` (API batch endpoint, 20 ids a call) and never refetched
while the file exists. Fields, in order: `fdcId`, `dataType` (Foundation,
SR Legacy or Survey (FNDDS)), `description`, `publicationDate` (the API's),
`fetched_at`, `nutrients` (every nutrient the record carries, per 100 g:
`{id, number, name, unit, amount}`), `portions` (`{description, gram_weight}`).
`data/usda_index.json` lists the entries mapping may choose from (descriptions,
categories and portions from USDA's bulk releases, named in `releases`).

### Nutrients: `data/nutrients.json` (schema_version 1)

One row per USDA record that `data/food_map.json` references, keyed by `fdcId`:
`dataType`, `description`, `per_100g` {`energy_kcal`, `protein_g`, `fiber_g`,
`sodium_mg`, `sugars_g`, `fat_g`, `saturated_fat_g`, `carbohydrate_g`} and
`nutrient_ids` (the USDA nutrient id each value came from). Ids, in fallback
order: energy 1008, then 2047, then 2048 (Atwater general, then specific: most
Foundation records carry no 1008); protein 1003; fat 1004; carbohydrate 1005
(by difference, so it already includes fiber); fiber 1079; sugars 2000, then
1063; sodium 1093; saturated fat 1258. A value the record does not carry is
`null`; zero only where USDA reports zero.

Written only by `scripts/usda_nutrients.py` from the bulk releases in
`data/usda_bulk/` (named with their dates in `basis.releases`, with
`basis.inputs_sha256` over every CSV row read); deterministic. `--check`
rebuilds and compares when the bulk releases are present; in a checkout
without them it checks every value against the committed per-record copies in
`data/usda/` (fetched from the FoodData Central API), within the precision
the API prints. `check_data.py` fails the build when a mapped record has no
row, a row has no mapping, or a value is outside its bounds (per 100 g:
energy 0 to 902 kcal; protein, fat, carbohydrate, fiber, sugars, saturated fat
0 to 100 g; sodium 0 to 40,000 mg; protein + fat + carbohydrate at most 105 g,
fiber left out of the sum because carbohydrate by difference already counts it).

Known difference from the API copies: for Green onion, raw (2727585) the bulk
Foundation release carries no fiber while the API copy of the same
publication does; the table says null. `usda_nutrients.py --check` lists such
notes.

Nutrients for a mapped item = its row's `per_100g` × `grams` / 100 (grams from
`data/food_map.json`), or its label.

### Package labels: `data/labels/<item id>.json`

The label as printed, per serving: `{id, source, as_of, serving, serving_g,
nutrients: [{name, unit, amount}]}` (see `data/labels/README.md`). Exact for the
nutrients it lists; every other nutrient of that item is unknown.

### Food map: `data/food_map.json` (schema_version 1)

`scripts/map_foods.py` derives it from the item table, the labels, the USDA
index and the pinned readings in `data/food_map_pins.jsonl`; `--check` fails
on any hand edit. `basis`, `index` (the USDA releases), `rule`, then:

- `rows`: `{id, kind, ...}` where `kind` is
  - `label`: nutrients from `label` (exact for what it lists), `grams` = its serving;
  - `usda-single-food`: `fdcId` names a record of a plain food (Foundation,
    SR Legacy, or a Survey entry filed in a plain-food group such as "Dried
    fruits"); its per-100 g values match the food;
  - `usda-mixed-dish-estimate`: `fdcId` names a Survey (FNDDS) entry filed in a
    dish group (bindings `dishCategories`), standing in for the place's own
    recipe; **an estimate**;
  - `unmapped`: no record; nutrients unknown (**never zero**), with `reason`.
  - `grams`, `grams_basis`: a product's package weight (`package`) or, for a
    menu item, the chosen USDA portion (`estimated portion: 1 cup`), else absent.
  - `estimate`: true for every mixed-dish match and every restaurant or cafe
    menu item (someone else's recipe and portion), false for a label or a
    store product matched to a plain food. Show `estimate: true` as an estimate.
  - `category`: the record's USDA food group; `agree`: readings behind the
    answer; `key`: hash of the exact model input.
- `unread`: `{id, key, reason}` for items with no pinned readings under the current basis.

Nutrients for an item: see "Nutrients" (`data/nutrients.json`) above.

## Decisions: the spine (`spine/`)

Every decision the index makes is registered in `spine/` with its tier, its
decider, its enforcer and its canonical cases: `spine/tiers.json`,
`spine/stages/*.json`, `spine/invariants.json`, `spine/bindings.json` (thresholds,
local facts and owner rulings). `spine/STORY.md` is generated from them.
`scripts/spine_gate.py` fails the build when the registry and the code disagree.
Changes land on a green gate. Only a change of stance (a principle's statement,
grain or scope and tier, or a ruling) needs the owner's consent, owed within
30 days of landing; a commit signed with the key in `spine/owner_signers` is
that consent.

## Layout

- `data/osm_raw.json` — raw OpenStreetMap POIs for the North Beach bbox
- `data/curated.json` — the hand-verified overlay (edit THIS file):
  - `overrides`: keyed by place name, merged onto OSM entries.
    Fields: `price` (1=$…4=$$$$), `verdict` (`pick`/`ok`/`treat`),
    `applePay`, `laptops`, `notes`, `menu`, `verified` (date)
  - `extras`: places OSM doesn't have yet (needs `lat`/`lon`)
- `data/places.json` — build output: merged, deduped, walk-annotated, with
  `neighborhood` + `key` on every row
- `data/neighborhoods.geojson` — the polygons + Bay Street line used for
  `neighborhood` (`scripts/fetch_neighborhoods.py`)
- `docs/index.html` — self-contained browsable viewer (open in a browser;
  search, category/verdict/neighborhood filters, "curated only" toggle)
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
python3 scripts/check_data.py       # integrity gate on the built data (+ menu freshness, verdicts, tags)
python3 scripts/menu_items.py       # rebuild the item table after a menu or product change
python3 scripts/tag_items.py        # rebuild the tags from pins; .venv/bin/python ... --run reads new items
python3 scripts/spine_gate.py       # registry gate; --write-story after editing spine/
python3 -m unittest discover -s tests   # unit tests + the gate's negative cases
git config core.hooksPath .githooks # once per clone: run every gate on every commit
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
  is the raw Overpass response with provenance (mirror, timing, quadrants);
  it is gitignored (raw OSM tags carry business contact details) and
  regenerated by the fetch script.
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
