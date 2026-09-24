# Food mapping battery

You match one restaurant menu item or packaged store product to the entry in
the USDA FoodData Central list below that is the same food. Each candidate is
marked FOOD (a single food: a fruit, a vegetable, a cut of meat, a cheese, a
bread, a plain drink) or DISH (a mixed dish as eaten, from the USDA survey
database). Answer two closed questions.

choice: the id of the candidate that is the item itself, or "none".
- The item itself means the whole item, prepared the way its words say: not an
  ingredient of it, a side served with it, or its sauce. Fennel is not a
  branzino dish; a relish is not the fish it comes with.
- A restaurant dish maps to a DISH entry that is the same dish. A single food,
  on a menu or in a package, maps to a FOOD entry that is the same food in the
  same state (raw or cooked, fresh or dried, plain or sweetened).
- A close cousin with a different main ingredient, preparation or kind of food
  is "none". A name you cannot place, or a candidate list without the item,
  is "none". A wrong match is worse than "none".

portion: for a restaurant or cafe menu item, the id of the chosen candidate's
listed portion that is closest to one serving of the item as a restaurant
serves it (for example "1 sandwich", "1 bowl", "1 slice"), or "none" if no
listed portion fits or no candidate was chosen. For a packaged store product,
always "none".

Answer with the JSON object {"choice": ..., "portion": ...} only, using the
ids exactly as listed ("c3", "p2") or "none".
