# Jev vs Opus on the attribute battery (2026-09-23)

Question: can Jev (TypeSafe jev-1.13.0) answer the nine-attribute battery in
place of Claude Opus 5 (three readings, the registered T2 path)?

Sample: 20 items drawn at random (seed 20260923) from data/menu_items.json;
both models saw the same section, name and description. Opus: the registered
battery, three readings, routed by `route_attribute` (yes needs two readings
quoting the item, no needs all three). Jev: one call per item, one Choice
question per attribute (yes / no / unknown) with the vocabulary's definitions
as criteria (`scripts/jev_tags.py`). Raw answers: the .json beside this file.

## Findings

- Agreement 111 / 180 answers (62%); 129 / 180 (72%) when a Jev answer under
  0.7 confidence is read as unknown.
- 59 of the 69 disagreements are Opus unknown / Jev no, 29 of them at Jev
  confidence 0.7 or higher. Most read absence as evidence: a sandwich with no
  description is "no nuts" at 0.89, "not raw" at 0.95, "not high in fiber" at
  0.93. That is the error the principle forbids, and the costlier one for a
  reader who acts on "no". It matches the vendor's own warning that Jev reads
  literally, and our criteria saying so did not stop it.
- On yes the two mostly agree: of Opus's 26 yes answers Jev said yes to 21;
  of Jev's 25 yes answers Opus said yes to 21.
- Yes against no, the sharpest conflict, happened 4 times (2%).
- Cost: Jev $0.0019 for the 20 items (44k input tokens, ~0.3 s a call); Opus
  about $0.55 at full price for the same 20 (about half that through Batches).
- Jev returns no words, so it cannot meet the rule that a yes quotes the item.

A sample of 20 items (180 answers) bounds nothing tightly: it shows a pattern,
not a rate.

## Decision

Deterministic vs judgment: the attribute answer stays a judgment (T2), and
Jev does not replace the Opus path. Its "no" breaks the principle; its "yes"
cannot carry the item's words. Jev may serve later as a cheap second reader
that flags items where it and the pinned tags disagree on a yes, but only
after a measurement on a labelled sample, registered as its own path.
