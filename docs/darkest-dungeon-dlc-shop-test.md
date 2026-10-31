> Historical evidence imported from the maintainer snapshot. These are old-project
> runs, not new Dungeon1 device acceptance. See [current compatibility](compatibility.md).

# Darkest Dungeon 1.3.0 — DLC (Comet) supply page: save fixture, policy and Mac-host verification

Date: 2026-10-31. Repository `/Volumes/MacData/code/nxnative-zzg-darkest-dungeon-ios`,
branch `main`, base commit `2c449b92330dc5a9906a51fe111071e9af49b0e0`. Everything in this
document was produced from the working tree without committing, branching or pushing.

The Nomad Wagon has two merchandise pages. The first (`TownUI::Panel::TrinketSupplyDisplay`)
prices trinkets in **gold** and was already delivered and accepted on iPhone. The page the
switch at the bottom-left of the panel opens (`TownUI::Panel::CometTrinketSupplyDisplay`,
the "Comet"/DLC supply) prices them in **shards** and binds a *different* purchase callable.
The iOS hold-to-buy policy now covers both pages; this document records the save fixture,
the static proof for the second callable and what the Mac host actually did.

## 1. Result

| Requirement | Result |
| --- | --- |
| DLC shop reachable on a test save without touching the user's save | yes — independent copies under `/Volumes/MacData/game/darkest-dungeon/dlc-comet-test-20261031/`, the user's Mac save backed up first |
| Comet currency identified and set by a structural save edit | yes — `wallet[6]`, entry type `shard`; `0 → 20000` in one copy, `20000 → 40` in a second |
| Comet callable verified independently (not assumed equal to Nomad) | yes — RTTI name, vtable slot and bound object all read from the binary and re-read at runtime |
| iOS short tap on a Comet row: focus only | yes (two runs) |
| iOS hold ≥ 0.5 s: exactly one native purchase, correct price in shards | yes — 25 shards once per contact |
| Purchased trinket in the trinket inventory | yes — `彗星透镜`, the row's own name |
| Same contact does not buy twice | yes — one debit per contact, no second click |
| Unaffordable Comet row refused | yes — 30-shard row with 15 shards: refused, nothing added |
| Move / cancel before the lift does not buy | yes — iPhone-source drag of 0.9 s over the grid |
| Ordinary Nomad page unchanged | yes — short tap focuses, hold buys once for gold, unaffordable refused |
| iPhone device acceptance | **not done** (host only), see §10 |

## 2. Saves

Nothing here is in Git, and the game's own save is only ever read.

| Path (all outside the repo) | What it is |
| --- | --- |
| `…/dlc-comet-test-20261031/backup-mac-save-before/` | byte copy of the Mac save the previous run had written (172 KiB, `profile_0` gold 6,135, shard 5,000). Made before anything else, never mounted. |
| `…/backup-provided-zip/` | exact extraction of `/Users/zzg/Downloads/save.zip` (`diff -r` against the earlier extraction: identical). `profile_0`: gold 13,480, shard **0**, one trinket (`bleed_stone`). |
| `…/save/` | the working copy for run 1, made from the zip; shard raised to 20,000 |
| `…/save-start/` | snapshot of `save/` as run 1 started (used as the base of run 2) |
| `…/save-low/` | copy of `save-start/` with shard lowered to **40** so an unaffordable row is reachable |
| `…/save.work/`, `…/save-low.work/` | the host's private clone of the mounted save (`hle_fs.c` clones `DM_SAVE` into `<DM_SAVE>.work`); the game's own writes land here, never in the directories above |

Restore is a copy: `cp -R save-start/ save/`. The test save can be reused for any later
run; the numbers below are the only state it carries.

## 3. The save container and the shard write

`persist.*.json` files are **not** JSON text. They are a binary value container:

* magic `0x0000B101` at `+0x00`; object-table bytes/count/offset at `+0x10`, `+0x14`, `+0x18`;
  string-record count/offset at `+0x2c`, `+0x30`; string section size/offset at `+0x38`, `+0x3c`;
* 12-byte string records `{u32 hash, u32 name_off, u32 type}`, hash = base-53 polynomial
  (`h = h*0x35 + c`, 32-bit);
* then a token stream: NUL-terminated keys, 4-byte-aligned `u32` integers, length-prefixed
  strings whose length includes the NUL (the next key then follows unaligned).

`tools/save_wallet.py` (in the test directory) parses that container, finds the wallet by
structure — the run of `{name, amount, type}` records — and validates every key it walks
past before writing anything. It rewrites only the amount word and then re-reads the whole
container. No blind binary search-and-replace is used.

Wallet of `profile_0` in the zip save (8 entries):

```
gold 13480 @0x3a0   bust 14 @0x3c0   portrait 11 @0x3e0   deed 7 @0x404
crest 24 @0x424     blueprint 0 @0x444   shard 0 @0x468     memory 0 @0x488
```

Writes made:

| Copy | Change | Bytes | SHA-256 before → after |
| --- | --- | --- | --- |
| `save/`, `save-start/` | shard `0 → 20000` | only `0x468..0x46b` | `9db51774…88ed7e5` → `25d58f55…5e63300` |
| `save-low/` | shard `20000 → 40` | only `0x468..0x46b` | `25d58f55…5e63300` → `2824ac3d…7d7271` |

The game reads it unchanged: the HUD showed `20,000` in run 1 and `40` in run 2, and the
Comet page rendered shard prices against that pool. (The older Mac save in
`backup-mac-save-before/` has a 7-entry wallet — `blueprint` absent, `shard` at `0x410` —
which is why the tool locates the wallet structurally instead of by fixed offsets.)

## 4. DLC unlock

No entitlement edit was needed. The provided save already records the add-ons
(`persist.game.json`, container strings):

```
presented_dlc → dlc0 name color_of_madness, dlc1 crimson_court, dlc2 fires_edge, …
dlc_init      → dlc0 name color_of_madness, dlc1 districts, dlc2 shieldbreaker, …
```

and the host mounts all five add-on directories (`aoc: 5 available add-on contents`,
`fs mount dlc0..dlc4`). The DLC page's layout gate is
`aoc/4/campaign/town/buildings/nomad_wagon/com.nomad_wagon.layout.darkest`
(`comet_layout`, `.showComet 1`, `.currencyPos 875 735`), read at `0xbd0470`; the same file
sets `comet_inventory_system_grid_layout`. In game, the switch button
(`comet_trinket_supply_switch.png`, referenced at `0xbcfdb8`) sits at the bottom-left of
the panel, normalized `(0.128, 0.765)`; a normal tap there swaps the page.

## 5. The Comet purchase binding — static evidence

All offsets are file offsets in `patched_v393216/main.patched.bin` (main module, build
`ff2bf22565188d11ea0981ee0e2b53ce`), i.e. the same numbers the host adds `dd_base` to.

### 5.1 The row objects are built by the same code as the Nomad page

* `0xe171c0` builds a merchandise row: it allocates the `0x310`-byte
  `Inventory::Display::InventoryButtonInGrid::$_0` wrapper (vtable `0x11933a8`), stores the
  mode/slot word at `+0x300`, the bound `std::function` at `+0x70`, and reaches
  `0xe177ac` (`add x0,sp,#0x80`) — the observation the host hooks (`OBS 30`).
* The Comet display calls the shared grid fill `0xe16370` at `0xc31530`; the Nomad display
  calls it at `0xc2fdbc`. Both pass grid parameters containing the row builder.
* The Comet display class is `TownUI::Panel::CometTrinketSupplyDisplay`, vtable
  `0x117a198` (typeinfo `0x117a438` → `N6TownUI5Panel25CometTrinketSupplyDisplayE`); the
  Nomad one is vtable `0x117a078` (`N6TownUI5Panel20TrinketSupplyDisplayE`).

So the *display* gate (`OBS 30` + vtable `0x11933a8` + mode 0) is identical for both pages;
only the callable at `+0x70` differs, and that is what a policy must not conflate.

### 5.2 The two callables, read from the binary

| | Nomad page | Comet (DLC) page |
| --- | --- | --- |
| callable vtable | `0x117a678` | `0x117a7c0` |
| RTTI name (typeinfo `+0x8`) | `NSt3__110__function6__funcIZN6TownUI5Panel20TrinketSupplyDisplay23PreChildrenShowInternalEvE3$_1FvjEEE` | `NSt3__110__function6__funcIZN6TownUI5Panel25CometTrinketSupplyDisplay23PreChildrenShowInternalEvE3$_1FvjEEE` |
| `operator()` at slot `+0x30` | `0xc30760` (`sub sp,sp,#0xd0`) | `0xc31e00` (`sub sp,sp,#0xb0`) |

The Comet lambda object is constructed at `0xc31310..0xc31320` (0x50 bytes, vtable
`0x117a7c0` stamped into it), bound into the grid parameters at `+0x40` and handed to
`0xe16370` from `0xc31530`. The runtime confirms both halves at once: the census line the
host prints when a row is built names the wrapper vtable, the mode and the *bound callable's*
vtable, e.g.

```
DD shop census: binding vt 0x11933a8 mode 0 cb 0x5906230 cbvt 0x117a678   (Nomad page)
DD shop census: binding vt 0x11933a8 mode 0 cb 0x5952050 cbvt 0x117a7c0   (DLC page)
```

Same wrapper class, same mode, different callback object — the two pages are distinguished
exactly where the policy distinguishes them.

### 5.3 What the Comet callback does with currency

`0xc31e00`, the part that charges the player:

```
c32018  cmp w0,#1
c32024  strb w8,[x23,#0x7d0]      ; stock/flag byte for the clicked row
c32030  adrp x8,0xb19c8000
c32038  ldr  w24,[x24,#0xa0]      ; price
c32044  ldr  w0,[x8,#0x25c]       ; currency entry id (global)
c32048  bl   0xb07a20             ; currency-derived price factor
c3204c  scvtf s1,w24
c32050  fmul s0,s0,s1
c32058  fcvtzs w8,s0
c3205c  sub  w26,w24,w8           ; cost actually charged
c32054  ldr  x9,[x27,#0xe48]      ; wallet end
c32060  ldr  x8,[x27,#0xe40]      ; wallet begin, 0x48-byte entries
c32094  ldr  w11,[x11,#0x44]      ; entry id
c32098  cmp  w11,w25
c320c8  ldr  w9,[x8]              ; balance
c320cc  subs w9,w9,w26
c320d0  str  w9,[x8]              ; charged
c320d4  b.pl 0xc320ec             ; negative → error dialog at 0x8b9610 (text 0xeb1000+0x11)
```

The wallet row is selected by the currency id held at `0xb19c825c`; in the loaded save that
row is `wallet[6]`, whose name string is `shard`, and the in-game HUD shows the same number
(the cyan count). The game therefore decides price, shard balance, capacity, stock and the
"not enough" dialog. The adapter never computes a price, never touches the wallet and never
calls this function itself.

## 6. The host policy change

`dm/host/hle_dd_touch.c`:

* `DD_SHOP_COMET_VT 0x117a7c0` added;
* `dd_shop_binding_ok()` now accepts `+0x70` callable vtable `0x117a678` **or** `0x117a7c0`
  (the wrapper's `0x11933a8`/mode-0 requirement is unchanged);
* `dd_validate()` requires the Comet callable's `+0x30` slot to hold `0xc31e00`;
* the tap latch (`dm_touch_hold_tap`), the 0.5 s rule, the one-click-per-contact rule and
  every refusal path are the *same* code for both pages — nothing was duplicated;
* a new diagnostic line reports a withheld click on a moved/cancelled contact;
* the log wording was generalized from "Nomad supply display" to "supply display".

`dm/host/hle_hid.c` gained `idrag` (an iPhone-source drag) next to `itap`, because a
Mac-mouse `drag` is not an iOS-source contact and therefore does not exercise this policy.

`dm/games/settings.tsv` (the launcher's own toggle description, compiled into the app's
`dm/launcher.json`) no longer says the DLC page is excluded.

Behaviour, unchanged from the accepted Nomad delivery, now on both pages: the row click is
withheld before dispatch; on the lift of a contact held ≥ 0.5 s the game's *own* click is
allowed through once; a short tap, a moved/cancelled contact, a second finger, the secondary
binding and any action outside the identified binding keep their original behaviour.

## 7. Mac-host runs

Host: `dm/host/dmhost` rebuilt 2026-10-31 16:28 from this working tree,
`make -C dm/host GAME=01008F1008DA6000`. Run scripts, logs and screenshots are in
`/Volumes/MacData/game/darkest-dungeon/dlc-comet-test-20261031/` (`run.sh` → `host.log`,
`run2.sh` → `host2.log`, `shots/`). `DM_DD_TOUCH_POLICY=1 DM_DD_TOUCH_DEBUG=1
DM_DD_SHOP_BUILD=1`, `DM_CTL` line file, contacts injected with `itap`/`idrag`
(iPhone contact source).

### 7.1 Run 1 — shard 20,000, gold 13,480 (`host.log`, `shots/e*.png`)

| Step | DM_CTL | Log | Screen evidence |
| --- | --- | --- | --- |
| open wagon | `itap 0.570 0.780 0.10` | `DD shop census … cbvt 0x117a678` (l.489) | Nomad page, two 10,000-gold trinkets |
| switch to DLC page | `itap 0.128 0.765 0.12` | `DD shop census … cbvt 0x117a7c0` (l.803) | Comet page, 18 cells, 25…170, shard **20,000** |
| short tap row 1 | `itap 0.477 0.285 0.12` | `short tap: the game's click is withheld, focus only` (l.830) | `e3`: tooltip `彗星透镜`, price 25, all items still there, shard 20,000 |
| hold 0.9 s, same row | `itap 0.477 0.285 0.9` | `lift after a >=0.5 s hold: the game's own click runs the purchase binding once (contact 21)` (l.850) | `e6`: shard 19,975 (−25), row becomes 25,30,45,45,60,65, gold 13,480 |
| trinket inventory | close panel, open 饰品 | — | `e9`/`e10`: 2 trinkets (was 1 in the save), cyan one reads `彗星透镜` |

### 7.2 Run 2 — shard 40, gold 13,480 (`host2.log`, `shots/h*.png`, `i*.png`, `j1.png`)

Run 2 exists to reach the unaffordable case, and it repeats the Nomad page as a regression.

| Step | DM_CTL | Log | Screen evidence |
| --- | --- | --- | --- |
| Nomad short tap | `itap 0.528 0.340 0.12` | `short tap: the game's click is withheld, focus only` (l.688) | `h1`: tooltip `医者挂坠`, both rows still 10,000, gold 13,480 |
| Nomad hold | `itap 0.483 0.340 0.9` | `lift after a >=0.5 s hold … once (contact 10)` (l.701) | `h3`: gold 13,480 → **3,480**, one row left, shard 40 untouched |
| Nomad hold, cannot afford | `itap 0.483 0.340 0.9` | latch only (l.718), no purchase line | `h4`: gold 3,480, row still 10,000 — the game itself refused |
| switch to DLC page | `itap 0.128 0.765 0.12` | `DD shop census … cbvt 0x117a7c0` (l.732) | `h5`: 18 cells, shard 40 |
| DLC short tap | `itap 0.477 0.285 0.12` | `short tap: … focus only` (l.744) | `h6`: tooltip, shard 40, nothing sold |
| DLC move past the slop, held 0.9 s | `idrag 0.477 0.285 0.560 0.520 0.9` | iPhone-source drag (l.756), latch only (l.757) — no purchase line | `h7`: shard 40, grid unchanged, no scroll |
| DLC hold | `itap 0.477 0.285 0.9` | `lift after a >=0.5 s hold … once (contact 15)` (l.774) | `h8`: shard 40 → **15** (−25), row becomes 25,30,45,45,60,65 |
| DLC hold, cannot afford (30) | `itap 0.520 0.285 0.9` | latch only (l.786), no purchase line | `i6`: shard 15, grid unchanged — refused |
| trinket inventory | close panel, open 饰品 | — | `i8`/`j1`: 3 trinkets (base save had 1): `bleed_stone`, `医者挂坠` (the Nomad purchase), `彗星透镜` (the DLC purchase) |

Both runs are single-purchase: one deducted price per accepted contact, no second debit, and
the only "purchase" lines are the two in the tables.

### 7.3 What the refusals look like

* **Short tap** — the click is dropped before dispatch, the game still shows the tooltip:
  `short tap: the game's click is withheld, focus only`.
* **Move / cancel** — the contact's phase becomes `CANCELLED` at the 8 px slop, so no click
  is dispatched at all; if one were, the filter refuses it and prints
  `moved, cancelled or second-fingered contact: the game's click is withheld`.
* **Unaffordable** — the adapter still lets the game's own click through (the contact was
  held long enough); the *game's* callback finds the balance short and refuses. Nothing is
  debited and no row leaves the grid. This is the proof that no currency check is bypassed.
* **Contact outside the rows** (the panel's close button, the merchant, the switch) — not a
  merchandise binding, so it keeps the original path; the close button closed the panel.
* **Second finger, contact taken by the controller, closed panel** — rejected by the host
  policy and by the unit tests (a click is never replayed, no game object is kept between
  frames, so a closed panel cannot be bought from).

## 8. Tests

* `dm/host/tests/t_dd_touch`: **154 checks, 0 failed** (`make -C dm/host/tests
  GAME=01008F1008DA6000 run`, whole suite exit 0). The shop section covers the secondary
  binding, drag mode, foreign callbacks, a module without the gates, the armed contact
  producing `TOUCH → TOUCH → TAP` with exactly one purchase, a repeated click refused, a
  short tap buying nothing, cancel and move disarming, a contact outside the display never
  arming, and the Comet callable marking the display.
* `t_gesture` 59/0 and the rest of the host suite unchanged.

## 9. Not done

* No iPhone/iPad run: the device acceptance list is §29.8 of
  `docs/darkest-dungeon-touch-interaction-audit.md` plus item 7 there (the DLC page).
* The second-finger and close-while-holding cases were exercised only by the unit tests,
  not live on the Mac host (the host injects one contact at a time).
* The Mac-mouse path on the DLC page was not re-examined beyond "a mouse drag does not
  buy"; the iOS policy never applies to it.

## 10. Reproduce

```sh
T=/Volumes/MacData/game/darkest-dungeon/dlc-comet-test-20261031
python3 $T/tools/save_wallet.py dump $T/save-start/profile_0/persist.estate.json   # wallet[6] shard
python3 $T/tools/save_wallet.py set  $T/save-low/profile_0/persist.estate.json shard 40
$T/run2.sh                                    # DM_SAVE=$T/save-low, DM_CTL=$T/ctl2.txt
printf 'itap 0.500 0.500 0.12\n' >> $T/ctl2.txt     # skip splash
printf 'itap 0.500 0.500 0.12\n' >> $T/ctl2.txt     # intro text
printf 'itap 0.500 0.500 0.12\n' >> $T/ctl2.txt     # past the intro movie
printf 'itap 0.500 0.850 0.12\n' >> $T/ctl2.txt     # 战役
printf 'itap 0.470 0.600 0.12\n' >> $T/ctl2.txt     # first profile
printf 'itap 0.773 0.156 0.10\n' >> $T/ctl2.txt     # close the town-event dialog
printf 'itap 0.570 0.780 0.10\n' >> $T/ctl2.txt     # nomad wagon
printf 'itap 0.128 0.765 0.12\n' >> $T/ctl2.txt     # switch to the DLC page
```

Then `itap <x> <y> <seconds>` (still contact) or `idrag x0 y0 x1 y1 <seconds>` (moving
contact), with `shot <path>` between steps.
