# Menu extraction

Read one place's menu from the source named in the task (the place's own site,
menu PDF or photo, or its own ordering page; a third-party copy only when the
place publishes none, and then the file's status is "partial").

Write data/menus/<slug>.json with:

- name: the place's key in data/places.json, exactly
- addr, menu_url, source (what was read, in words), as_of (the day it was read)
- status: ok (the full menu with prices), partial (some sections or no
  prices), not_found or skipped (with the reason in source)
- items: one object per item, keys exactly section, item, price, description:
  - section and item as the menu prints them
  - price: the listed number, or null when none is listed; never a guess
  - description: the menu's own words for the item, or ""; never completed or
    paraphrased
- extraction: {"method": "model", "model": <model id from the API response or
  the harness>, "prompt_hash": <this file's content hash as pinned in
  spine/stages/menus.json>, "read_on": <date>}

Nothing is inferred: an item the menu does not list is not added, and words
the menu does not print are not added to a description.
