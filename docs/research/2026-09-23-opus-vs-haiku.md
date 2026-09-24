# Opus 5 vs Haiku 4.5 on both batteries (2026-09-23)

Question: can Claude Haiku 4.5 carry the attribute battery or the food-mapping
battery in place of Claude Opus 5 at a lower cost?

Sample: the same 20 random items as the Jev comparison (seed 20260923). Both
models ran the registered request builder, parser and route with three
readings; only the model id changed (Haiku rejects `effort`, so it is omitted).
Opus answers are the pinned ones; Haiku answers are in the .json beside this
file (`scripts/compare_models.py`, nothing pinned).

## Findings

Attribute tags: 119 / 180 answers agree (66%).
- No answer is yes in one model and no in the other.
- 33 answers are Opus unknown / Haiku no. Most are absence read as evidence
  (a noodle soup with no listed parts is "no nuts", "no seeds", "not raw").
  The principle calls those unknown, so this is Haiku's error, less often
  than Jev's (59) but the same kind.
- 12 answers are Opus yes / Haiku unknown: Haiku's present answers more often
  failed the rule that two readings quote the item's own words.
- 11 answers are Opus no / Haiku unknown (Haiku the more careful).

Food mapping: 16 / 20 items map the same way. Haiku left three unmapped that
Opus mapped (Korean galbi, falafel burger, dried mango) and picked the meatless
egg roll where Opus picked beef or pork, for an item whose words say
"veggie or meat". Neither model mapped an item to a wrong food.

Cost for the 20 items at full price: tags Opus about $0.55, Haiku $0.17
(Haiku's prompt is below its caching minimum, so it pays full input); mapping
Opus about $0.44, Haiku $0.10.

Side finding: an FNDDS entry that is a single food (Mango, dried) gets the kind
"usda-mixed-dish-estimate" because the kind follows the data type. Open
question for the owner.

A 20-item sample shows a pattern, not a rate.

## Decision

Tags: Opus stays. Haiku's extra "no" answers break the principle, and a wrong
no is the costly error. Mapping: Haiku's errors here lean toward unmapped,
which the principle allows (unknown, never zero), so Haiku is a candidate for
the mapping path if the owner accepts fewer items mapped (3 of these 20);
this needs the owner's ruling before the model binding changes.

## Re-run under the tightened rules (same day)

After the battery was tightened (absent only when certain; pine nuts count as
nuts; the high attributes from a food's nature), Haiku 4.5 was re-run on the
same 20 items, this time through the same headless Claude Code transport as the
pinned Opus answers, so only the model differs
(`2026-09-23-opus-vs-haiku-tightened-rules.json`).

- Haiku gave no usable answer set for 2 of the 20 items. On the other 18:
  111 / 162 answers agree (69%), against 66% under the old rules.
- Opus now follows the tightened rule: its "no" answers dropped to plain foods.
  Haiku still answers "no" for dishes whose words do not settle it (38
  answers: a noodle soup "no nuts", tacos "no seeds"), which the rule forbids.
- One answer is no in Opus and yes in Haiku.

Decision unchanged: Opus carries the attribute path. Tighter rules helped the
model that reads them; they did not make Haiku follow them.
