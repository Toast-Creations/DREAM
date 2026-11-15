"""V1.5.5 Stage A v2 items (criteria: Runs/idea-survival-20261031/output/continuity/CATEGORIZATION-CHECK-CRITERIA-v2.md).
Same fresh object sets C (screen) and D (replication) as V1.5.4; no C/D outcome was inspected before this revision.

Interpretation (stated before data): membership is judged as asked ("member of / belongs to / classified as"). A
remote category is one the object can be counted under only through a stated basis: its FORM, its FUNCTION, or a
common USE. Foils are clearly inapplicable under any basis. Eight categories per object:
typical (2), peripheral (2), remote (2, each with its basis), foil (2).
"""

LEVELS = ("typical", "peripheral", "remote", "foil")
BASES = ("form", "function", "use")

# (name, description, typical, peripheral, ((remote, basis), (remote, basis)), (foil, foil))
SET_C = (
    ('vase', 'a glass or ceramic vessel that holds cut flowers', ('containers', 'home decor'), ('artworks', 'gifts'), (('sculptures', 'form'), ('memorials', 'use')), ('footwear', 'insects')),
    ('stapler', 'a hand device that drives wire staples through paper', ('office supplies', 'fastening tools'), ('hand tools', 'machines'), (('presses', 'function'), ('sewing tools', 'function')), ('fruit', 'weather')),
    ('raincoat', 'a waterproof coat worn in wet weather', ('clothing', 'rain gear'), ('outerwear', 'protective equipment'), (('shelters', 'function'), ('shields', 'function')), ('kitchen appliances', 'minerals')),
    ('matchbox', 'a small cardboard box of matches with a striking strip', ('fire starters', 'household items'), ('containers', 'collectibles'), (('toys', 'use'), ('drawers', 'form')), ('beverages', 'reptiles')),
    ('fridge magnet', 'a small decorative magnet that sticks to a refrigerator door', ('souvenirs', 'kitchen decor'), ('magnets', 'fasteners'), (('notice boards', 'function'), ('artworks', 'form')), ('footwear', 'planets')),
    ('yo-yo', 'a spool on a string that spins down and climbs back up', ('toys', 'games'), ('sports equipment', 'collectibles'), (('pendulums', 'form'), ('gyroscopes', 'function')), ('soups', 'birds')),
    ('horseshoe', "a U-shaped iron plate nailed to a horse's hoof", ('farrier supplies', 'equestrian equipment'), ('hardware', 'good-luck charms'), (('game pieces', 'use'), ('magnets', 'form')), ('dairy products', 'fabrics')),
    ('egg timer', 'a small device that counts down a few minutes for cooking', ('timers', 'kitchen tools'), ('timekeeping devices', 'gadgets'), (('alarms', 'function'), ('hourglasses', 'form')), ('footwear', 'trees')),
    ('harmonica', 'a small wind instrument played by breathing through reed holes', ('musical instruments', 'wind instruments'), ('collectibles', 'toys'), (('breathing exercisers', 'function'), ('signaling devices', 'use')), ('furniture', 'grains')),
    ('pillow', 'a cloth bag stuffed with soft filling to rest the head on', ('bedding', 'household textiles'), ('furniture', 'comfort items'), (('toys', 'use'), ('sound insulation', 'function')), ('power tools', 'fish')),
    ('bookmark', 'a thin strip placed between pages to mark a place', ('stationery', 'reading accessories'), ('souvenirs', 'gifts'), (('memory aids', 'function'), ('labels', 'function')), ('power tools', 'cheeses')),
    ('mirror', 'a sheet of glass backed with a reflective coating', ('household furnishings', 'glassware'), ('optical instruments', 'decorations'), (('signaling devices', 'use'), ('windows', 'form')), ('fruit', 'mammals')),
    ('tambourine', 'a small hand drum with jingling metal discs in its frame', ('musical instruments', 'percussion instruments'), ('toys', 'dance props'), (('bells', 'function'), ('trays', 'form')), ('vegetables', 'liquids')),
    ('flowerpot', 'a clay or plastic pot for growing plants', ('garden supplies', 'containers'), ('home decor', 'ceramics'), (('drums', 'use'), ('molds', 'form')), ('birds', 'garments')),
    ('bottle cap', 'a small metal or plastic lid that seals a bottle', ('closures', 'packaging'), ('collectibles', 'recyclables'), (('coins', 'form'), ('game pieces', 'use')), ('mammals', 'weather events')),
    ('scissors', 'two crossed blades joined at a pivot, used for cutting', ('cutting tools', 'office supplies'), ('craft tools', 'hardware'), (('weapons', 'function'), ('levers', 'form')), ('beverages', 'clouds')),
    ('bench', 'a long seat for several people', ('furniture', 'seating'), ('outdoor fixtures', 'workstations'), (('stages', 'use'), ('memorials', 'use')), ('fish', 'spices')),
    ('windsock', 'a cloth tube on a pole that shows wind direction', ('weather instruments', 'aviation equipment'), ('signaling devices', 'flags'), (('decorations', 'use'), ('sails', 'form')), ('dairy products', 'insects')),
    ('doormat', 'a mat at a doorway for wiping shoes', ('floor coverings', 'household items'), ('cleaning tools', 'entryway decor'), (('signs', 'use'), ('filters', 'function')), ('beverages', 'birds')),
    ('postcard', 'a card with a picture on one side, mailed without an envelope', ('mail', 'stationery'), ('souvenirs', 'photographs'), (('artworks', 'form'), ('diaries', 'use')), ('power tools', 'fruit')),
    ('whistle', 'a small device that makes a shrill sound when blown', ('signaling devices', 'sound makers'), ('musical instruments', 'safety equipment'), (('toys', 'use'), ('jewelry', 'use')), ('vegetables', 'rocks')),
    ('basket', 'a container woven from strips of cane or reed', ('containers', 'household items'), ('crafts', 'luggage'), (('traps', 'function'), ('artworks', 'form')), ('metals', 'beverages')),
    ('lunchbox', 'a lidded box for carrying a packed meal', ('containers', 'food storage'), ('school supplies', 'luggage'), (('time capsules', 'function'), ('toolboxes', 'form')), ('fruit', 'clouds')),
    ('grater', 'a metal sheet with sharp-edged holes for shredding food', ('kitchen utensils', 'cutting tools'), ('cookware', 'hand tools'), (('musical instruments', 'use'), ('sieves', 'form')), ('mammals', 'fabrics')),
)

SET_D = (
    ('hairbrush', 'a brush with bristles for grooming hair', ('grooming tools', 'personal care items'), ('brushes', 'accessories'), (('cleaning tools', 'function'), ('massage tools', 'function')), ('beverages', 'minerals')),
    ('thumbtack', 'a short pin with a flat head for fixing paper to a board', ('office supplies', 'fasteners'), ('hardware', 'stationery'), (('nails', 'form'), ('markers', 'use')), ('fruit', 'birds')),
    ('hat', 'a shaped covering worn on the head', ('clothing', 'headwear'), ('fashion accessories', 'protective gear'), (('containers', 'form'), ('badges', 'function')), ('power tools', 'fish')),
    ('flashlight', 'a handheld battery lamp that throws a beam', ('light sources', 'tools'), ('emergency supplies', 'electronics'), (('signaling devices', 'use'), ('weapons', 'use')), ('dairy products', 'plants')),
    ('spoon', 'a small bowl on a handle for eating or stirring', ('cutlery', 'kitchen utensils'), ('measuring tools', 'serving ware'), (('musical instruments', 'use'), ('levers', 'function')), ('footwear', 'weather')),
    ('marble', "a small glass ball used in children's games", ('toys', 'game pieces'), ('collectibles', 'glass objects'), (('ball bearings', 'form'), ('jewels', 'form')), ('beverages', 'insects')),
    ('stool', 'a seat without a back or arms', ('furniture', 'seating'), ('household items', 'workshop equipment'), (('tables', 'use'), ('ladders', 'use')), ('fish', 'spices')),
    ('envelope', 'a folded paper sleeve for posting a letter', ('stationery', 'mail supplies'), ('packaging', 'documents'), (('wrappers', 'function'), ('folders', 'function')), ('kitchen appliances', 'reptiles')),
    ('piggy bank', 'a hollow pig-shaped container with a coin slot', ('money boxes', 'containers'), ('toys', 'ceramics'), (('savings plans', 'function'), ('ornaments', 'use')), ('beverages', 'weather')),
    ('kettle', 'a metal pot with a spout and handle for boiling water', ('kitchen appliances', 'cookware'), ('containers', 'electrical devices'), (('alarms', 'function'), ('heaters', 'function')), ('clothing', 'birds')),
    ('bucket', 'an open round container with a handle for carrying liquids', ('containers', 'household tools'), ('cleaning supplies', 'garden tools'), (('drums', 'use'), ('seats', 'use')), ('birds', 'spices')),
    ('pencil', 'a wooden stick with a graphite core for writing', ('writing instruments', 'stationery'), ('art supplies', 'office supplies'), (('pointers', 'use'), ('kindling', 'function')), ('fruit', 'mammals')),
    ('mask', 'a covering worn over the face', ('costumes', 'face coverings'), ('protective equipment', 'artworks'), (('identities', 'function'), ('ritual objects', 'use')), ('kitchen utensils', 'minerals')),
    ('shovel', 'a broad blade on a long handle for digging', ('garden tools', 'digging tools'), ('construction equipment', 'hand tools'), (('levers', 'function'), ('oars', 'form')), ('beverages', 'insects')),
    ('clock', 'a device with hands or digits that shows the time', ('timekeeping devices', 'household items'), ('decorations', 'machines'), (('calendars', 'function'), ('schedules', 'function')), ('vegetables', 'fabrics')),
    ('sieve', 'a mesh bowl that strains liquids or sifts powders', ('kitchen utensils', 'strainers'), ('cookware', 'laboratory tools'), (('hats', 'form'), ('lampshades', 'form')), ('birds', 'liquids')),
    ('crown', "a jewelled ring worn on a ruler's head", ('regalia', 'headwear'), ('jewelry', 'symbols'), (('trophies', 'function'), ('hats', 'form')), ('kitchen appliances', 'grains')),
    ('dice', 'small cubes marked with dots, rolled in games', ('game pieces', 'gaming equipment'), ('toys', 'random number generators'), (('decision tools', 'use'), ('sculptures', 'form')), ('vegetables', 'weather')),
    ('ruler', 'a straight strip marked in units for measuring length', ('measuring tools', 'stationery'), ('drawing tools', 'office supplies'), (('levers', 'use'), ('pointers', 'use')), ('beverages', 'birds')),
    ('balloon', 'a thin rubber bag filled with air or gas', ('party decorations', 'toys'), ('inflatables', 'novelties'), (('weather instruments', 'use'), ('vehicles', 'use')), ('furniture', 'cheeses')),
    ('calendar', 'a chart of the days, weeks and months of a year', ('documents', 'planning tools'), ('decorations', 'reference materials'), (('clocks', 'function'), ('histories', 'use')), ('cutting tools', 'fish')),
    ('faucet', 'a valve with a spout that controls water from a pipe', ('plumbing fixtures', 'valves'), ('kitchen fixtures', 'hardware'), (('switches', 'function'), ('fountains', 'form')), ('birds', 'fabrics')),
    ('safety pin', 'a bent pin with a clasp that covers its point', ('fasteners', 'sewing supplies'), ('first-aid supplies', 'jewelry'), (('hooks', 'form'), ('emblems', 'use')), ('vegetables', 'planets')),
    ('sleeping bag', 'a padded, zip-up bag for sleeping outdoors', ('camping gear', 'bedding'), ('outdoor equipment', 'travel items'), (('clothing', 'use'), ('shelters', 'function')), ('kitchen appliances', 'minerals')),
)
SETS = {"C": SET_C, "D": SET_D}

# Calibration (temperature choice, dispersion/relevance qualification) uses already-seen set A objects only.
TEMPERATURE_GRID = (0.6, 0.9, 1.2, 1.5)
TEMPERATURE_SEEDS = (0, 1, 2, 3, 4)

# Three frozen question formulations; F2 reverses the answer-label order.
FORMULATIONS = {
    "F1": 'Is this object a member of the category "{c}"? Answer Yes or No.',
    "F2": 'Would it be correct to classify this object under "{c}"? Answer No or Yes.',
    "F3": 'Does this object belong to the category "{c}"? Reply with Yes or No only.',
}


def categories(entry):
    """Yield (level, category) for one object entry, in fixed order."""
    _, _, typical, peripheral, remote, foils = entry
    for level, cats in (("typical", typical), ("peripheral", peripheral), ("remote", tuple(c for c, _ in remote)),
                        ("foil", foils)):
        for cat in cats:
            yield level, cat
