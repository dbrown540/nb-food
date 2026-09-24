# How nb-food decides

_Generated from spine/ by `python3 scripts/spine_gate.py --write-story`. Do not edit._

## Stage: menus

Each place's menu or store product list is read from the place's own published source into items with their listed words and prices. A list older than the kept age is flagged, and once past due it stops the build until it is refreshed or an extension is ruled. Every item is then read for a fixed vocabulary of food attributes, and each attribute is answered present, absent or unknown from the item's own words.

### menu-extraction

> A menu item is recorded only as its place's source lists it, with the source's own words and price, and nothing is inferred or completed.

- grain: menu; tier: T3
- decided by: prompt spine/prompts/menu-extract.md
- enforced by: scripts/check_data.py `check_menu_extraction`, on reject: halt
- why not lower: Menus arrive as web pages, PDFs and photographs with no shared structure; no parser or closed answer set covers them. A store's structured product feed is parsed by code instead and records that basis.
- known gap, review by 2026-12-31: Menu files dated before the basis cutoff were extracted in agent sessions that recorded no model or prompt, and no gate re-reads a source to confirm an item's words and price.
- binding: spine/bindings.json `menu-extraction`
- cases:
  - a file with every row well formed and its extraction basis: expect {"problems": 0}
  - a file dated after the cutoff with no extraction basis: expect {"problems": 1}
  - a price written as text: expect {"problems": 1}

### menu-freshness

> A menu older than the kept age is flagged, and once past due it stops the build until it is refreshed or an extension is ruled.

- grain: menu; tier: T1
- decided by: code scripts/freshness.py `menu_age`
- enforced by: scripts/check_data.py `check_menu_freshness`, on reject: halt
- binding: spine/bindings.json `menu-freshness`
- binding: spine/bindings.json `time`
- reads: menu-extraction (as_of, per menu)
- cases:
  - read nine days ago: expect {"status": "current"}
  - inside the warning window: expect {"status": "due-soon"}
  - past its due date: expect {"status": "stale"}

### item-attributes

> An item has an attribute only when its own words say so, lacks it only when its own words rule it out, and is otherwise unknown; the absence of a word is never evidence of absence.

- grain: item; tier: T2
- decided by a cascade routed by scripts/tag_items.py `route_attribute`:
  - T2: repeated readings agree, and a present answer quotes the item (spine/battery/item-attributes.md)
    - known gap, review by 2026-12-31: No labelled sample has been measured against this battery; a spot check is not a measurement.
  - T1: readings disagree, or a present answer quotes nothing in the item: unknown (scripts/tag_items.py `route_attribute`)
- enforced by: scripts/tag_items.py `check_item_tags`, on reject: halt
- binding: spine/bindings.json `item-attributes`
- binding: data/attributes.json `attributes`
- reads: menu-extraction (items, per menu)
- cases:
  - words that name the frying: expect {"tagged": true, "answers": {"fried": "yes"}}
  - a dish whose parts are not listed: expect {"tagged": true, "answers": {"nuts": "unknown", "seeds": "unknown", "fried": "unknown"}}
  - a name that contains a nut word but is not a nut: expect {"tagged": true, "answers": {"nuts": "no"}}
  - two readings quote the item: at the agreement bar: expect {"answer": "yes", "agree": 2}
  - one reading quotes the item: just below the bar: expect {"answer": "unknown"}
  - every reading says present but quotes words the item does not have: expect {"answer": "unknown"}
  - absent in all but one reading: just below the bar for absent: expect {"answer": "unknown"}

Consumers:
- item-table (data/menu_items.json) reads menu-extraction
- item-tags (data/item_tags.json) reads item-attributes

## Stage: nutrients

Every item in the item table is given a source for its nutrients: its own package label when one is on file, else the public USDA record that is the same food, a single food for a single food and a surveyed mixed dish for a restaurant dish with an estimated serving weight, and otherwise none, so its nutrients stay unknown. The public records are read once and kept as dated copies.

### food-mapping

> An item's nutrients come from its own package label when one is on file, else from the public food record that is the same food, and are otherwise unknown, never zero.

- grain: item; tier: T2
- decided by a cascade routed by scripts/map_foods.py `route_mapping`:
  - T0: a package label is on file (data/labels)
  - T1: no public record shares a word with the item: unmapped (scripts/map_foods.py `decide`)
  - T2: every reading names the same record (spine/battery/food-map.md)
    - known gap, review by 2026-12-31: No labelled sample has been measured against this battery; a spot check is not a measurement.
  - T1: readings disagree or name no record: unmapped (scripts/map_foods.py `route_mapping`)
- enforced by: scripts/map_foods.py `check_food_map`, on reject: halt
- binding: spine/bindings.json `food-mapping`
- reads: menu-extraction (items, per menu)
- cases:
  - a package label on file: expect {"kind": "label"}
  - a single food with its own public record: expect {"kind": "usda-single-food", "fdcId": 2710824}
  - a restaurant dish with a surveyed dish of the same name: expect {"kind": "usda-mixed-dish-estimate", "fdcId": 2706401}
  - a dish the public records do not have: stays unmapped: expect {"kind": "unmapped", "reason": "no candidate is the same food"}
  - a name that shares no word with any record: expect {"kind": "unmapped"}
  - every reading names one record: at the bar: expect {"candidate": 3, "portion": 1}
  - two of three readings: just below the bar: expect {"candidate": null}
  - the record agreed, the portion split: expect {"candidate": 3, "portion": null}
  - a choice that is not on the list: expect {"candidate": null}

Consumers:
- food-map (data/food_map.json) reads food-mapping

## Stage: places

Each place near the door takes the city's inspection history only when a registration can be defended as the same business, by name and street address or by name and location, and otherwise takes none. A place the owner has visited carries the owner's dated verdict, and nothing else sets or changes it.

### inspection-match

> A place takes a city inspection record only when the names relate and the street address or the location corroborates them; without a defensible match the place has no record.

- grain: place; tier: T1
- decided by: code scripts/inspections.py `match_poi`
- known gap, review by 2026-12-31: No gate re-checks a stored match against its corroborating evidence; the confidence the matcher writes is read as-is by the build.
- binding: spine/bindings.json `inspection-match`
- cases:
  - related names and the same street address: expect {"confidence": "name+address"}
  - the same name in the same building, no address to compare: expect {"confidence": "name-only"}
  - the same name across the city: expect {"confidence": "none"}

### curated-verdict

> A place's verdict is the owner's own dated ruling from a visit; nothing else sets or changes it, and it stands only until its review date.

- grain: place; tier: H
- decided by: ruling data/curated.json `#overrides`
- enforced by: scripts/check_data.py `check_verdicts`, on reject: halt
- binding: spine/bindings.json `curated-verdict`
- cases:
  - a verdict with its ruling date: expect {"fails": 0, "warns": 0}
  - a verdict with no ruling date: expect {"fails": 1}
  - a verdict past its review date: expect {"fails": 1}

Consumers:
- viewer (docs/index.html) reads inspection-match, curated-verdict

## Integrity invariants

### layers-keyed-to-places

> Every enrichment record belongs to exactly one place in the index, and every place has a street-risk record.

- scope: places
- enforced by: scripts/check_data.py `check_layer_keys`, on reject: halt
- cases:
  - every record keyed to a place: expect {"problems": 0}
  - a risk record for no place: expect {"problems": 1}

### derived-not-transcribed

> Every derived table is exactly what its derivation writes from its sources; none is edited by hand.

- scope: menus
- enforced by: scripts/check_data.py `check_derived`, on reject: halt
- cases:
  - the committed table equals the derivation: expect {"stale": false}
  - a row typed into the committed table: expect {"stale": true}

### public-content

> Nothing tracked describes who uses the index: only places, their public records and their own words.

- scope: menus, places
- enforced by: scripts/check_public.py `scan_text`, on reject: halt
- cases:
  - a menu line: expect {"hits": 0}
  - a regimen word in a menu file: expect {"hits": 1}

### usda-records-cached

> Every public food record the index relies on is a whole, dated copy kept in the repository, and a lookup reads that copy.

- scope: nutrients
- enforced by: scripts/usda.py `check_usda_cache`, on reject: halt
- cases:
  - a whole record named by its id: expect {"problems": 0}
  - a record with no fetch date: expect {"problems": 1}
  - a record filed under another id: expect {"problems": 1}

## Rulings

- **attribute-vocabulary** (data/attributes.json): by owner on 2026-09-23, review by 2027-03-23. the nine attribute ids named in the owner's brief of 2026-09-23; definitions drafted for the owner's review, tightened 2026-09-23 on the owner's ruling: absent only when certain, pine nuts count as nuts, the three high attributes answered from a food's nature
- **attribute-agreement** (item-attributes): by owner on 2026-09-23, review by 2027-03-23. present needs two of three readings quoting the item, absent needs all three: an absent answer claims more than the words usually show, so it takes full agreement
- **menu-max-age** (menu-freshness): by owner on 2026-09-23, review by 2027-03-23. restaurant menus and store prices change seasonally; half a year is the proposed kept age
- **food-aliases** (food-mapping): by owner on 2026-09-23, review by 2027-03-23. the most frequent menu words missing from the USDA descriptions on 2026-09-23 (penne, prawn, nigiri, donut...), each given the words USDA uses; an alias only adds candidates, the classifier still decides
