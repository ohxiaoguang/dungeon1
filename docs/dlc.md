# Nintendo Switch DLC: mapping and validation

Baseline: Nintendo Switch Darkest Dungeon **1.3.0 / v393216**, title
`01008F1008DA6000`. Users supply their own matching game, update, DLC and private
keys. This source repository contains none of those files.

## Verified mapping

The private AOC manifest identifies application, title, index, version and minimum
application version. Each extracted root's `dlc_info.csv` identifies its content.
Actual Host logs confirm the mount names below. The game's `dlc0:` means AOC
**index 1**, not directory 0. Save-list entry numbers are a separate enumeration.

| DLC name | Internal identifier | Resource / game mount | AOC Title ID | Recognized / mounted | Activation and actual evidence | Limits |
| --- | --- | --- | --- | --- | --- | --- |
| The Crimson Court | `crimson_court` | `aoc/1` / `dlc0:` | `01008F1008DA7001` | Yes / yes, read-only | Listed in test save `presented_dlc`; matching feature/audio/localization tree | Full campaign/bosses not tested |
| The Shieldbreaker | `shieldbreaker` | `aoc/2` / `dlc1:` | `01008F1008DA7002` | Yes / yes, read-only | `presented_dlc` and `dlc_init`; matching hero resources | Every skill/nightmare not tested |
| The Musketeer | `musketeer` | `aoc/3` / `dlc2:` | `01008F1008DA7003` | Yes / yes, read-only | `presented_dlc`; matching hero resources | Recruitment/all skills not separately accepted |
| The Color of Madness | `color_of_madness` | `aoc/4` / `dlc3:` | `01008F1008DA7004` | Yes / yes, read-only | `presented_dlc` + `dlc_init`; reachable Comet UI, native Shards debit/inventory/refusal tests on Mac | Farmstead/story/endless combat and physical iPhone DLC-shop acceptance not complete |
| The Fire's Edge | `fires_edge` | `aoc/5` / `dlc4:` | `01008F1008DA7005` | Yes / yes, read-only | `presented_dlc`; Duelist/Runaway feature trees and localization confirmed | Dedicated mechanics/story/long runs not fully tested |

The test save lists all five in `presented_dlc`. Its `dlc_init` lists
`color_of_madness`, `districts`, `shieldbreaker`; `districts` is an in-game feature,
not a sixth AOC. These fields do not prove every feature was played. No activation
field was modified in this review; the private save is not published.

Tested manifest CNMT versions: indices 1–3 = 131072, 4 = 65536, 5 = 0. The first
four require application v327680; the fifth requires v393216. Lower CNMT minimums
are not additional supported/accepted Dungeon1 runtime versions.

Names were cross-checked against [Red Hook's DLC page](https://www.darkestdungeon.com/darkest-dungeon/dlc/)
and [Nintendo's Switch DLC list](https://www.nintendo.com/en-ca/store/products/darkest-dungeon-switch/dlc/).
The Fire's Edge also has an [official Switch page](https://www.nintendo.com/us/store/products/darkest-dungeon-the-fires-edge-70050000078915-switch/).
Local `aoc/5/localization/rd.string_table.xml` names its event The Fire's Edge / 浴火之锋;
its features include `duelist` and `runaway`. Mapping uses local metadata, not a
storefront order. The Butcher's Circus is not one of the five tested inputs;
a cross-platform publisher listing is not a Dungeon1 support claim.

## Comet shop transactions

The Color of Madness shop uses **Shards**. Short tap focuses and shows Tooltip /
price. Hold about 0.5 seconds and lift to request one native purchase. The separate
Comet callable remains responsible for balance, eligibility, stock and inventory.
Standalone Mac-host iPhone-source runs recorded 40 → 15 for a 25-Shard lens,
correct inventory insertion, and refusal of a 30-Shard item with 15 Shards.
A separate 0.9 s drag with 40 Shards left grid/balance unchanged. An earlier run
recorded 20,000 → 19,975. Normal Nomad gold purchasing was also regressed.

Older independent fixtures were structurally given starting currency, but no
purchase success was faked by changing balance/inventory: the game performed
the transactions, and native Save and Quit persisted the result. See
[A–F evidence](compatibility.md) and [historical details](darkest-dungeon-dlc-shop-test.md).
This does not establish all DLC content as completed or iPhone-reaccepted.

## User resources and modes

Provide owned matching Switch DLC containers for preparation. The extractor
checks CNMT identity, required version, index and file hashes. Prepared directory
mode uses a matching `aoc/manifest.json` and includes those verified files in the
private local App/IPA. External NSP mode keeps containers/keys external and does
not bundle the directory-mode AOC tree; its import/discovery setup is separate
from bundled-DLC acceptance. See [building](building.md).

Recognition, mount, save activation, reachable UI, native purchase and full
campaign completion are distinct levels. Never publish containers, extracted DLC,
keys, saves, game-derived shaders or bundled App/IPA products to public GitHub,
Releases or CI artifacts.
