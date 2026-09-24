# Package labels

One file per item whose package label is on file: `data/labels/<item id>.json`,
where the item id is the row id in `data/menu_items.json`.

```json
{"id": "<item id>", "source": "where the label was read", "as_of": "YYYY-MM-DD",
 "serving": "the label's serving size as printed", "serving_g": 28,
 "nutrients": [{"name": "Sodium", "unit": "mg", "amount": 140}]}
```

Amounts are per serving as the label prints them. A label is exact for the
nutrients it lists; every other nutrient of that item is unknown. An item with
a label is mapped to its label before any USDA entry (scripts/map_foods.py).
