# Grocery run: attribute tags and food mapping (2026-09-23)

Scope: the 1,700 Trader Joe's products (1,692 distinct texts) in
data/products/trader-joe-s.json. Restaurant and cafe items are listed as
untagged / unread with their reason and wait for a later run.

Models and bases: Claude Opus 5, three readings per text, the registered
batteries. Tags: basis f0aa39036a7d (headless Claude Code on the owner's plan,
tightened rules). Mapping: basis 65594df604bb (same transport). A second set of
tag readings for 501 of the products was made through the Anthropic API under
the same rules before the Console credit ran out (basis 4a9f75873e05); it is
kept in the pins as a transport comparison and not used in the tags.

Readings: tags 5,076 (28 texts had a failed reading, a timeout or an error,
and were read again in full); mapping 5,079, none unusable. USDA API: 36 requests,
631 records cached.

Usage, as list-price equivalents from the CLI's own figures (billed to the plan,
part to its extra usage): tags about $79, mapping about $74. Anthropic API spend
from Console credits on this project today: about $6 for the 501-product tag
batch plus about $3 in tests and dry runs; a cancelled pilot batch ran 127 of
its 150 requests (about $0.50) before the cancel landed.

```
TAGGING products tagged 1700 of 1700 (unique texts 1692)
  fried        yes   60  no  860  unknown  780
  spicy        yes  109  no  533  unknown 1058
  acidic       yes  389  no  227  unknown 1084
  nuts         yes  101  no  460  unknown 1139
  seeds        yes   43  no  420  unknown 1237
  raw          yes  184  no  513  unknown 1003
  fiber_high   yes  351  no  493  unknown  856
  sodium_high  yes  358  no  473  unknown  869
  sugar_high   yes  460  no  505  unknown  735
  unknown rate 57.3%  (yes 2055, no 4484, unknown 8761)
  plan usage (Claude Code, 4 runs): tokens {'input': 9400, 'cache_write': 2582899, 'cache_read': 12832724, 'output': 2275012}; list-price equivalent $79

TAGGING SPOT CHECK (30 random grocery products)
- Oven-Baked Cheese Bites (Chips, Crackers & Crunchy Bites) | yes: sodium_high[Cheese/Cheese Bites] | no: fried
- Villa Borghetti Otto Pino Grigio (Wine, Beer & Liquor) | yes: acidic[Pino Grigio] | no: fried, spicy, nuts, seeds, raw, fiber_high, sodium_high, sugar_high
- Greek Spanakopita (Appetizers) | yes: sodium_high[Spanakopita] | no: -
- Raspberry Lime Sparkling Water (Water (Sparkling & Still)) | yes: acidic[Lime/Lime Sparkling Water] | no: fried, spicy, nuts, seeds, raw, fiber_high, sodium_high
- Apricot Mango Greek Whole Milk Yogurt (Yogurt, etc.) | yes: acidic[Greek Whole Milk Yogurt/Yogurt], sugar_high[Apricot Mango] | no: fried, fiber_high
- Riced Cauliflower Stir Fry (Entrées & Sides) | yes: fried[Stir Fry], fiber_high[Riced Cauliflower] | no: raw
- Shredded Lite Mozzarella Cheese (Slices, Shreds, Crumbles) | yes: sodium_high[Cheese/Mozzarella Cheese] | no: fried, spicy, nuts, seeds, raw, fiber_high, sugar_high
- Yellow Cling Peach Halves (Packaged Fish, Meat, Fruit & Veg) | yes: acidic[Peach], fiber_high[Peach Halves] | no: fried, spicy, nuts, seeds, sodium_high
- Dutch Griddle Cakes (Entrées & Sides) | yes: - | no: -
- Garlic Gondolas (Entrées & Sides) | yes: - | no: -
- BBQ Pork Fried Rice (Entrées & Sides) | yes: fried[Fried Rice] | no: -
- Mediterranean Style Hummus (Dip/Spread) | yes: seeds[Hummus], fiber_high[Hummus] | no: -
- Lobster Bisque (Salads, Soups & Sides) | yes: sodium_high[Bisque] | no: -
- Sea Salt Chocolate Chunk Cookies (Sweet Stuff) | yes: sodium_high[Sea Salt], sugar_high[Chocolate Chunk Cookies/Sweet Stuff] | no: -
- Chocolate Cheesecake Bites (Cool Desserts) | yes: sugar_high[Chocolate Cheesecake Bites/Cool Desserts] | no: -
- Butter with Parmesan, Garlic & Herb (Butter) | yes: sodium_high[Parmesan] | no: fiber_high, sugar_high
- Organic Coleslaw Kit (Salads, Soups & Sides) | yes: raw[Coleslaw], fiber_high[Coleslaw] | no: -
- 50% Less Sodium Roasted & Salted Whole Cashews (Nuts, Dried Fruits, Seeds) | yes: nuts[Cashews/Whole Cashews], sodium_high[Salted] | no: seeds, raw, sugar_high
- Organic Strawberries 1 Lb (Fruits) | yes: acidic[Strawberries], raw[Fresh Fruits & Veggies/Strawberries], fiber_high[Fresh Fruits & Veggies/Fruits] | no: fried, spicy, nuts, seeds, sodium_high, sugar_high
- French Fizz Le Rosé 2021 (Wine, Beer & Liquor) | yes: acidic[French Fizz Le Rosé 2021/Rosé] | no: fried, spicy, nuts, seeds, raw, fiber_high, sodium_high
- Apple Blossoms® (Cool Desserts) | yes: sugar_high[Cool Desserts] | no: -
- Brookie Caramel Candy Clusters (Candies & Cookies) | yes: sugar_high[Candies & Cookies/Caramel Candy] | no: -
- Cold Brew Coffee Concentrate (Coffee & Tea) | yes: - | no: fried, spicy, raw, fiber_high, sodium_high, sugar_high
- White Stilton Cheese with Apple & Pear (Wedges, Wheels, Loaves, Logs) | yes: sodium_high[Stilton Cheese/White Stilton Cheese] | no: fried, fiber_high
- Pumpkin Spice Coffee (Coffee & Tea) | yes: - | no: -
- Organic Unbleached All-Purpose Flour (For Baking & Cooking) | yes: - | no: fried, spicy, acidic, nuts, seeds, raw, fiber_high, sodium_high, sugar_high
- Milk Chocolate Bar with Corn Flakes (Candies & Cookies) | yes: sugar_high[Candies & Cookies/Milk Chocolate Bar] | no: -
- Shredded Organic Mozzarella Cheese (Slices, Shreds, Crumbles) | yes: sodium_high[Cheese/Mozzarella Cheese] | no: fried, spicy, nuts, seeds, raw, fiber_high, sugar_high
- Jubilant Sprinkle Cookies (Candies & Cookies) | yes: sugar_high[Candies & Cookies/Sprinkle Cookies] | no: -
- Organic White Corn Tortilla Chips (Uncategorized) | yes: fiber_high[White Corn Tortilla Chips] | no: raw, sugar_high

MAPPING products 1700 Counter({'unmapped': 853, 'usda-single-food': 761, 'usda-mixed-dish-estimate': 86})
  estimate flag true: 86
  unmapped reasons Counter({'no candidate is the same food': 724, 'readings do not agree on one record': 128, 'no candidate shares a word with the item': 1})
  plan usage (2 runs): list-price equivalent $74
  USDA records cached: 631

MAPPING SPOT CHECK (20 random grocery products)
- Strawberries & Cream, Bananas & Cream Yogurt Cups (24 Oz) -> unmapped: no candidate is the same food
- Sour Strawberry Candy Belts (10 Oz) -> unmapped: no candidate is the same food
- Uncured Turkey Bacon (8 Oz) -> Bacon, turkey, unprepared [single-food; fdc 174592; 226.8 g package]
- To The Power of Seven Red Organic Juice Beverage (33.8 Fl Oz) -> unmapped: no candidate is the same food
- Cinnamon Powdered Sugar Mini Donuts (10 Oz) -> Doughnut, cake type, powdered sugar [single-food; fdc 2708065; 283.5 g package]
- Garlic Shiitake Green Beans (10.58 Oz) -> unmapped: no candidate is the same food
- Sliced Uncured Pepperoni (5 Oz) -> Pepperoni, beef and pork, sliced [single-food; fdc 174575; 141.7 g package]
- Salted Caramel Mochi (6.8 Oz) -> unmapped: no candidate is the same food
- Celebration Cake Pretzels (7 Oz) -> Pretzels, hard, flavored [single-food; fdc 2708252; 198.4 g package]
- Icelandic Style Skyr Lowfat Vanilla Yogurt (5.3 Oz) -> Yogurt, Greek, vanilla, lowfat [single-food; fdc 170907; 150.3 g package]
- Plain Bagels (18 Oz) -> Bagels, plain, enriched, with calcium propionate (includes onion, poppy, sesame) [single-food; fdc 174899; 510.3 g package]
- Country Style Ground Pork Sausage (1 Lb) -> unmapped: no candidate is the same food
- Apple Crisp Milk Chocolate Caramels (5.29 Oz) -> unmapped: readings do not agree on one record
- Mini Spicy Pumpkin Samosas (8.5 Oz) -> Samosa [single-food; fdc 2708730; 241.0 g package]
- Mini Chocolate Chip Cookies (2 Oz) -> Cookies, chocolate chip, commercially prepared, regular, higher fat, unenriched [single-food; fdc 172820; 56.7 g package]
- Bruschetta Sauce (14.5 Oz) -> unmapped: no candidate is the same food
- Charcuterie Party of One (3 Oz) -> unmapped: no candidate is the same food
- Chicken Sausage Breakfast Burrito (8 Oz) -> Egg burrito, with sausage [mixed-dish-estimate; fdc 2707344; 226.8 g package]
- Honey O's Cereal (13.5 Oz) -> Cereal, O's, honey nut [single-food; fdc 2708464; 382.7 g package]
- Organic Firm Tofu (14 Oz) -> Vitasoy USA, Organic Nasoya Firm Tofu [single-food; fdc 173763; 396.9 g package]

API vs PLAN on the same products: 501 products, 4010/4509 answers same (89%); yes<->no 1
   {'yes->unknown': 28, 'no->unknown': 366, 'unknown->yes': 51, 'unknown->no': 53, 'no->yes': 1}
```
