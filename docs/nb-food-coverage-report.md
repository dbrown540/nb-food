# nb-food coverage report — 2026-09-22

Scope: finish North Beach menu coverage, extend every enrichment layer to the
walk-radius neighborhoods (Chinatown, Fisherman's Wharf, Russian Hill), and
list what stayed blocked and which schema decisions need ratifying. All
numbers below come from `python3 scripts/coverage.py` on the committed build;
regenerate rather than edit them.

## 1. Coverage per neighborhood

| neighborhood | places | rest. | cafes | groc. | walk min | street risk | DPH match | DPH name+addr | menus tried | ok | partial | not_found | skipped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| North Beach | 85 | 58 | 12 | 15 | 1–12 | 85 | 68 | 52 | 27 | 19 | 3 | 2 | 3 |
| Chinatown | 253 | 139 | 42 | 72 | 1–10 | 253 | 205 | 137 | 25 | 12 | 6 | 4 | 3 |
| Fisherman's Wharf | 83 | 57 | 16 | 10 | 10–20 | 83 | 63 | 28 | 51 | 26 | 12 | 9 | 4 |
| Russian Hill | 72 | 48 | 16 | 8 | 7–19 | 72 | 62 | 41 | 60 | 29 | 9 | 7 | 15 |
| Nob Hill | 10 | 5 | 1 | 4 | 8–13 | 10 | 8 | 3 | 0 | 0 | 0 | 0 | 0 |
| Financial District/South Beach | 11 | 7 | 3 | 1 | 6–11 | 11 | 7 | 6 | 2 | 0 | 2 | 0 | 0 |
| TOTAL | 514 | 314 | 90 | 110 | 1–20 | 514 | 413 | 267 | 165 | 86 | 32 | 22 | 25 |

Restaurants + cafes: 404; with a menu (ok or partial): 118; attempted: 165.
Street-risk geocoding gaps (total 0, nearest snap point > 150 m): 19 places (Fisherman's Wharf 19).

How to read it: `places` is every named OSM restaurant / cafe / grocery-type
shop inside the neighborhood polygon (see §4.2). `street risk` and `DPH match`
count places carrying that layer; `DPH name+addr` is the high-confidence
subset. `menus tried` counts places with a file in `data/menus/`; `ok` =
items with prices from the restaurant's own channel, `partial` = prices
missing, aggregator-collapsed, or chain-wide menu, `not_found` = nothing
usable after trying, `skipped` = the place is closed.

Two things the table hides:

- **The North Beach index is mostly "Chinatown" by the official polygons.**
  The original 374-place bbox around 371 Columbus straddles the Analysis
  Neighborhood boundary, which runs along the south-east side of Columbus Ave
  (Caffè Greco, Molinari, China Live are "Chinatown"; Golden Boy, Il Casaro,
  Réveille are "North Beach"). §4.2 asks whether to keep that.
- **Fisherman's Wharf street risk reads 0 at the piers.** SFPD geocodes to
  intersections; Pier 39 / Pier 41 businesses sit > 150 m from any snap point,
  so `total` is 0 with `nearest_incident_m` > 150 (19 places). That
  is a geocoding gap, not a calm block, and the viewer still paints it green.

## 2. North Beach menus: 33 of 41 attempted places

| place | status | items | as_of | source |
|---|---|---|---|---|
| Barbara Pinseria & Cocktail Bar | ok | 34 | 2026-09-09 | restaurant website PDF menu |
| Belle Cora | ok | 30 | 2026-09-09 | restaurant website |
| China Live | ok | 117 | 2026-09-22 | restaurant website menu |
| Compton's Coffe House | ok | 49 | 2026-09-09 | restaurant website |
| Fiddle Fig Cafe | ok | 49 | 2026-09-09 | Yelp menu page |
| Flour + Water Pizzeria | ok | 29 | 2026-09-09 | restaurant website menu image |
| Golden Boy Pizza | ok | 13 | 2026-09-09 | restaurant website |
| Hing Lung Co | ok | 27 | 2026-09-09 | restaurant website PDF menu |
| Hon's Wun-Tun House | ok | 151 | 2026-09-09 | restaurant website |
| Il Casaro Pizzeria | ok | 51 | 2026-09-22 | restaurant website menu images |
| Il Pollaio | ok | 30 | 2026-09-09 | restaurant website |
| Mario's Bohemian Cigar Store Cafe | ok | 50 | 2026-09-09 | restaurant website menu images |
| Maykadeh Persian Restaurant | ok | 52 | 2026-09-09 | restaurant website |
| Mo's Grill | ok | 98 | 2026-09-22 | restaurant website |
| North Beach Gyros | ok | 33 | 2026-09-22 | restaurant website menu page |
| North Beach Pizza | ok | 100 | 2026-09-22 | restaurant website online-ordering menu |
| Original Joe's | ok | 78 | 2026-09-09 | restaurant website PDFs: /s/OJNB_DinnerMenu_6226.pdf |
| Osmanthus Dim Sum Lounge | ok | 95 | 2026-09-22 | restaurant's own online-ordering menu |
| Pizzelle di North Beach | ok | 85 | 2026-09-09 | restaurant website |
| Red Window | ok | 59 | 2026-09-09 | restaurant website |
| Sodini's | ok | 65 | 2026-09-09 | restaurant website |
| Sotto Mare | ok | 45 | 2026-09-09 | restaurant website menu images |
| Tacolicious | ok | 41 | 2026-09-09 | restaurant website |
| Tacorea | ok | 16 | 2026-09-22 | restaurant website menu-board image |
| Taqueria Zorro | ok | 61 | 2026-09-22 | restaurant's own online-ordering menu |
| The Stinking Rose | ok | 61 | 2026-09-09 | restaurant website PDF daily menu |
| Tommaso's Ristorante Italiano | ok | 51 | 2026-09-22 | restaurant website menu |
| Tony's Pizza Napoletana | ok | 130 | 2026-09-22 | restaurant website dinner-menu PDF |
| Dim Sum Bistro | partial | 21 | 2026-09-22 | Yelp menu page |
| El Farolito | partial | 32 | 2026-09-09 | restaurant website |
| Kam Po Kitchen | partial | 19 | 2026-09-09 | Yelp menu page |
| Réveille Coffee Co. | partial | 16 | 2026-09-09 | repo file menus/reveille-north-beach-2026-08.pdf |
| Sam's Panini | partial | 11 | 2026-09-09 | restaurant website |
| Caffe Trieste | not_found | 0 | 2026-09-22 | no reliable menu source |
| Caffè Greco | not_found | 0 | 2026-09-22 | no reliable menu source |
| Canna Bistro | not_found | 0 | 2026-09-22 | no reliable menu source |
| Cavalli Cafe | not_found | 0 | 2026-09-22 | no reliable menu source |
| Gourmet Delight B.B.Q. | not_found | 0 | 2026-09-22 | no reliable menu source |
| Chubby Noodle | skipped | 0 | 2026-09-22 | web search + official site + Yelp |
| Don Pistos | skipped | 0 | 2026-09-22 | official site + Yelp |
| Dupont Thai | skipped | 0 | 2026-09-09 | web search |

Method: every site that blocked `curl`/WebFetch on 2026-09-09 was re-read in
a real Chrome session (page text, rendered menu widgets, PDF links, menu
images read visually). Restaurants' own ordering pages (Toast, Square, Owner,
SpotOn, bestfoodtoday) count as first-party and are labeled in `source`; their
prices are online prices and may differ in-store. Aggregators (Yelp) were used
only when no first-party menu exists and yield `partial` at best.

Still blocked after the browser pass:

- **Caffe Trieste** (North Beach): Official site (caffetrieste.com/nbeach) describes the offering only in prose (pastries, cookies, muffins, bagels, sandwiches, salads, pizza by the slice, desserts, wine and beer) with no items or prices; the rest of the …
- **Caffè Greco** (Chinatown): Official site caffegreco.com (found this pass) is a three-page brochure (Home / About / Contact) with no menu; it names Illy espresso, tiramisu, cannoli and gelato in prose only. Yelp has no menu page for this location (…
- **Cavalli Cafe** (Chinatown): No official website found (cavallicafe.com times out; no other domain resolves). Yelp has no menu page (the /menu URL redirects to the business page, which lists popular dishes by name only: tiramisu, panna cotta, cannol…
- **Gourmet Delight B.B.Q.** (Chinatown): No official website (gourmetdelightsf.com is a registrar parking page). Yelp has no menu page for this business (the /menu URL redirects to the business page, which lists popular dishes by name only: BBQ pork, roast duck…
- **Canna Bistro** (North Beach): The OSM website (cannabistrotogo.com) does not resolve. Yelp still lists the business as open (unclaimed listing, American / pizza, 464 Broadway, hours Mon-Thu 11am-3am, Fri 11am-4am, Sat 3:30pm-4am, Sun 3:30pm-3am) but …

Closed (`skipped`):

- **Chubby Noodle** (North Beach): Appears CLOSED in San Francisco. Yelp lists the San Francisco Chubby Noodle (last at 510 Union St) as closed ("Yelpers report this location has closed"); the official site's navigation (sitemap lastmod 2026-08-13) offers…
- **Don Pistos** (North Beach): Appears CLOSED. donpistos.com is now a registrar parking page (GoDaddy "parked free"); Yelp lists Don Pisto's Burrito Bar (its listing gives 570 Green St; OSM has 510 Union St, the two addresses were swapped between this…
- **Dupont Thai** (North Beach): CLOSED per Yelp (Mar 2026); 1398 Grant is now Tasty Pot (Taiwanese hot pot). Remove from places.json on next OSM refresh.

## 3. Expansion neighborhoods: what was pulled in

`build.py` now reads the citywide OSM base (`data/sf_places.json`, 3,932 rows,
pulled 2026-09-09) and keeps every named row whose polygon label is North
Beach, Chinatown, Fisherman's Wharf or Russian Hill, unless a place with the
same normalized name already sits within 150 m (node + way duplicates, or
already in the bbox set). That added 133 places; the distance-aware dedup
also surfaced 7 same-name places the old name-only dedup had collapsed inside
the bbox (4 Starbucks, Hon's Wun-Tun House at 648 Kearny, a Subway, a Latte
Express). The set is 514: 381 from the North Beach bbox + 133 from the base.
Walk times top out at 20 min (Pier 39 / Aquatic Park), so no walk cap was
needed; the polygons are the selection, the walk radius is why these four.

All three layers ran on the full set with the same scripts and schemas:

- **Street risk**: one DataSF pull for the POI bbox + 200 m (5,714 rows, 365
  days to 2026-09-22), 514/514 scored. See §1 for the pier geocoding gap.
- **DPH inspections**: the three datasets were re-fetched (the 2024+ feed had
  a new monthly load) and matched: 413/514 (267 name+address, 146 name-only,
  101 none). The Wharf's name+address rate (28/83) is the lowest because pier
  businesses register under other legal names and "Pier 39, Space N" addresses
  do not parse as street addresses.
- **Menus**: every new restaurant and cafe (123 + the original Starbucks) got
  an attempt — first with curl/WebFetch/PDF/menu-image reads, then a real
  Chrome session for the sites that only render in a browser. Results are in
  the table in §1 and the lists below. What the pass found about the base
  itself: the OSM rows are stale — 22 of the attempted places
  are closed (Yelp / the restaurant's own site), and a few rows are the same
  restaurant under two OSM names (McCormick & Schmick's and McCormick &
  Kuleto's at 900 North Point; Crepe Cafe and The Crêpe Cafe at the Wharf are
  two businesses) or a stale node (a second "The Stinking Rose" near Pier 39
  with no address). Recommendation: refresh `sf_places.json`, then let the
  `skipped` menu files retire those rows.

Menus still not extracted in the expansion neighborhoods (with the reason
recorded in each file's `notes`):

- **Baccus** (Russian Hill): Likely Bacchus Wine Bar, 1954 Hyde St (small wine bar with cheese and charcuterie per listings). Official site is a placeholder blog with About/Contact pages only; no menu or prices. Match to this POI inferred from name …
- **Cafe Nook** (Russian Hill): cafenook.com resolves but refuses connections (site down). Search shows the cafe operating as NOOK (cafe by day, wine bar evenings; coffee, breakfast sandwiches, bocadillos, Spanish tapas); only aggregator/third-party me…
- **Collina** (Russian Hill): Italian, handmade pasta. Official site collinasf.com embeds its menu from checkle.menu, which returned a Vercel security checkpoint (HTTP 429) to both curl and WebFetch; not bypassed. Hours on site: Sun-Thu 5-9pm, Fri-Sa…
- **Fun Food Factory** (Fisherman's Wharf): Pier 39 dessert/snack stand. Pier 39 and Fisherman's Wharf Association listings describe funnel cake with ice cream and churros but publish no menu or prices; no first-party menu found.
- **Golden Gate** (Fisherman's Wharf): Map POI named only "Golden Gate" with no address, cuisine or website. One search for a restaurant of that name at Fisherman's Wharf found no matching business; identity unverified.
- **Hardware Coffee Co.** (Fisherman's Wharf): Ghirardelli Square kiosk (Suite E204B), open 7 days 8am-6pm. Site describes coffee drinks, cold brew, matcha and pastries from Saltwater Bakeshop but publishes no itemized menu or prices; online store sells retail beans …
- **Latte Express (434 Beach Street)** (Fisherman's Wharf): Independent coffee shop; listings give hours 6am-4pm daily and mention espresso drinks, Vietnamese coffee, banh mi, breakfast sandwiches and donuts, but no first-party menu. DoorDash store page returned 403 (bot-gated).
- **Morning Brew** (Chinatown): No official website. Search surfaces only delivery/review listings for "Morning Brew Coffee & Tea" at 401 Sansome St (coffee, bubble tea, breakfast sandwiches, banh mi; Mon-Fri 7am-3pm), which may or may not be this POI;…
- **Old Tyme Treats** (Fisherman's Wharf): Snack stand/cart near PIER 39 (cotton candy, churros, popcorn, pretzels per search snippets). One web search found no official website or menu with prices; aggregator page not fetched. Address from the Yelp listing.
- **Quickly** (Fisherman's Wharf): Chain bubble-tea shop in the Anchorage Shopping Center. Corporate site lists only product categories (milk tea, slush, snow, smoothie, boba latte, egg puffs, mochi waffle, fried chicken, rice bowls); category menu images…
- **Saint Frank** (Russian Hill): Hours Mon-Sun 7am-6pm per the official locations page. The site sells beans/retail only and publishes no cafe menu. One search found only aggregators; DoorDash returned 403 to automated fetch.
- **Street** (Russian Hill): Search mentions "Street Restaurant and Bar" on Polk St (Russian Hill) but surfaced no official site; its former domain streetsf.com now redirects to a parked "/lander" page, suggesting the restaurant may have closed (not…
- **Sun Kwong Restaurant** (Russian Hill): Chinese-American; open per Yelp (updated September 2026); hours listed 11am-7:45pm. No official website beyond a Facebook page. Its order.online storefront returned 403 to automated fetch; DoorDash/Grubhub listings not a…
- **Taco Rouge** (Russian Hill): Mexican restaurant at 1500 Broadway (Polk Gulch). tacorouge.com no longer belongs to the restaurant. The Toast online-ordering page returned a Cloudflare challenge (bot-gated) to both curl and WebFetch; a real browser ma…
- **The Chowder Hut Grill** (Fisherman's Wharf): Open per Yelp (updated July 2026). No official website found. Aggregators refused automation: Uber Eats 403, Seamless/Grubhub JS shell with no items. Listings describe clam/crab chowder bread bowls, fish and chips, fish …
- **The Hook** (Fisherman's Wharf): Listings describe a Pier 39 seafood counter (fish and chips, chowder, fried shrimp and calamari, grilled sandwiches) rather than Asian food; no first-party menu or prices found.
- **The Stinking Rose (37.80905,-122.41454)** (Fisherman's Wharf): This POI is a Fisherman's Wharf point tagged fast food/seafood. Search found no Stinking Rose outlet at the Wharf; the brand's only confirmed SF restaurant is 430 Columbus Ave (North Beach), which already has its own men…

Places found closed during the pass (`status: skipped`; kept until the next
OSM refresh drops the row):

- **Berber** (Russian Hill): Closed: Yelp lists Berber (1516 Broadway) as CLOSED (updated August 2026); the official site berbersf.com is stale (navigation still promotes "NYE 2023") and shows no current menu text.
- **Cafe Sebastian** (Chinatown): Closed: Yelp lists the cafe at 545 Sansome St as CLOSED (updated July 2026) and the official site cafesebastiansf.com now shows only a "site under maintenance" page. Address found via web search (batch had none).
- **Fisherman's Pizza** (Fisherman's Wharf): Matched to Fisherman's Pizzeria, 2800 Leavenworth St; Yelp marks it CLOSED and a menu-archive site lists it as permanently closed. No official website found.
- **House Rules** (Russian Hill): Closed: Yelp marks House Rules (sports bar, 2227 Polk St) as CLOSED and Foursquare lists it as now closed. The POI's "mexican" cuisine tag may reflect a successor business at the address; not verified.
- **La Folie** (Russian Hill): Closed. News coverage (SF Chronicle, SFGate) reports the restaurant closed in March 2020 after 32 years; Yelp lists it as closed; lafolie.com now serves only a parked-domain redirect. Address from those listings.
- **Little Kitchen** (Russian Hill): Yelp listing (updated May 2026) marks the business CLOSED. No official website found; remaining listings are aggregator/ordering-directory pages.
- **Lord Stanley** (Russian Hill): Closed permanently May 31, 2025 (lease not renewed). The POI's website field (t2joldlittlethai.com) does not resolve; it may point to a successor business in the space, not verified.
- **Lorenzo’s Pizzeria** (Fisherman's Wharf): Closed: Yelp lists Lorenzo's Pizzeria (200 Pier 39) as CLOSED (updated August 2026) and a menu directory marks it permanently closed. Address found via web search (batch had none).
- **Loving Cup** (Russian Hill): The Polk St shop appears closed: the brand's current locations page lists only Divisadero (NOPA) and Greenbrae, Yelp marks 2356 Polk St as closed, and lovingcupsf.com is an old archived placeholder. Address from listings…
- **Lush Gelato** (Russian Hill): Closed: Yelp marks Lush Gelato at 1817 Polk St as CLOSED. The brand site lushgelato.com still exists but was not used since the Polk St shop is closed.
- **Mac'd** (Russian Hill): Closed. Yelp lists the Polk St location as CLOSED (updated July 2026; search summary gives July 31, 2026), the DoorDash store is marked do-not-reactivate, and getmacd.com/sf-russian-hill returns 404 behind a bot wall.
- **Noodle Time** (Chinatown): Yelp listing (updated September 2026) marks the business CLOSED. No official website found in search; only delivery/aggregator listings (Uber Eats, ezCater, allmenus) remain. Vietnamese noodles, banh mi and vermicelli pe…
- **Project Juice** (Russian Hill): Closed: Yelp lists Project Juice at 2259 Polk St as CLOSED (updated December 2025) and HappyCow titles it "CLOSED: Project Juice - Russian Hill".
- **Queen Mediterranean Pizzeria** (Fisherman's Wharf): Appears closed: Yelp marks Queen Mediterranean at 993 North Point St as CLOSED and a menu-guide listing says permanently closed. No official website found. Address from those listings.
- **Ramen Sho Ryu** (Russian Hill): Closed: Yelp lists Ramen Sho Ryu (2123 Polk St) as CLOSED (updated July 2026). An official site (ramenshoryusf.com) still exists but was not used for a closed venue.
- **Restorante Milano** (Russian Hill): Matched to Ristorante Milano, 1448 Pacific Ave (Russian Hill); Yelp listing updated September 2026 marks it CLOSED. Northern Italian, house-made pastas. Menu not extracted because the business is closed.
- **Royal Ground Coffee** (Russian Hill): Likely closed: Yelp lists the 2216 Polk St cafe as CLOSED (updated June 2026) and the official domain now shows a parking page. Not independently confirmed on site.
- **Split** (Russian Hill): Likely closed at this address: spliteats.com lists only its SoMa location (560 Mission St) and the Russian Hill menu pages return 404; listings (Uber Eats, Tripadvisor) show MIXT Russian Hill now operating at 2300 Polk S…
- **Stones Throw** (Russian Hill): Closed: Yelp lists Stones Throw at 1896 Hyde St as CLOSED and Foursquare as "Now Closed"; search sources report it closed in 2018.
- **The Crêpe Cafe** (Fisherman's Wharf): Appears closed: the Yelp listing for The Crepe Cafe at 333 Jefferson St (Ste 5A) is marked CLOSED (July 2026). No official website found; the Fisherman's Wharf Association listing is JS-only and gave no menu. Not to be c…
- **The Soap Box Cafe** (Russian Hill): Closed: Yelp marks The Soapbox Cafe (Vietnamese cafe, 1800 Hyde St) as CLOSED (April 2026). No official website found.
- **Tlaloc** (Chinatown): The restaurant's own site states the 525 Commercial St location is permanently closed; the brand now operates a weekday food truck around the Financial District. No menu recorded for the closed storefront.


## 4. Schema decisions to ratify

Each item is a choice made to ship this pass; the alternative is stated so it
can be reversed by editing one constant or one file.

### 4.1 `key` is the join key for every layer (build.py `key_for`)

`key == name`, except when a second place with the same normalized name lies
more than 150 m (`DUP_M`) from the first; then `key = "Name (address)"` (or
`"Name (lat,lon)"` with no address) and the first keeps the bare name. The
street-risk, DPH and menus layers are keyed by it; a menu file's `name` must
equal it (`menus_index.py` warns on orphans). Side effect: the original bbox
set grew from 374 to 381 because the old name-only dedup had collapsed 4
Starbucks, a second Hon's Wun-Tun House (648 Kearny), a second Subway and a
Latte Express into their namesakes. Alternative: an `id` from `osm_type:osm_id`
(cleaner, but every layer file and the curated overlay would need re-keying).

### 4.2 `neighborhood` comes from the city's Analysis Neighborhood polygons

Source: DataSF dataset j2bu-swwd, the same 41-neighborhood set SFPD and DPH
rows are labeled with. Consequences to accept or reverse:

- The Chinatown polygon includes the south-east side of Columbus Ave up to
  Green St, so Caffè Greco, Molinari, Original Joe's neighbors on that side and
  most of the Broadway corridor read "Chinatown"; the North Beach label covers
  the north-west side of Columbus, Washington Square and Telegraph Hill.
- Fisherman's Wharf is not an analysis neighborhood; the index labels a POI
  in the North Beach or Russian Hill polygon that lies north of the Bay Street
  centerline (OSM) as "Fisherman's Wharf". Bay St itself splits by side: odd
  numbers (327, 401, 499 Bay) are North Beach, 350 Bay is the Wharf.
- Nob Hill (10) and Financial District/South Beach (11) places in the original
  bbox keep their official labels and are not filtered out.

Alternative: the finer SF Find Neighborhoods polygons (117 names, with a
separate Fisherman's Wharf and Telegraph Hill) — that dataset is no longer
on data.sf.gov (id pty2-2jhs returns "dataset missing"), so it would have to
come from an archived copy.

### 4.3 Street-risk percentile is ranked across the whole index

`percentile` is "% of all 514 places with a strictly lower 150 m total". The
North Beach values therefore shifted from the 374-place ranking (Chinatown and
Broadway blocks rank higher, the Wharf and Russian Hill lower), and `as_of`
moved to 2026-09-22 with the trailing-365-day window. Alternative: rank within
neighborhood (add `percentile_neighborhood`); the raw counts are unchanged
either way. The pull bbox is now derived from the POI set (+200 m) and
`--cached` refuses a pull that no longer covers it.

### 4.4 Menus: derived index, mechanical price level, status semantics

- `data/menus/index.json` is generated from the files by `menus_index.py`
  (sorted by slug); the committed index must pass `menus_index.py --check`.
- New files carry a mechanical `price_level_estimate`: median of the prices in
  the file's main sections, L1 < $10, L2 < $18, L3 < $30, L4 ≥ $30, with the
  rule written into `price_level_basis`. The 22 files from 2026-09-09 were
  hand-assigned and three would move under the rule (Barbara Pinseria 2→3,
  Hing Lung 3→2, Maykadeh 3→2). Decide: recompute them, or keep hand levels.
- `status`: `ok` needs prices from the restaurant's own channel (site, PDF,
  menu image, or its own ordering page — Toast, Square, Owner, Otter, SpotOn,
  Popmenu, Best Food Today; the `source` names the platform and online prices
  may differ in-store); `partial` covers missing prices, aggregator sources,
  chain-wide menus; `skipped` means closed (evidence in `notes`), kept as a
  record until the next OSM refresh drops the POI.
- Descriptions are shortened ingredient lists, not verbatim copy; drinks are
  collapsed; catering, condiments and merchandise are omitted.

### 4.5 Publish gate and content scrubbing (`check_public.py`)

The gate scans the layer files and this report for personal-context terms and
fails the commit on a hit (soda product names are exempt). To stay inside it,
the extraction pass dropped per-serving figures, ingredient-attribute notices
and wellness-style wording from item descriptions, relabeled a handful of
restaurant section headings by their contents (e.g. one breakfast section
became "Oats & Yogurt"), and left out a few items whose names were themselves
gate terms; item names were otherwise kept as printed (a "Vegan Pizza" stays a
"Vegan Pizza"), but the workers applied that line unevenly and the files'
`notes` do not record every edit.
Decide the written rule (item names verbatim, descriptions scrubbed, sections
relabeled) so a re-extraction is mechanical.

The second commit of this pass widened the gate to every tracked file and
made the repo itself pass it: the curated rating field was renamed to
`verdict` (`pick` / `ok` / `treat`) with its viewer control and badges, the
curated notes that carried personal framing were reworded to the practical
facts (hours, prices, what to order), the two scripts' User-Agent strings
lost their contact address, the raw citywide OSM dump (which carries
businesses' contact tags) is now gitignored and regenerated by its script,
and the city's own DPH text plus the OSM base are exempt from the topic
patterns but never from the owner patterns. `scripts/check_data.py` adds an
integrity gate (unique keys, layer entries that match a place, a current
menus index), and `.githooks/pre-commit` runs both; enable it once per clone
with `git config core.hooksPath .githooks`. What the gate cannot reach: the
repository's earlier history still contains the pre-scrub content; only a
history rewrite (force push) removes it, and that is a separate decision.

### 4.6 DPH matching thresholds were not retuned for the Wharf

`inspections.py` matched 80% of the 514 places (52% name+address). Pier
businesses often register under a different legal name (e.g. "Boudin at the
Wharf"), so the Wharf's name+address rate is the lowest; the `NB_ZIPS` list
already includes 94133/94109. Decide whether to add a pier-aware address
parser ("Pier 39, Space 201") or accept name-only matches there.


## 5. Reproduce

```sh
python3 scripts/fetch_neighborhoods.py   # polygons + Bay St line (network)
python3 scripts/build.py                 # POIs + keys + neighborhoods
python3 scripts/street_risk.py           # SFPD pull for the POI bbox (network)
python3 scripts/fetch_inspections.py     # DPH datasets (network, ~2 min)
python3 scripts/inspections.py           # match DPH to POIs
python3 scripts/menus_index.py           # derive the menus index
python3 scripts/build.py                 # merge layers, emit viewer
python3 scripts/coverage.py              # this report's table
python3 scripts/check_public.py          # publish gate
```

CI/CD: this repository has no pipeline and no GitHub Pages site; the viewer
is the committed `docs/index.html`, opened locally.
