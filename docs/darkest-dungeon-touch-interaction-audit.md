> Historical evidence imported from the maintainer snapshot. These are old-project
> runs, not new Dungeon1 device acceptance. Current standalone iPhone installation,
> startup and coexistence are user-confirmed; see [current compatibility](compatibility.md).
> Pending labels below retain their historical dates/scope, not current overall status.

# Darkest Dungeon 1.3.0 touch interaction audit

Date: 2026-10-29. Initial static audit below; the development-only update in
section 9 records the current uncompiled working-tree implementation.

## Initial static-audit scope, provenance and decision

Repository: `/Volumes/MacData/code/nxnative-zzg-darkest-dungeon-ios`.
Branch: `main`; HEAD: `6dcf9868582388173f81f4f02385cd4cdb125b3e`.
During the initial static-audit round, the worktree was clean at the start and
this report was the only repository addition. That initial round made no
production changes, compilation, game launch, tests, LLDB, commit or push.
The later development round is documented separately in section 9. No original module, NSP, RomFS, DLC, shader or save was modified.
The resolved tutorial and iOS trinket-box rendering issues are out of scope.

Original input inspected:
`/Volumes/MacData/code/.worktmp/darkest-dungeon-1.3.0/extract/exefs-1.3.0/ExeFS/main`.
Its header Build ID is `ff2bf22565188d11ea0981ee0e2b53ce`; file SHA-256:
`2f7814c5ebae541c80bba58902f40d782d0c61eece320044ab82491251353db1`.
The existing NSO reader decoded its segments in memory and checked declared segment
hashes; Capstone decoded original AArch64 instructions. Function boundaries were
cross-checked against the exception-frame index (38,616 ranges), and RTTI/vtable
pointers against relocation-derived pointer values. No modified/prepared main was
used to choose an instruction address. All addresses below are **original main
module offsets**, never host absolute addresses or approved patch sites.

Evidence labels:

- **S**: current source or original instruction/data evidence, re-read this round.
- **I**: static interpretation of those instructions; needs scene confirmation.
- **U**: unresolved ABI, mapping or behavior; no dynamic proof this round.
- **P**: proposed future implementation; not implemented or tested.

| Request | Feasibility | Smallest credible location | Readiness / difficulty |
| --- | --- | --- | --- |
| A. Trinket short tap only hovers, long press performs the contextual action | Feasible in principle; purchase/equip/sell are not one universal operation | Title-specific slot/control policy, preserving existing actions and drag contexts | Medium-high; all mutation edges and item classification must be closed first |
| B. Portrait long press replaces double tap | Feasible in principle; do not globally manufacture double taps | Portrait-specific operation mapping plus shared press lifetime | Medium; town/raid portrait callbacks and their gesture-result mapping are not fully closed |
| C. Character-details combat skills short tap hovers, long press toggles | Strongest static candidate: selected-skill mutation callback identified | CharacterDisplay combat-grid action gate | Medium; queue timing and action-edge mapping still need later validation |

**Decision:** reuse the existing gesture recognizer and original UI callbacks,
with one title-specific, iOS-touch-only interaction policy. A UIKit-only change,
a global Tap-to-Press replacement, or the existing Mac pointer handoff alone
cannot safely implement all three requests. Some game-specific UI hooks are
needed for accurate control identity and operation suppression. No original NSP
needs to be modified; any future prepared-module gates must be restricted to this
Build ID and validate original instructions.

## 1. Current source pipeline and limits

| Source | Actual responsibility / evidence |
| --- | --- |
| `dm/ios/Sources/DmGamepad.m` | `gameBegin`, `pushGame`, `touchesBegan/Moved`, `endTouches`: retain finger ownership; convert the centered 16:9 picture to normalized coordinates; publish the entire unclaimed game-touch set. Virtual pad/layout touches are handled separately. No `UITouch.tapCount` use or native long-press recognizer implements these game actions. |
| `dm/ios/Sources/front_ios.m` | Focus events, suspension and gamepad reset; it does not know game widget types. |
| `dm/host/front.h` | `dm_touch {id,x,y}` and `dm_touch_set(points,count)`; no input-source or explicit cancellation reason in this ABI. |
| `dm/host/dm_input.h`, `hle_hid.c` | Npad and optional Mouse HID; HID touch/gesture exports call `touch_fill_n` / `gesture_fill`. A HID sample contains no inventory, hero or skill identity. |
| `dm/host/hle_touch.c` | Mutex-protected touch latch and independent gesture history from the same contacts. Coordinates become 1280x720 panel coordinates. |
| `dm/host/dd_pointer.h`, `hle_dd_pointer_mac.c` | Opt-in Mac **coordinate-only** handoff; no click/toggle/long-press dispatch. Fresh Mouse HID revision required, mode=0 and auto-controller flag clear. |
| `dm/games/01008F1008DA6000/patches.py` | Existing MOD cuts and Build-ID-restricted observation gate 22 at `0x8b5dc0`, original word `0x1e204120`. This gate is after input polling, before UI processing; it is not an identified per-widget action API. |
| `dm/ios/tools/gen_build.py` | Excludes source stems ending `_mac`; the current `hle_dd_pointer_mac.c` is not an iOS touch bridge. |

**S: existing recognizer semantics.** `GT_TOUCH=3`, `GT_PRESS=4`, `GT_TAP=5`,
`GT_PAN=6`, `GT_CANCEL=2`. A stationary single contact becomes Press after
`dt > 0.5 s`, when the game reads gestures. Movement greater than 8 panel pixels
in either axis exits the slop region. A Press release produces Complete, then
Idle, **not Tap**. A short Touch release produces Tap, then Complete/Idle.
Gesture sampling numbers/history ensure the game can distinguish new samples.
This is a reusable threshold and release-suppression mechanism, not proof that
the game's Press branch performs the requested operations.

**S: double-tap recognition is currently in the Host recognizer.** A Tap gets
attribute bit 8 (`0x100`) if the previous Tap was less than 350 ms earlier.
That Host condition does not check the same control, position or hero. The game
may impose additional control/context checks; cross-control double-tap safety is
not established. Replacing UIKit double-click handling would therefore miss the
actual producer.

**S: cancellation loses information today.** `touchesCancelled` calls
`endTouches(...,tapped:NO)`, but that flag only affects the layout-button action.
Game contacts are removed and `pushGame` publishes the same disappearance as a
normal lift. `dm_touch_set` cannot distinguish cancellation from End. Therefore a
short cancelled contact can follow the recognizer's ordinary Touch→Tap path if
sampled in that state. `front_ios_focus_event(0)` calls `dm_gamepad_reset`, which
asynchronously clears game touches and publishes an empty set. Actual timing
across suspension is **U**. A future long-press feature needs an explicit cancel
reason/generation, not just a release event.

Git history supports the source findings: `f596c75` introduced general gestures
for Taiko, including Press, Tap/double-tap, slop and history; `5f8a049` / `083b076`
added the iOS layout/touchscreen routing and switch; `998ce8a` introduced the
restricted Mac pointer experiment. These are not previous implementations of
A/B/C. Existing test sources were read as context; **no tests were run**.

## 2. Original input and UI event chain

The following prefix is **S**, confirmed again against original instructions:

```text
main loop 0x8b5dbc -> input poll 0x74ac70
  0x74b58c -> PLT 0xe69d90 -> nn::hid::GetGestureStates
  0x74b604..60c: sampling-number freshness
  0x74b610..650: input-mode/auto-controller decision and focus clearing
  0x74b660 onward: GestureState.type dispatch
    Touch / Press: 0x74b7a0 onward (types 3 / 4)
    Tap: 0x74b9a8 onward (type 5)
    Cancel: 0x74b684 stores internal event code 7
  -> game touch/context state and coordinates
post-poll 0x8b5dc0; UI/controller update call 0x8b5dc4 -> 0x8e6b10
  -> scene/panel controls -> hit result -> operation callback or tooltip descriptor
```

**S:** Tap reads `GestureState.attributes` at `0x74bc1c`, tests `0x100` at
`0x74bc20`, and selects internal event code 3 or 4 at `0x74bc24..3c`.
The internal code must not be confused with the SDK GestureType enum (where 4
means Press). Press and SDK double Tap are different input paths.

**S:** `0x738eb0` is a common interaction function, not a geometry-only test.
Its hit calls are `0x739130 -> 0x738c30` or `0x739148 -> 0x738960`.
It consumes target-ID/pending flags through the object pointer at `0x27e0600`:
`0x738fc8..fdc` uses object+6/+8; `0x739068..7c` uses +0x10/+0x18;
`0x7390ec..100` uses +0x20/+0x28. Clearing only a return bit after these stores
would not undo all input consumption or focus/drag state.

At `0x739c84..cb4`, x0 packs six result bytes:
`byte0=w8, byte1=w20, byte2=w21, byte3=w27, byte4=w22, byte5=w25`.
The geometry-derived hover result feeds byte0; **U:** a complete, named contract
for every action byte across touch, controller and drag paths is not recovered.
No byte is arbitrarily labelled DoubleClick or LongPress in this audit.

**S:** wrapper `0x73b6d0` calls interaction at `0x73b83c`. Hover bit 0 plus a
non-null descriptor causes `0x73bc38 -> 0x739cd0` tooltip registration. Separately,
result bits 8/16/24/32 gate four supplied callable objects at
`0x73bc3c`, `0x73bcc8`, `0x73bd54`, `0x73bdd8`. The code clones/enqueues these
callables into the vector based at `0x257e530` (end at `0x257e538`), rather than
necessarily executing the final action immediately in the hit test.
The exact queue-drain stage/ownership and all wrappers' argument mappings remain
**U**; `0x739cd0 -> 0x730a60` is the separate tooltip registration/consumption
chain, not the operation queue.

**I:** preserve the hover byte/descriptor pipeline and filter only the appropriate
operation edges for a proven target/source. Returning zero from `0x738eb0`,
blocking all gestures, or forcing the tooltip queue would violate the goals.

## 3. A — Trinkets: paths, identification and action preservation

### Scene coverage

| Scene | S: concrete static path | Remaining boundary |
| --- | --- | --- |
| Nomad Wagon purchase display | RTTI/vtable `NomadWagonDisplay`, vtable `0x117a2b8`; factory `0xc326c0` installs `TrinketSupplyDisplay` vtable `0x117a078` at `0xc32730`. Its display method `0xc2fab0` calls `0xe16370` at `0xc2fdbc`. | The final purchase/currency/stock transaction callback and every possible confirm-dialog route are not closed. Do not call the supply renderer itself a purchase function. |
| Comet/shard trinket supply | `CometTrinketSupplyDisplay` vtable `0x117a198`; method `0xc31120 -> (0xc31530) 0xe16370`. | Price/currency/availability differences and transaction callback need separate binding, despite shared display code. Resolved 2026-10-31: the callback is `0x117a7c0 -> 0xc31e00` and is bound as its own callable (§14.2, `docs/darkest-dungeon-dlc-shop-test.md`). |
| Character-details equipped trinkets | `0xe32da0` references `character_title_trinkets`; `0xe33464 -> 0xe06900 -> (0xe06b98) 0xe184a0`. | Preserve equipped-slot identity and selected hero. |
| Raid hero equipment / inventory context | `0xd1ff30 -> (0xd20a30) 0xe184a0`; Panel_Hero and common equipment interface. | Distinguish combat restrictions and modal context. |
| Backpack / raid inventory slots | `0xe16370 -> (0xe16e34) 0xe171c0`. Assertions identify raid inventory slot lookup. | Includes non-trinkets; a blanket inventory filter would break food, torches and quest items. |
| Town trinket storage | RTTI `RealmInventory`, method `0xc4e9f0`; `0xc519e8 -> 0xe184a0`; strings include realm inventory, sell instructions and unequip-all. | Slot actions and separate sell/unequip-all buttons require distinct policy; do not accidentally change the latter. |
| Provision selection / reused inventory UI | `0xc33fd0` calls `0xe184a0` at `0xc34b20` and `0xc34e28`; its sell-back strings identify this as a provision context, **not Nomad Wagon**. | Preserve ordinary items and provision actions. Loot/reward/other reused contexts are not exhaustively enumerated; unknown owners must retain original behavior. |

Common slot pipeline, **S**:

```text
e184a0 -> e18f4c -> e171c0        or e16370 -> e16e34 -> e171c0
e171c0 -> e1788c -> e13120
  e14320 -> 73c780 -> 73bf90 -> 738eb0 -> geometry test
  e14324 retains result; e143dc masks/stores it; e14d44..60 unpacks bytes
  hover/focus branch e15358 onward, with slot flag +e5
  e1570c -> e15ed0 -> e16164 -> e0fae0 (description)
                      e16284 -> 739cd0 (tooltip registration)
```

An additional description path in `0xe184a0` uses `0xe19740 -> 0x738960` and
`0xe19b70 -> 0x739cd0`. Thus not every tooltip uses the same slot branch.

### Operations are separate from hover, but include drag transactions

**S:** `EquipmentSlotInterface` vtable `0x11934a8` has:

- slot +0x10 `0xe1a7f0`: assertion names `OnPickedUp`, equipment drag data, and
  `/ui/dungeon/trink_unequip`; calls `0xdf4720`.
- slots +0x18 `0xe1a930` and +0x20 `0xe1aa10`: data comparisons and calls into
  `0xb5ab50` / `0xb5a8e0`; the latter also calls `0x9ce980` on the hero context.
  **I:** removal/replacement and related drag transaction stages; exact public
  method names for these two slots are not asserted in their bodies.
- +0x38 `0xe1abb0`: returns a lazily assigned runtime type ID address.

**S:** `InventoryItemSlotInterface` vtable `0x1193c08` and
`RealmInventorySlotInterface` vtable `0x11939d8` share +0x10 `0xe1ba50`
(`OnPickedUp` assertion), +0x18 `0xe1bb10`, +0x20 `0xe1bc00`, and +0x28
`0xe1bd10` (includes an invalid-trinket-unlock confirmation reference).
The +0x38 type-ID getters differ (`0xe1be00`, `0xe1ed00`), as do other slots.
`TrinketDropAreaInventoryInterface` also shares several of these methods.
Consequently the pickup method alone does **not** identify a trinket.

**S:** CharacterDisplay equipment setup callable `0xe3c6f0`, vtable
`0x1194e48` +0x30, explicitly checks an equipment-interface type via virtual
+0x38 and writes the captured hero context to interface+0xc8 at `0xe3c794`.
This is **setup**, not a verified equip-on-click function.

**P: identification.** Use `(active panel/owner, slot interface type, current
item classification, item identity, slot index, hero identity, generation)`.
Reuse the game's type getter and item classifier/description input once their ABI
is recovered. Runtime type IDs are lazily allocated, so do not hard-code their
numeric values. Do not classify by an icon, filename, screen rectangle alone,
Equipment interface alone, or shared `OnPickedUp` address. The exact item-type
field/enum suitable for a stable cross-scene classifier is **U**.

**P: minimal behavior.** Short tap may update/retain the pointer and normal tooltip
but must not enqueue an operation, mutate inventory, start an irreversible pickup
or execute a synthetic release/drop. Long press authorizes **one original
contextual operation**, retaining price, class restrictions, capacity, confirmation
and availability checks. Intercept before the first mutating edge, not only at
the final purchase function. Existing drag creation/pickup/commit/cancel must be
mapped before enabling this for inventory.

A single long press cannot choose a destination hero, choose between equip and
sell, or manufacture a missing drag destination. Where original single-click has
a defined contextual action, reuse it. Where the original flow is drag/drop or an
explicit sell command, preserve that flow after deliberate hold/drag or the
existing command. Do not reinterpret every long hold as “sell”. **U:** it is not
yet proven that all purchase/equip/unequip/sell paths can share one operation
callback; only the recognition/policy state machine can be shared.

**Difficulty / later validation:** highest of A/B/C. Close shop transactions,
item classification, every pickup/commit path, scrolling versus drag priority,
full/empty slots, swaps, buy/sell cancellation, DLC supply, price changes and
owner destruction before asserting that trinket management remains usable.

## 4. B — Portrait double tap to long press

**S:** no frontend UIKit double-click action was found. The actual prefix is
Host double-Tap attribute -> input poll `0x74bc1c..3c` -> internal event/context
-> common control results -> supplied portrait callable.

Town roster evidence:

- RTTI `TownUI::Panel::RosterElement`, method `0xc5c6c0`.
- Geometry sites `0xc5c79c` and `0xc5efb0`; the latter can call `0xc610e0` for
  timed/animated display behavior. They are not themselves a double-click API.
- `0xc60080 -> 0x73b6d0` receives two nonempty callable objects:
  vtables `0x117cd40` (`PreChildrenShowInternal::$_1`) and `0x117cdc0` (`$_2`).
- +0x30 call operators are `0xc61890` and `0xc615b0`. `0xc61890` checks an
  object+0x140 predicate, then invokes the owner-supplied callable at +0xb0.
  `0xc615b0` updates roster selection/animations and calls `0xcb59a0` with a
  roster-context callback. A separate control at `0xc5cba0` supplies `$_0`,
  operator `0xc61ae0`, which forwards owner callback +0xe0.

Raid/detail boundary:
`Panel_Hero` and character display are not the town RosterElement. A controller
path at `0x969e00` explicitly prints `DungeonController::ToggleCharacterDisplay()`
and reaches `0xe257e0` or `0xd6d2c0`. This is evidence of an existing character
panel toggle, **not proof that every portrait double tap calls that function**.

**U:** this round does not fully close SDK double-Tap -> named control-result
byte -> exact single/double callable -> final character-panel operation for both
town and raid portraits. It would be false to declare `0xc61890`, `0xc615b0` or
`0x969e00` a universal “portrait double click” hook. Ordinary roster selection,
embark assignment, hero details and drag targets can have different owners.

**P: minimal behavior.** Register only the proven portrait targets. Keep the
original single-selection action at its existing point in the flow. When a held
contact crosses the Press threshold on the same hero/owner, invoke the original
**verified double-action callable** once on the game thread. Mark the contact
consumed and suppress its release Tap/double Tap for that target. Do not generate
a second physical tap, globally set IsDoubleTap, or invoke the controller toggle
without confirming context. If a short selection must occur before the long
operation, reuse selection once; never replay it on release after the long action.

Movement beyond slop, leaving the portrait, a second finger, list scrolling,
hero replacement/removal, modal change, focus loss or TouchCancel cancels the hold.
A portrait drag should retain the existing selection/drag behavior; the long-action
must not also fire after drag ownership has been granted.

**Feasibility / difficulty:** medium once both portrait variants are identified;
not implementation-ready from the listed candidates alone. Later validation must
identify the intended town/raid portrait variants, distinguish single/double
callback counts, and check that one hold opens the intended details view once.

### 2026-10-29 closure: B is answered negatively, so nothing was enabled

This round reopened the question over the same 1.3.0 `main`
(`ff2bf22565188d11ea0981ee0e2b53ce`) with read-only decoding, to decide between
implementing the hold and leaving the roster alone. The answer is that there is no
"original double-click operation" behind `0xc60080` to preserve:

- **Owner is confirmed, and it is the town roster.** The two `std::function`
  target vtables used at `0xc60080` (`0x117cd40`, `0x117cdc0`) carry the RTTI
  names `std::__1::__function::__func<TownUI::Panel::RosterElement::PreChildrenShowInternal()::$_1, void ()>`
  and `...::$_2, void ()>`. So `0xc61890` / `0xc615b0` are `void()` lambdas of
  `TownUI::Panel::RosterElement::PreChildrenShowInternal`, and `0xc60080` is the
  call that hands them to the shared dispatcher. `0xc61ae0` (`$_0`) belongs to the
  neighbouring control at `0xc5cba0` and forwards to the owner callback at `+0xe0`.
- **The call is a four-callback event dispatch, not a click-count test.**
  `0xc60080` calls `0x73b6d0(widget = sp+0x6a0, fn_a = sp+0xa0, fn_b = sp+0x70,
  fn_c = sp+0x40, fn_d = sp+0x10)`. Inside, the packed mask from `0x738eb0` picks
  the actions: bit 8 pushes `fn_a` when `[widget+0x91]&1`, bit 16 pushes `fn_c`
  when `[widget+0x92]&1`, bit 24 pushes `fn_d` when `[widget+0x91]&1`, and bit 0
  runs `0x739cd0`. Every push is the native
  `vector<std::function<void()>>::push_back` helper `0x717370` on the action queue
  `0x257e530` that `0x8b5dd0..0x8b5dfc` drains after input polling.
- **`0x738eb0` has no way to recognise a double click.** Its only calls are hit
  tests (`0x738960`, `0x738c30` over the pointer-id sets at `0x257e740`), the
  membership query `0x74d510` over the held-contact set at `0x27e08b0`,
  `0x7307c0`, and two layout calls to `0x6e9990`. It reads no clock in its own
  body (`mrs cntvct_el0`/`cntpct` absent, no time import) and keeps no per-widget
  click count. What it returns is which of the pending contact records at
  `0x27e0600` (`+0x08/+0x06`, `+0x18/+0x10`, `+0x28/+0x20`) match this widget and
  whether the contact's id is currently held. The matching records are consumed
  (`strb wzr`, `str xzr`), so a second read cannot see the same event twice.
- **The game has no double-click vocabulary.** `main` names
  `/ui/town/button_click`, `/ui/town/button_click_back`,
  `/ui/town/button_click_locked`, `/ui/shared/button_click`,
  `/ui/shared/button_click_enemy`, `/general/raid_screen/hero_click`,
  `/general/raid_screen/town_click`, `/general/raid_screen/quirk_click`,
  `/ui/dungeon/pit_activate_click` and `interaction_click_sound`; no string, and no
  comparable constant or timer, names a double click.

The three callables are therefore deferred actions of ordinary pointer events:
`0xc61890` forwards to the owner callables at `+0x140` and `+0xb0`; `0xc615b0`
sets `[element+0x231]` and tweens `element+0x410` with `easeInOutSine` across the
element vector at `+0x80` (selection highlight); `0xc61ae0` forwards to `+0xe0`.
Executing one of them from a 0.5 s hold would synthesise a new action from a
callable built for the frame in which the game itself saw the event — it would not
replay anything the game already does on a double tap, and a wrong pick is a state
change with no original to fall back on. Consistent with the request's own rule
for insufficient evidence, **the town roster keeps its original behavior**
(short tap selection, drag, and multi-touch untouched), and the Mac left button is
unchanged. No new gate, filter or setting was added for the roster.

## 5. C — Character-details combat skill toggle

This has the clearest mutation endpoint and a separate hover path.

**S: concrete action binding.** `0xe33d40` references
`character_title_combat_skills` and prepares `ShowCombatSkillGrid` callbacks:

| Role | Vtable / operator | Instruction evidence |
| --- | --- | --- |
| Selected predicate, lambda `$_3` | `0x1195108` +0x30 -> `0xe3bdf0` | Searches hero+[0x1340,0x1348) for the skill index |
| Eligibility predicate, lambda `$_4` | `0x1195198` +0x30 -> `0xe3bd10` | Separate from selected state; retain it |
| Toggle action, lambda `$_5` | `0x1195228` +0x30 -> `0xe3b5a0` | Bound at `0xe33d98..da0`; selected list is actually mutated |
| Tooltip, lambda `$_6` | `0x11952a8` +0x30 -> `0xe3afd0` | Bound at `0xe33dbc..dcc`; calls `0xdfe030` to build descriptor |

**S:** toggle `0xe3b5a0` extracts the hero from `*x1`, the skill index from `*x2`
and panel context from callable+8. It checks class configuration byte +0x121c,
compares the list size against the configured maximum at +0x1220, adds through
`0xe3b66c -> 0x6eee50`, or removes using `0xe3b698 -> memmove` and updates the
vector end at `0xe3b6a0`. It invalidates a cached value at hero+0x13a0, updates
selection animations, and calls `0xdb62c0`, `0xe3b7c0`, `0xe3a8f0`.
Returning false without touching the vector is possible on its original guards.
This is a real selected-skill toggle, not merely visual checkbox decoration.
Do not replace it by directly XORing a hero field or bypassing the maximum.

**S: action UI versus tooltip UI.** `0xe340c8` calls shared skill renderer
`0xe38460` (`ShowSkillGrid`; RTTI recovered from its wrapper):

```text
combat grid e33d40 -> e340c8 -> e38460
 action control: e39078..80 installs wrapper vtable 11956b8
                 e39114 -> 73c780 -> common control family
                 original queued wrapper -> e39fe0
                 e39ff0 checks class+12d; e3a024 calls captured callable +30
                 combat-bound callable is e3b5a0 (toggle)
 hover control: e39568 invokes tooltip builder
                e39578 stores descriptor at control+50
                e3959c -> 73b6d0 -> hover registration 73bc38 -> 739cd0
```

The generic skill renderer also has a caller at `0xe2d6e8` for another grid;
it must not be globally treated as combat-skill activation. **U:** the precise
Touch/Press/result edge that enqueues the action wrapper, and its queue-drain
moment, still need a later authorized observation. Static callback capture and
mutation establish the intended action, not runtime call counts.

**P: minimal behavior.** Match CharacterDisplay **combat** grid + hero + skill
index + stable panel generation. Preserve descriptor creation, hit testing,
selected predicate, disabled/locked rendering and eligibility checks. Suppress
the short-touch action enqueue; on one qualified Press, enqueue the same original
wrapped toggle with current valid captures. Suppress all remaining action edges
from that contact, including release Tap. Re-evaluate the original predicates at
execution so a panel/skill-list change during the hold cannot toggle stale data.

Do not filter `0x738eb0` for every skill, do not hook global `memmove` or the
selected vector helper, and do not replace the shared renderer unconditionally.
Battle skill selection/targeting, Guild upgrades, camping skills and other skill
grids are excluded by owner + combat-grid identity + callable binding.

**Feasibility / difficulty:** medium; implement C first as the narrow proof of
the shared policy. Later checks must cover enable/disable, locked skills, maximum
selected count, holding an already-selected skill, hero switching, an alternate
skill grid, battle selection and upgrade screens, with exactly one mutation per
long press and zero per short tap/cancel.

## 6. Shared minimal design for a later development round

All entries in this section are **P**, not new APIs present in the repository.

### Responsibility split

1. **iOS frontend:** attach a source/contact generation and explicit Down/Move/
   Up/Cancel to game-touch publications; retain existing picture transform and
   virtual-pad ownership. No hard-coded widget rectangles, game functions or
   inventory logic in UIKit. Distinguish real iOS contacts from Mac's left-touch
   emulation; current `dm_touch_set` alone carries no source discriminator.
2. **Gesture layer:** reuse the 0.5 s Press and 8 px slop rules. If adding generic
   cancellation fidelity, preserve ordinary games' Tap/Pan/history contracts and
   add an explicit cancellation path rather than treating cancel as zero points.
   Do not change global double-tap timing or Press behavior for this feature.
3. **Title-specific shared adapter:** one contact lifetime/policy for A/B/C,
   opt-in and iOS-touch-origin only. It owns the candidate target, hold/consumed/
   drag/cancel state and a coordinate-only touch cursor snapshot. The current
   `_mac.c` adapter cannot supply this on iOS without new shared integration.
4. **Restricted game UI gates:** register semantic targets and their original
   action bindings at the proven slot/grid/portrait layers; preserve hover and
   modal rules; suppress or authorize operations before they mutate/enqueue.
   Unknown owners/types continue through the original path.

A registry key should contain semantic item/hero/skill/slot identity and owner
lifetime, not a stack control address. `0x738eb0` replaces control IDs and wrappers
construct controls/callables on the stack; raw pointers or generated IDs alone
are not established to persist across frames. Do not save those pointers until
finger-up. Retain/copy a valid original callable using its existing mechanism,
or resolve the semantic target again on the game thread.

### One recognition state machine, three policies

| State/event | Common behavior | A / C | B |
| --- | --- | --- | --- |
| Down on a whitelisted target | Record contact, owner/generation, target identity, coordinates and start time | Permit hover; defer all mutating click/pickup edges | Preserve original single-selection behavior once |
| Stationary before threshold | Refresh allowed pointer/tooltip through original UI rules | No purchase/equip/sell/toggle | No double-action yet |
| Qualified Press, same live target | Validate source, active panel, no modal/controller takeover; issue one authorization token | Reuse original contextual action/toggle | Reuse verified portrait double-action |
| Up after long action | Drain contact; consumed token forbids any repeated action | No Tap, drop or inverse toggle | No second selection/double action |
| Up before threshold | End contact but retain valid touch cursor for original tooltip lifetime | Hover only; no action | Original short behavior retained |
| Move beyond slop / leave / scroll | Cancel long candidate or transfer to an explicitly allowed drag owner | No delayed long action or drop from an unstarted pickup | Do not open details during portrait drag |
| Cancel / focus loss / second finger / owner destroyed / controller takes over | Invalidate generation, authorization and deferred actions; release captured objects | No fallback Tap or commit | No fallback double action |

The recognizer's Press→Complete already avoids a normal release Tap, but the
adapter must also suppress queued actions and pending game-context edges for
that consumed contact. Merely relying on GestureType history is insufficient
if an action was already queued on TouchDown. Do not emit synthetic Contact Up
at the threshold: that can itself create a Tap/commit. An operation token must
be claimed once by the matching target, not by the first widget visited in a UI
traversal, and must expire before a later frame/scene can reuse it.

### Hover, drag and controller constraints

The internal UI pointer lives at `0x27e0890/894`. Touch processing writes it,
but prior read-only evidence also lists controller/focus writers, including
`0x746c70` and `0x96ff60`. No-touch-after-release does not guarantee persistence
in every state. A future iOS touch cursor should hand off only under the game's
existing noncontroller ownership and respect subsequent focus/mode changes.
Do not force `neverusecontroller`, write `mode` / `auto_flag`, or clear tooltip
suppression counters. Preserve touch-driven auto switching. Whether a purely
hover short tap can retain its tooltip after all UI phases is a later check.

Drag requires an explicit contract: a hold may deliberately unlock pickup/drag,
or movement may retain the original drag behavior, but cancel/short release must
never commit an unstarted transaction. Do not replay buffered raw gestures after
an ambiguous target classification: replaying a down/up can buy an item that was
supposed to hover. Gate the operation paths while leaving unrelated controls'
raw input intact. Verify target identity at Down and action time; a scrolled or
re-sorted item under the finger is not automatically the same target.

### Files that would minimally change

| Future file/location | Purpose |
| --- | --- |
| `dm/ios/Sources/DmGamepad.m` and focus/reset integration in `front_ios.m` | Small source-aware contact/cancel publications; preserve existing routing |
| `dm/host/front.h` or `dm_input.h` | Optional semantic contact/cancel snapshot contract, no game data in generic HID |
| `dm/host/hle_touch.c`, only if needed | Correct explicit cancellation; reuse Press/slop rather than a second per-widget recognizer |
| A new shared title adapter, e.g. `dm/host/hle_dd_touch.c` + small policy header | One A/B/C state machine and operation token; iOS-only policy selection, game-thread handling |
| `dm/host/dd_pointer.h` / existing `_mac.c` | At most share a neutral policy/snapshot helper; do not turn on touch remapping for Mac |
| `dm/games/01008F1008DA6000/patches.py` | Future verified observation/replacement gates for UI target/action boundaries, not production cuts chosen by this report |

No render, shader, RomFS, original NSP, per-frame input-mode forcing or global
Mouse HID change is needed for this design. The same rewritten Build-ID-gated
logic can serve bundled and external-container builds because the proposed
classification uses live game UI objects, not resource packaging paths.

## 7. Risks, evidence gaps and development order

### Required gaps to close before a production patch

- **A:** classify an actual item as trinket without conflating all inventory
  items; map shop buy/currency/stock, equip/unequip, sell and every drag-commit edge.
  No universal trinket operation callback has been proved.
- **B:** close the exact portrait double-action on town and raid variants; map
  internal event 4 to the portrait's action byte and owner callback. Do not assume
  a controller toggle is interchangeable with a portrait action.
- **C:** confirm the queued action edge/capture lifetime and long-release
  suppression around the proven `0xe39fe0 -> 0xe3b5a0` binding.
- **Common:** queue-drain order, stable semantic target lifetime, multiple input
  sources in one frame, last coordinate writer, cancellation across suspension,
  scroll/drag arbitration and all modal restrictions.

Later validation must count **actual operation callbacks and state mutations**,
not just hit booleans or tooltip visibility. For each feature observe short tap,
hold, release after hold, motion, leaving target, second finger, cancel, focus
loss, controller input and a scene change. Use isolated saves and record inventory,
currency and selected-skill state before/after. Those checks are a future plan;
none were executed in this static-only round.

### Recommended sequence

1. Finish the remaining static contracts: action-result bytes/queue drain and
   source-aware cancellation; identify the portrait double operation and A's
   typed slot/action boundaries. Add no global gesture remapping to compensate
   for an unresolved game ABI.
2. Implement the one opt-in title policy with contact/owner generations, consumed
   tokens and original action forwarding, then wire **C only**. Its mutation and
   hover endpoints are best established and it has the smallest economic/save risk.
3. Add **B** using the same state machine and a portrait-specific long-action
   binding; prove short selection and original drag remain separate.
4. Add **A** in stages: equipped trinkets, backpack/storage, then purchase/sell
   and DLC supply contexts. Do not enable an unclassified scene just because it
   shares `e171c0` or a vtable method. Preserve explicit sale/drag workflows.
5. In a later authorized run, exercise native iOS touch and Mac original mouse/
   controller regression, bundled/external modes and all cancellation cases.
   Only then enable the option outside the experimental path.

All future game gates must check main Build ID, mapped bounds and original words
at each candidate site (and the required SDK identity if their ABI depends on it),
operate on the game thread, and fail closed on mismatch. Off/unsupported builds
must preserve original behavior. This audit deliberately provides **candidate
functions and call sites, not unvalidated patch instructions**.

## 8. Reproducible evidence locations

Previously existing material consulted:

- `docs/darkest-dungeon-mouse-input.md` (partial dispatcher contract and Mac handoff).
- `/Volumes/MacData/game/darkest-dungeon/mouse-ui-readonly-20261028/REPORT.md`,
  `index.json`, `callback-evidence.tsv`, and original-function listings.
- Prior HID/UI/auto-mode reports in the adjacent game investigation folders.
  Prior dynamic results are context only, not new acceptance evidence here.

This round's decoded listings and summaries are outside Git:
`/Volumes/MacData/game/darkest-dungeon/touch-interaction-audit-20261029/`.
`strings.txt` records the checked Build ID and file SHA; `vtables.txt` records
relocation-resolved type bindings; `fn-*.asm`, `functions.txt`, `actions.txt`,
`scene-functions.txt`, `shop.txt`, `supply.txt`, and `portrait-toggle.txt` contain
the read-only instruction evidence discussed above. Scratch Python helpers only
read the original module and cached static index; their original temporary-output
paths describe how the listings were produced. They were not run as game code.
No private game bytes or extracted executable were added to the repository.

## 9. Development-only update: opt-in iOS combat-skill policy

This section records the subsequent implementation request, at the same HEAD
`6dcf9868582388173f81f4f02385cd4cdb125b3e` on `main`. The pre-existing untracked
static report above is retained. **No compilation, module preparation, packaging,
unit tests, game launch, LLDB, device operation, commit or push was performed.**
Only source inspection, original-module decoding, editing and Git diff inspection
were used. All implementation claims below mean **source written, awaiting build
and runtime validation**, not acceptance.

### Actual implementation status

The labels A/B/C in the development request differ from those in the initial
static request; this table uses the development request's names.

| Development request | iOS | Mac | Controller | Delivery state |
| --- | --- | --- | --- | --- |
| A. Character-details combat skills: short focus, long toggle | Code added behind `DM_DD_TOUCH_POLICY=1` | Original behavior | Original behavior | Modified code; not compiled or run |
| B. Town right-side RosterElement: long press instead of double tap | Original behavior | Original behavior | Original behavior | Candidate entries found; action mapping/right-side owner whitelist still insufficient; not enabled |
| C. Identifiable trinkets: short focus only, no new long action | Original behavior in all item scenes | Original behavior | Original behavior | Item classifier and pre-pickup coverage insufficient; not enabled |
| Shared source/contact/cancel lifetime | Tagged game fingers | Tagged left-touch contacts only | No contact tagging from Npad | Code added; cancellation semantics enabled only after exact iOS title/gate validation |

This is a **partial implementation**. It does not advertise roster holds or safe
trinket short taps as completed, and it does not disable all inventory clicks to
appear to satisfy coverage. In particular, an iOS short tap can still buy/equip/
unequip a trinket under the game's original behavior in this delivery.

### Source files changed

| File | Change |
| --- | --- |
| `dm/host/front.h` | Source-tagged contact publication, explicit cancellation, snapshot and activation APIs |
| `dm/host/hle_touch.c` | Contact generations, raw movement cancellation, recognizer-qualified Press snapshot and opt-in Cancel; original touch sample/latch ABI retained |
| `dm/ios/Sources/DmGamepad.m` | Tag only game-owned touches as iOS; explicit TouchCancel/reset while preserving legacy handling when the policy is inactive |
| `dm/ios/Sources/front_ios.m` | Cancel synchronously on focus loss/background before an asynchronous view reset can leave a hold alive |
| `dm/host/front_mac.m` | Tag existing left down/drag/up touch publications; no second mouse system or timer |
| `dm/host/hle_dd_touch.c` (new) | Title/build/gate validation, game-thread ownership, combat-grid identity, one-consumption authorization, coordinate handoff and native callback forwarding |
| `dm/host/dm.h`, `dm/host/hle.c` | Observation IDs and a separate integer/void entry-filter gate contract; existing observations stay read-only |
| `dm/tools/patch_nso.py` | Restricted `FILTERS` entry-stub emitter; no filter for games/builds without a matching table |
| `dm/games/01008F1008DA6000/patches.py` | Four new observation sites and one combat-skill filter, restricted to the 1.3.0 main Build ID |
| `dm/games/settings.tsv` | One default-off, title-only experimental setting; no parallel settings store |

The Host and iOS source generators already include ordinary `hle_*.c` files;
`hle_dd_touch.c` deliberately has no `_mac` suffix. No generated project, binary,
shader, graphics source, original game file or save was changed.

### Additional static evidence closed this round

The original instruction stream was read again, without executing the rewriter:

- `0x73c9c8 -> 0x73bf90` returns the packed result retained by the shared button
  wrapper; the normal wrapper return preserves this value. At `0xe39118`, x20 is
  still the live `ShowSkillGrid` action wrapper constructed at `0xe39078..80`.
- `0x717370..0x717568` is the vector append/reallocation path used by the native
  controls. Its parameters are `(vector*, const std::function<void()>&)` in
  x0/x1. It clones a heap callable through vtable+0x10 or copies an inline one
  through +0x18. Thus a current wrapper can be cloned into the game's queue
  without storing a borrowed stack function between frames.
- `0x8b5dc8..0x8b5e1c` reads the action vector at `0x257e530`, walks entries in
  0x30-byte steps, and calls each function's vtable+0x30 at `0x8b5df0`. This closes
  one concrete native queue-drain location that was unresolved in the audit.
- `CharacterDisplay` vtable is `0x11946c0`. Its current hero is read at object
  +0x120. Opening stores state 1 at +0x2c0 (`0xe26c18`); closing begins at
  `0xe274c0`, fades out and stores state 2 (`0xe27528`). Destructor `0xe3d7d0`
  releases owned state. These yield concrete close/destruction invalidation
  boundaries, rather than guessing a generic CharacterDisplay toggle.
- The action wrapper `0xe39fe0` only reads its eligibility field and forwards
  the captured combat action at `0xe3a024`; no selected-skill vector mutation is
  performed before `0xe3b5a0`. Therefore, **for this verified skill binding**, an
  entry filter is early enough to prevent the state change. This conclusion is
  not generalized to trinket pickup or transaction callbacks.

### iOS skill flow in the written code

1. `DmGamepad` publishes existing normalized game fingers with source
   `DM_CONTACT_IOS`; virtual controller touches retain their separate routing.
2. `hle_touch.c` observes contact count, finger identity/generation, down position,
   current position and SDK gesture sampling. Moving more than 8 panel pixels,
   replacing a finger while contacts remain, or adding a second finger cancels
   the policy's contact. It does not change the game's ordinary Pan recognition.
3. Press qualification comes **only** from the existing GestureType Press after
   the existing 0.5 s recognizer threshold. A separate gesture-generation check
   prevents a fast replacement contact inheriting an earlier touch's Press time.
   UIKit/AppKit have no new hold timer.
4. Observation at `0xe39118` recognizes the current wrapper by exact vtable
   `0x11956b8`, its combat action by `0x1195228`, and the owner by CharacterDisplay
   vtable, hero and open state. It reads the original control's hover result.
   A rectangle alone, a shared renderer address or a generic skill icon does not
   qualify a target. Camping/Guild/battle bindings do not match the action type.
5. Short Tap's native callback may still be **queued**, but the filter at the
   first instruction of `0xe3b5a0` rejects it before the original prologue and
   vector changes. The queue is not cleared. The earlier verified wrapper has no
   selected-skill mutation, so this is not attempting to reverse an earlier
   mutation. Native hover, tooltip descriptor, hit testing, selection predicate
   and disabled rendering still run. Press sounds/decorations are not globally
   suppressed.
6. For one qualified Press on the same semantic target, the policy asks native
   helper `0x717370` to clone the **current original** Fvv wrapper into the native
   queue. The temporary function holder has 16-byte alignment and the recovered
   0x30-byte layout; its heap callable is copied immediately using the game's own
   clone method. It is not retained as a pointer to a control stack frame.
7. At actual Toggle execution, the entry filter checks an authorization token,
   source, generation, finger still down, Press phase, target hero/skill/owner,
   owner open/current-hero state and recent UI visitation. Exactly one matching
   call consumes the token; any duplicate native/forwarded callback is refused.
   It then enters the **unchanged original** Toggle, preserving class restrictions,
   selected-count limit, native return behavior, animation and cache updates.
8. Press release already becomes Complete rather than Tap. Independently, a
   released/cancelled contact has no valid operation authorization. Closing the
   panel or destruction invalidates the target before its storage is released;
   changing heroes, missing the original target or a UI visitation gap cancels
   the current generation. Reopening/rebuilding while the same contact is held
   does not authorize a different target.

The native action queue still executes on its original schedule. A finger released
or cancelled before that drain may cause the queued hold to be rejected rather
than executed late. No action is called from the UIKit thread or directly on a
hero's skill vector. Native predicate/limit failure consumes the single hold;
holding longer does not repeatedly retry a locked/full skill.

### Hover and coordinate handoff

At the frame observation, only a verified iOS policy running on its original game
thread may publish normalized-panel coordinates to `main+0x27e0890/894`, using the
same 1280x720 coordinate convention as existing touch input. After release, the
last qualified skill target may retain that cursor while it remains live/recent.
The adapter requires native mode=0 and auto-controller flag=0; it never writes
either field, forces `neverusecontroller`, edits tooltip flags or invokes a
Tooltip registration function directly. `0xe3959c` and the descriptor callback
`0xe3afd0` remain on their original paths.

This coordinate timing, packed hover bit and target-state assumptions are static
contracts, **not runtime acceptance**. Real iOS observation must still show the
cursor/tooltip survives all later focus/render phases.

Additional acceptance limits: Press timing belongs to the original contact, not
an independently timed semantic widget. The adapter rejects a target first seen
only after Press, but a contact beginning just outside an edge and entering within
the 8 px slop still needs a target-dwell check in the subsequent verification
round. The native queued callable does not carry a contact generation; its
authorization is checked against the current contact and semantic target at
execution. Queue ordering, rapid same-target replacement and controller takeover
must therefore be observed before claiming complete stale-action suppression.
Controller-owned mode deliberately passes the original action; an iOS tap during
the transition into that mode is not yet proven to obey the touch-only policy.
Close/destructor observations cover known owner lifetimes, but do not establish
that every in-place panel rebuild is covered. These are unverified boundaries,
not completed cancellation guarantees.

### Source isolation, cancellation and original behavior

`dm_touch_set` remains available with source UNKNOWN for scripts and old callers.
Mac's existing left `mouseDown -> mouseDragged`, and its drag/up, now tag the same
contact stream as MAC_LEFT. A down publishes a held point and only Up removes it;
`gesture_fill` can therefore reach Press without more MouseDragged events. Hover,
right and middle events do not publish a left contact. None of this enables the
unverified roster action. There is no new Mac click/hold dispatcher, and current
Mac mouse, HID and pointer settings retain their operation paths.

Only `TARGET_OS_IPHONE` activates the implementation. On Mac the new setting logs
that the roster mapping is unavailable and keeps original behavior. Npad/virtual
pad inputs are not tagged as iOS fingers; controller-owned mode passes the
original Toggle. Legacy UNKNOWN contacts also pass original behavior.

The new explicit cancellation is active only after exact title/build/gate checks.
When inactive, the touch recognizer's old Tap/Press/Pan/history rules are retained.
When active, cancel clears pending gesture contacts and emits Cancel, then Idle,
without a release Tap or stale double-tap timestamp. Focus/background cancels
synchronously; a queued action independently re-reads the snapshot before state
mutation. On affected contacts, second fingers, movement, leaving the original
skill, changing the hero/page and close/destruction also invalidate authorization.
No timer or UIKit object pointer is retained by the game adapter.

### Gate safety and rollback

| Original main offset | Original word | Purpose |
| --- | --- | --- |
| `0xe39118` | `f9400288` | Observe the original skill control return and live action wrapper |
| `0x8b5dd0` | `f90017f5` | Frame boundary before native action-queue drain |
| `0xe274c0` | `d10143ff` | Cancel at CharacterDisplay close start |
| `0xe3d7d0` | `a9be7bfd` | Cancel before CharacterDisplay destructor |
| `0xe3b5a0` | `d10203ff` | Integer/void entry filter on the actual combat Toggle |

The rewriter asserts the exact original words and valid sites. Runtime checks
require the compiled Title ID, exact main/SDK Build IDs, sufficient module extent,
all four observations, the filter's original offset and unchanged neighbouring
instructions around the control, Toggle, native queue helper and frame boundary.
The main/SDK IDs remain those in the user's request.

`FILTERS` is separate from `OBS`: an allow decision restores original x0 and
arguments, stack/LR, then runs the original prologue; denial returns integer zero
before the prologue. Missing Host filter defaults to allow. This mechanism is
restricted to an ordinary integer/void function entry with a relocatable stack
prologue, not an arbitrary mid-function branch or floating-point return. Existing
observation callbacks remain read-only; no generic GUI result is changed.
The entry-stub code is **new and uncompiled/unexecuted**, and must be independently
validated before distributing a prepared image.

`DM_DD_TOUCH_POLICY=1` is default off and is offered through the existing shared
`settings.tsv` mechanism only for this title. The setting note explicitly states
that only iOS character combat-skill holds have source implementation. Turning it
off/restarting restores original action authorization. Missing prepared gates or
runtime signature/Build-ID mismatch refuses activation and passes original calls.
An offline assertion mismatch aborts preparation; it does not silently package a
patch at a different instruction. Old prepared modules have no gates and therefore
keep their old behavior; new prepared modules require a new Host that understands
`filter` gate rows. No package was rebuilt this round.

### Roster/trinket work deliberately not enabled

Further source/decoded-instruction inspection confirms the town roster's two
operators at `0xc61890` / `0xc615b0` have different owner-supplied behavior, not a
single universal open-details entry. The former invokes a predicate and callback
at owner +0x140/+0xb0; the latter updates selection and forwards a roster callback.
The Host's IsDoubleTap bit and game internal event 3/4 translation are known, but
the complete byte-to-final-action mapping **and** proof that an owner is only the
right-side town roster are still missing. Reused town/embark lists cannot safely
be distinguished by `RosterElement` RTTI alone. No roster gate or fake double Tap
was added, and the dungeon/controller CharacterDisplay toggle is not substituted.

For trinkets, shared slot/interface pickup and commit methods remain shared with
ordinary items. The audit has supply, equipment, realm-storage and backpack
render paths, but not a stable actual-item classifier plus all pre-pickup action
edges. Suppressing only a final buy/equip callback could leave a pickup/drag
context or transaction already changed. Accordingly **no trinket slot is claimed
supported yet**, including equipped slots; all retain original behavior. No new
trinket long action, fallback sale or invented button was added. This preserves
normal items and independent shop buttons, but does not yet prevent trinket mis-taps.

### Checks performed, and minimum future acceptance

Performed now: manual source/ABI inspection, original-instruction decoding,
source-diff review and `git diff --check`. Not performed: syntax compilation,
rewriter execution, unit tests, Mac/iOS builds, packaging or any runtime/device
check. The original 0.5 s / 8 px recognizer rules were reused, not revalidated.
There is no new binary to install from this round.

The next authorized verification round must first validate generated filter stub
allow/deny register/stack/LR behavior, original-word rejection and off/mismatch
fallback, then compile both targets and perform focused synthetic contact tests.
On an isolated iOS save, inspect short taps, one long enable/disable, no release
inverse, locked/full selection, finger movement/leave, rapid finger replacement,
multiple fingers, changing heroes, page close/rebuild, suspension/focus loss,
controller takeover and cancellation between enqueue and drain. Count actual
Toggle calls and selected-list changes alongside cursor and tooltip visibility.
Then verify Mac clicks, controller actions, battle skill selection, Guild/camping
screens, normal items and existing render/mouse functions with the option off/on.
Bundled and external-container builds use the same prepared gate and live UI
bindings; both modes remain **unverified** here.

Do not enable roster or trinket policy simply after these skill checks pass. Their
specific static gaps above must be closed separately, followed by their own
isolated input/action checks. All code remains uncommitted in this working tree.

## 10. Verification and delivery round (2026-10-29)

Section 9 recorded the source-only state and explicitly claimed no build or test.
This section supersedes those status statements: the same working tree was built,
tested and packaged, while the roster and trinket decisions are unchanged.

Repository state: `main` at `6dcf9868582388173f81f4f02385cd4cdb125b3e`, no branch,
commit or push. The eleven modified tracked files, `dm/host/hle_dd_touch.c`,
`dm/tools/tests/test_entry_filters.py` and this document remain uncommitted. No
original NSO/NSP/RomFS/DLC/shader/save was modified. The previous delivery folder
(`deliver-20261029/`) was left untouched.

### 10.1 Artifacts built this round

| Artifact | Path | Size | SHA-256 |
| --- | --- | --- | --- |
| IPA (unsigned) | `/Volumes/MacData/game/darkest-dungeon/deliver-touchpolicy-verify-20261029/DarkestDungeon-touchpolicy-verify.ipa` | 1,688,267,809 bytes (1.6 GB) | `23bff8d3bcafee2f156e0012e42637dece994ce99a8b73446ef28d79c9ffc6fe` |
| Mac App (directory, game data bundled) | `/Volumes/MacData/game/darkest-dungeon/deliver-touchpolicy-verify-20261029/Darkest Dungeon 1.3.0-touchpolicy-verify.app` | 3.3 GB (`du`), 11,434 files | tree hash `a72e7ecc140546ef9609d12aad347043681be38f0b94408526af35e5deeb2538` |
| Mac host binary | `.../Contents/MacOS/dmhost` | 2,460,120 bytes | `9fd43a24d68a19d1a84afa12cf45340734324482354cc4f571558c6116870423` |
| Mac launcher | `.../Contents/MacOS/launch` | 900,696 bytes | `bcfa1db5c44bb469447a9f0cf534ad2685b860148ee65b6c2245660979816308` |

The App tree hash is the SHA-256 of `find . -type f -print0 | sort -z | xargs -0
shasum -a 256 | shasum -a 256`, i.e. each file's relative path and hash, not a
ZIP timestamp. Build logs are beside the artifacts (`ipa_build.log`,
`mac_build.log`). The build was incremental: extracted files, the prepared
modules, GL shaders and unchanged object files from the same working tree were
reused (`rewrite ... reused (inputs unchanged)`, 55 iOS files compiled, Mac host
`make` up to date); every modified source mtime precedes the cached build. No
artifact was signed, installed or launched.

The IPA contains `Payload/DmIOS.app/DmIOS` with the iOS adapter string
`[dm] DD touch policy: %s (iOS combat skills only; roster/trinkets unchanged)`;
the Mac `dmhost` contains the Mac refusal string
`[dm] DD touch policy: Mac roster action is not yet verified; original behavior retained`.
The iOS app embeds the prepared modules in `DmIOS`; the exact 17-word filter stub
taken from the Mac `main.patched.bin` occurs exactly once in that executable.
Both packages carry `main.gates.tsv` with the observation rows 22/24/25/26/27 and
the `filter 1 0xe3b5a0` row, and a `launcher.json` whose `DM_DD_TOUCH_POLICY`
toggle defaults to `0` with the note quoted above.

### 10.2 Filter and observation validation

The rewriter asserted the exact original words of every new site offline. All
matched in the 1.3.0 `main` NSO (`ff2bf22565188d11ea0981ee0e2b53ce`, text
`0xe6afb0`):

`0xe39118 f9400288`, `0xe3910c 913783e4`, `0xe39114 97e40d9b`,
`0xe3911c aa1403e0`, `0xe3b5a0 d10203ff`, `0xe3b5a4 6d0323e9`,
`0xe39fe0 d10083ff`, `0xe39fe4 a9017bfd`, `0x717370 d10203ff`,
`0x717374 a9037bfd`, `0x8b5dd4 a9405113`, `0x8b5dac 1e204120`,
`0xe274c0 d10143ff`, `0xe3d7d0 a9be7bfd`, `0x8b5dc0 1e204120`.

The prepared `main.patched.bin` was decoded, not just inspected in source:

- The site `0xe3b5a0` holds a `b` whose target is the stub at `-0x1fcd5f8`; the stub is:
  `stp x29,x30,[sp,#-0x20]!` / `str x0,[sp,#0x10]` / `mrs x30,tpidrro_el0` /
  key-page load of the gate / `blr x30`; allow: `ldr x0,[sp,#0x10]`,
  `ldp x29,x30,[sp],#0x20`, the original `sub sp,sp,#0x80`, then
  `b 0xe3b5a4`; deny: `ldp x29,x30,[sp],#0x20`, `mov x0,#0`, `ret`.
- Allow therefore restores the original x0 (argument 1), x29, x30 and sp before
  the original prologue; x1–x17 and x19–x28 are preserved by `entry.S` (`_dm_gate` saves and
  reloads them, and the filter writes only `regs[0]`; x18 is the Apple platform
  register and is deliberately left alone). Deny returns integer zero
  to the caller before any original instruction, with sp/x29/x30 restored. The
  stub uses a 32-byte 16-byte-aligned frame, never x18, and has no PC-relative
  branch except the key-page `adrp`.
- The old observation at `0x8b5dc0` still jumps to a stub that executes the
  original `fmov s0,s9` and returns to `0x8b5dc4`; the new frame boundary at
  `0x8b5dac` does the same for its own `fmov` and returns to `0x8b5db0`.

Static ABI confirmation of the skill target:

- `0x1195228` is the vtable of
  `std::__1::__function::__func<UI::Panel::CharacterDisplay::ShowCombatSkillGrid(...)::$_5, bool (Hero*, unsigned int)>`;
  its entry at `+0x30` is `0xe3b5a0`.
- `0x11956b8` is the vtable of
  `...CharacterDisplay::ShowSkillGrid(...)::$_0, void()`; its operator at
  `+0x30` is `0xe39fe0`. The wrapper is allocated at `0xe39070` and constructed
  at `0xe39078..0xe390f8`: vtable at +0, action at +0x40, hero at +0x50, skill
  at +0x58. `0xe39fe0` calls the action's `+0x30` with x0 = action, x1 = &hero,
  x2 = &skill, exactly the filter's `r[0]/r[1]/r[2]`.
- The queue helper `0x717370` treats a function object as 0x30 bytes with the
  callable pointer at +0x20; it clones a heap callable through vtable `+0x10`
  before returning, so the temporary 48-byte holder in `hle_dd_touch.c` is
  copied into the queue and does not own a stack frame. The drain at
  `0x8b5de0..0x8b5df0` calls each callable's vtable `+0x30`, i.e. the wrapper
  0xe39fe0, which reaches the filtered Toggle.

### 10.3 Tests and compatibility comparisons actually run

| Command | Result |
| --- | --- |
| `python3 -m unittest tests.test_entry_filters` (dm/tools, venv with capstone) | 9 tests, OK |
| `python3 -m unittest tests.test_patches tests.test_spin_waits` | 10 tests, OK |
| `make -C dm/host/tests GAME=01008F1008DA6000 run` | exit 0; all host tests passed |
| `build/t_touch` | 13 checks, 0 failed |
| `build/t_gesture` | 43 checks, 0 failed |
| ad-hoc `t_contact` linked against `hle_touch.c` | 14 checks, 0 failed |

The ad-hoc contact test is in
`/Volumes/MacData/code/.worktmp/darkest-dungeon-1.3.0/tmp/touchpolicy-verify-20261029/`
and is not part of the repository. It verified: source tag and normalized pixel
position; generation on a fresh contact; DOWN → HOLDING → PRESS after 0.6 s; an
unchanged sample keeps PRESS; a >8 px move becomes CANCELLED with the same
generation; release becomes RELEASED; a new contact advances the generation;
explicit cancel yields CANCELLED with count 0 and reaches the recognizer as
gesture Cancel (type 2, not Tap).

No-FILTERS rewriter compatibility was compared against the HEAD rewriter
(`git show HEAD:dm/tools/patch_nso.py`) on three modules that have no FILTERS
row:

| Module | `.patched.bin` | gates/fixups/obs/sites/cuts |
| --- | --- | --- |
| Darkest Dungeon 1.3.0 `sdk` (`b33804825108340e4cad9d080a636a3f`) | byte-identical | identical |
| Rhythm Heaven Groove `main` | byte-identical | identical |
| Mario Kart 8 Deluxe `main` | byte-identical | identical |

Only `build_src.sha256` differed, in its first line (`patch_nso.py`'s own hash);
every other line was identical. The prepared `sdk.patched.bin` already in the
work folder is also byte-identical to a fresh current-rewriter run. The Darkest
Dungeon `main` work artifact records `patch_nso.py` hash
`69d6fb5c6acd195dbef462ac7977ae74c00ff7f56b74a17c03dc5e8c2f5d76c0`, i.e. this
working tree's rewriter, and its gate table is the one packaged above.

### 10.4 Roster long-press (B): still not closable, kept unchanged

The 0.5 s hold was **not** implemented. The new read-only decode confirms the
earlier negative closure:

- `0xc60080` calls `0x73b6d0` with four `std::function` objects (stack
  +0xa0/+0x70/+0x40/+0x10). `0x73b6d0` asks `0x738eb0` for a mask and pushes the
  matching callbacks through `0x717370` on bits 0, 8, 0x10, 0x18 and 0x20.
  `0x738eb0`'s only calls are hit tests, a held-contact membership query, and
  layout calls; it has no `cntvct`/`cntpct` read and consumes the matched
  contact records (`strb wzr` / `str xzr`). The mask describes pointer-event
  state, not a click count.
- `0xc61890` and `0xc615b0` are the `void()` lambdas of
  `TownUI::Panel::RosterElement::PreChildrenShowInternal` (`0x117cd40`,
  `0x117cdc0`). The first forwards to owner +0x140 predicate and +0xb0 callable;
  the second sets `[element+0x231]` and tweens `element+0x410` (selection
  highlight) and calls `0xcb59a0` with a roster callback.
- The owner RTTI proves `RosterElement`, not that a particular instance is only
  the town's right-side portrait. The same class is reused by roster/embark
  lists, and no instance-level discriminator was found.

There is therefore no original "double click" operation to replay, and no safe
right-side-only owner gate. No roster gate, filter, timer or synthesized double
Tap was added; the Mac left button, short tap selection, drag and multi-touch
remain the game's own. Trinkets (C) remain unchanged for the same reason as
section 9: no stable actual-item classifier and no proof that suppressing a
final callback leaves no pickup/drag/transaction already changed.

### 10.5 Status, honestly separated

| Item | Compiled into the artifacts | Unit/static evidence | Runtime in game |
| --- | --- | --- | --- |
| `FILTERS` stub allow/deny, x0/SP/LR/FP ABI | yes, Mac and iOS hosts; prepared `main` | 9 unit tests + decoded stub in the packaged module | not executed |
| Build-ID, title, gate and original-word checks | yes | rewriter asserts; `dd_init` checks; all words matched | not executed |
| Default-off fallback | yes | toggle default 0; `dd_init` returns; filter allows when inactive | not toggled in a running game |
| Original observation 22 | yes | decoded stub; old word/site unchanged | not executed |
| iOS contact tagging, Press, movement/second-finger cancel, explicit cancel | yes | `t_gesture` 43 checks, ad-hoc 14 checks | not on a device |
| Combat-skill hold enqueue and one-shot filter | yes | static ABI/call chain above | **not verified in game**; no claim that a hold toggles |
| Mac left-button path | yes, tagged MAC_LEFT | source inspection; pointer code unchanged | not executed |
| Town roster long press | no (not implemented) | static negative closure | original behavior |
| Trinket short-tap policy | no (not implemented) | static gaps | original behavior |

Known boundaries not claimed as solved: the queued wrapper is cloned safely but
still carries raw panel/hero pointers, so an in-place panel rebuild not covered
by the close/destructor gates is a lifetime risk (analysed again in 11.5); and a
short iOS tap to the Toggle is denied by design (selection unchanged), which is
the intended "short focus, long toggle" behavior but has not been observed.

**Correction (2026-10-29, second round).** Two statements written in the first
version of this section were wrong and are superseded by section 11: `g_contact`
was never updated outside `g_tl` — `gesture_sample` is a `static` function whose
only caller is `gesture_fill`, which takes that lock before it runs (11.1) — and
the frame handoff no longer publishes coordinates for every single iOS finger: it
now requires a qualified, still-live CharacterDisplay skill target (11.2). The
first-thread ownership gate (`dd_owner`) also no longer exists; a mutex serialises
the policy state (11.3).

### 10.6 Manual acceptance still required

Use an isolated save copy; do not judge this round as game acceptance.

1. iOS, setting off: tap a combat skill; it behaves exactly as before; the
   log has no `DD touch policy` enabled line.
2. iOS, setting on: log says `DD touch policy: enabled, not runtime-validated`
   (or `REFUSED` if the module/gates do not match); a short tap on a combat
   skill must not change the selection; a 0.5 s hold must call the original
   toggle once; release must not toggle again.
3. While holding: move >8 px, leave the icon, add a second finger, change hero,
   close/reopen the panel, suspend/resume, or take over with a controller; no
   late toggle and no crash.
4. Battle, dungeon portraits, camping/guild screens, normal items and the
   controller must behave as before with the setting on and off.
5. Mac: with the setting on, the log must show the Mac refusal and every click
   must be unchanged; with it off, no new log line.
6. Town right-side roster: short tap, drag and multi-touch must remain the
   original behavior; this round adds no hold there.

Count actual Toggle calls and selected-list changes, not only cursor/tooltip
visibility. A black screen, a crash, a doubled toggle or a toggle after release
is a failure, not a partial success.

## 11. Safety close-out round (2026-10-29, second build)

This round addressed the blocking findings of section 10. It corrects one wrong
claim, narrows one behaviour, replaces one assumption, and rebuilds both targets
from the current sources. Roster and trinket policies remain off; no original
NSP/NSO/RomFS/DLC/shader/save was modified; the tree is still `main` at
`6dcf9868582388173f81f4f02385cd4cdb125b3e` with no branch, commit or push.

### 11.1 The reported `g_contact` race did not exist (correction)

Section 10.5 said `gesture_sample` updated `g_contact` on the game thread
"without that lock". That was wrong. The call chain is:

- `gesture_sample` is declared `static` (`dm/host/hle_touch.c:134`) and has
  exactly one caller in the tree: `hle_touch.c:207`, inside `gesture_fill`.
- `gesture_fill` takes `g_tl` at `hle_touch.c:206` and releases it at
  `hle_touch.c:210`, so the body that writes `g_contact` (`:143`, `:194`–`:198`)
  runs under the mutex.
- The front-end writer `touch_publish` takes the same mutex at `:24`; every
  reader takes it (`dm_touch_contact_snapshot` `:61`, `dm_touch_policy_activate`
  `:62`, `dm_touch_policy_is_active` `:63`). `g_gf`, `g_f`, `g_tsamp` and
  `g_tlast_ns` are only touched in those same locked regions.
- `grep` confirms no second definition or caller (`gesture_read` is likewise
  `static`, called only from `gesture_sample`).

Reproducible evidence: `dm/host/tests/t_touch_threads.c` (new) runs a publisher
(`dm_touch_set_from`, mixed iOS/Mac sources), a canceller
(`dm_touch_cancel_from`, `dm_touch_policy_activate`) and a reader
(`gesture_fill`, `dm_touch_contact_snapshot`) concurrently for 200,000
publications. Under ThreadSanitizer it reports no data race, and the plain build
checks the sampled values stay in range:

```
$ make -C dm/host/tests GAME=01008F1008DA6000 tsan
build/t_touch_threads_tsan
ok   reader: every sampled phase is a documented one
ok   reader: every sampled count is 0..16
ok   reader: gesture count is 0..16
ok   reader: generation never goes backwards
ok   publisher and reader completed
== 5 checks, 0 failed ==
```

Because the lock was already correct, `hle_touch.c` was **not** changed for this:
no second lock was added and no lock was removed.

### 11.2 Pointer handoff narrowed to a qualified skill target

`dd_frame_tick` used to publish `main+0x27e0890/894` for **every** single-finger
iOS contact whenever the game owned the pointer (`mode == 0`, auto-controller
flag clear) — that is, in town, menus, battle and every other screen, not only
CharacterDisplay. The game's own touch path already writes the same pair
(`0x74c09c/0x74c0a8` and `0x74c1fc/0x74c228`, decoded in
`docs/darkest-dungeon-mouse-input.md`), so the adapter's
write was an extra, screen-wide cursor/tooltip handoff.

It now writes only when the game itself has qualified the current contact on a
live CharacterDisplay skill control: `dd_skill.panel` set by the observation at
`0xe39118`, same contact generation, `dd_live` true, and the target observed in
the previous frame. In every other case the pointer is left exactly where the
game's own touch code put it, so no guessed screen/rect classifier decides what
another interface may do.

Consequence, recorded as unverified: the first hover of a contact now comes from
the game's own touch-to-pointer code, and the adapter only sustains a target the
game has already reported. This has not been observed in a running game.

### 11.3 Thread identity replaced by one mutex

`dd_owner` (the first thread to reach any gate) is gone, and with it the failure
mode where an unexpected first caller silently disabled the policy. Every gate
now runs its decision under `dd_mu`:

- lock order is always `dd_mu` → `g_tl` (the contact snapshot); no path takes
  `g_tl` first, and `touch_publish` never calls into the adapter, so the order
  cannot invert;
- the guest call (`vector::push_back` at `0x717370`) is made **after** the
  unlock, so no game code runs with `dd_mu` held;
- decisions still require the live target identity, so a gate reached from an
  unexpected guest thread cannot authorise anything on its own.

### 11.4 Policy off, other games and old prepared modules (re-run)

The rewriter was unchanged this round; the comparison was repeated anyway against
the `HEAD` rewriter (`git show HEAD:dm/tools/patch_nso.py`) on modules with no
`FILTERS` row:

| Module | `.patched.bin` | gates / obs / cuts / fixups / sites |
| --- | --- | --- |
| Darkest Dungeon 1.3.0 `sdk` | byte-identical | identical |
| Rhythm Heaven Groove `main` | byte-identical | identical |
| Mario Kart 8 Deluxe `main` | byte-identical | identical |

`build_src.sha256` again differs only in its first line (the rewriter's own
hash). A fresh rewrite of the Darkest Dungeon 1.3.0 `main` is byte-identical to
the prepared module already in the work folder (`main.patched.bin`
`e88d948e9f3248d0de2db1c6ad21ea95e3e40d4ab3e45256e434c6dd0c91d08d`), and
`sdk.patched.bin` matches the fresh current-rewriter run. The packaged module is
that same file, so the gate table and the filter stub in both new packages are
unchanged from the previous round.

With the policy off (the default, `0`), `dd_init` returns before
`dm_touch_policy_activate`. The filter and observation callbacks stay installed,
but `dd_ready()` is false, so the filter returns 1 without touching any register
or state and every call keeps its original arguments and return. The Mac host refuses
outright (`#if !TARGET_OS_IPHONE` logs and returns), so Mac behaviour is the
game's own.

### 11.5 Queued wrapper lifetime (reviewed, no new ABI)

The hold enqueues the game's live `std::function` wrapper through the native
`push_back`, which clones the callable through its vtable `+0x10` into the
vector's own heap storage; only that clone is kept, no stack pointer. At the
game's drain the clone calls the wrapper `0xe39fe0`, which calls the action's
`+0x30` — the filtered Toggle — with `(action, &hero, &skill)`.

The filter denies before dereferencing any game object while
`dd_skill.authorized` is clear, and authorization is cleared by: the close
observation `0xe274c0`, the destructor observation `0xe3d7d0`, a new contact
generation, a different hero/skill/panel, or a frame without a fresh
observation. Residual, unchanged and not claimed solved: an in-place panel
rebuild that reaches neither close nor destructor and keeps the same generation
could leave `dd_live` reading storage the game has reused. Closing that needs an
ABI that is not established, so no patch was written for it.

### 11.6 Tests run this round

| Command | Result |
| --- | --- |
| `python3 -m unittest tests.test_entry_filters tests.test_patches tests.test_spin_waits` (dm/tools, venv with capstone) | 19 tests, OK |
| `make -C dm/host/tests GAME=01008F1008DA6000 run` | exit 0; `t_touch` 13/13, `t_gesture` 43/43, new `t_touch_threads` 5/5, all other suites pass |
| `make -C dm/host/tests GAME=01008F1008DA6000 tsan` | `t_audio_spsc` and `t_touch_threads` pass under ThreadSanitizer; no race reported |
| ad-hoc `t_contact` against the current `hle_touch.c` | 14 checks, 0 failed |
| no-`FILTERS` rewriter comparison (3 modules) | byte-identical, see 11.4 |
| prepared-module comparison | `main` and `sdk` byte-identical to a fresh current run |

Full host-test output: `/Volumes/MacData/code/.worktmp/darkest-dungeon-1.3.0/tmp/touchpolicy-verify-20261029/host_tests_run.log`.
The ad-hoc contact test and the compatibility runs live beside it.

### 11.7 Artifacts of this round (new directory, old ones untouched)

| Artifact | Size | SHA-256 |
| --- | --- | --- |
| `deliver-touchpolicy-safety-20261029/DarkestDungeon-touchpolicy-safety.ipa` | 1,688,267,796 bytes | `70ef894f2fdb621c9d87996f9183201a29d430198cd9ea3658d4d69e436fe28d` |
| `.../Darkest Dungeon 1.3.0-touchpolicy-safety.app` (tree) | 3.3 GB, 11,434 files | `1f70f7f8c12e3cb0dc53739e0c03ae0c18dfa5ac84e169b40c15faa82ed6f1f6` |
| `...app/Contents/MacOS/dmhost` | 2,460,120 bytes | `b37b10bf59424349465a594d9a96e17db7907c9aa7ff5f4f531df256cf80c8d8` |
| `...app/Contents/MacOS/launch` | 900,696 bytes | `bcfa1db5c44bb469447a9f0cf534ad2685b860148ee65b6c2245660979816308` |
| `Payload/DmIOS.app/DmIOS` inside the new IPA | — | `611841b151e2e09e1daf602fb7129c70eb277d4d67207531aeaef650ff223ba8` |
| same file in the previous IPA (unchanged package) | — | `4a54ea0b900e8fb05f7fa408dae0af33940751fab6e0c62c5ddbc748a8c8f34c` |

Absolute paths (all on the game volume, never in the repository and never in the
home folder):

- `/Volumes/MacData/game/darkest-dungeon/deliver-touchpolicy-safety-20261029/DarkestDungeon-touchpolicy-safety.ipa`
- `/Volumes/MacData/game/darkest-dungeon/deliver-touchpolicy-safety-20261029/Darkest Dungeon 1.3.0-touchpolicy-safety.app`

Previous deliverables, verified unchanged by hash after this round:
`deliver-touchpolicy-verify-20261029/DarkestDungeon-touchpolicy-verify.ipa`
`23bff8d3…c6fe` and `deliver-20261029/DarkestDungeon-touchpolicy.ipa`
`e638f3c7…1084`.

Build commands (run from the repository root):

```
python3 scripts/build_ipa_from_nsp.py /Volumes/MacData/game/darkest-dungeon \
  -k /Volumes/MacData/game/darkest-dungeon/prod.keys -p v393216 \
  -o /Volumes/MacData/game/darkest-dungeon/deliver-touchpolicy-safety-20261029/DarkestDungeon-touchpolicy-safety.ipa

python3 scripts/build_ipa_from_nsp.py /Volumes/MacData/game/darkest-dungeon \
  -k /Volumes/MacData/game/darkest-dungeon/prod.keys -p v393216 \
  --mac-app "/Volumes/MacData/game/darkest-dungeon/deliver-touchpolicy-safety-20261029/Darkest Dungeon 1.3.0-touchpolicy-safety.app"
```

Logs: `.../deliver-touchpolicy-safety-20261029/ipa_build.log`,
`.../mac_build.log`, the iOS `xcodebuild` log at
`/Volumes/MacData/game/darkest-dungeon/01008F1008DA6000_build/ipa/build/ios/pkg/build.log`
and the Mac compiler output at `.../01008F1008DA6000_build/logs/mac_host_build.log`.

Evidence that the current sources were compiled, not inferred from mtimes:

- the stale object `host__hle_dd_touch.o` was deleted before the build, and the
  new `xcodebuild` log contains
  `CompileC …/host__hle_dd_touch.o …/dm/ios/Gen/src/host__hle_dd_touch.c`;
- `dm/ios/Gen/src/host__hle_dd_touch.c` and `host__hle_touch.c` are symlinks to
  `dm/host/hle_dd_touch.c` and `dm/host/hle_touch.c` and `cmp` equal to them;
- the written binary differs where the change is: in the new `Payload/DmIOS.app/DmIOS`,
  `_dd_frame_tick` calls `_pthread_mutex_lock` (`0x100095ebc`) and `_dd_live`; in
  the previous one it called neither. `otool -tV -p _dd_frame_tick` on both.

On the Mac build the four gate functions compile to a single `pthread_once`
plus the refusal log: `dd_valid` is only ever set in the iOS branch, so the
compiler proves it stays 0 and drops the rest. Mac behaviour is therefore the
game's own, and the `dmhost` hash changed only because the shared sources were
recompiled.

Both packages carry `main.gates.tsv` rows `obs 22/24/25/26/27` and
`filter 1 0xe3b5a0`, and a `launcher.json` `DM_DD_TOUCH_POLICY` toggle with
`"default": "0"` and the unchanged note that only iOS combat skills are
implemented. Nothing was signed, installed or launched.

### 11.8 Manual acceptance still required

The section 10.6 list still applies. This round adds two checks:

7. iOS, policy on, any screen other than the combat-skill grid (town, menus,
   battle, inventory): moving and holding a finger must leave pointer/tooltip
   behaviour exactly as with the policy off — the adapter no longer writes the
   pointer there.
8. iOS, policy on, combat skill grid: open the grid, hover and hold; then move
   off an icon and back. Confirm the target is acquired again by the game's own
   hover, that a short tap does not change the selection, and that a 0.5 s hold
   toggles once with no toggle after release.

A black screen, a crash, a doubled toggle or a toggle after release is a failure,
not a partial success.

## 12. Long press: root cause, the original eligibility path, and this round's build (2026-10-29, fourth)

The third build in this section is **withdrawn**. Its replay called the skill
action directly (`0xe3b5a0`) and so never ran the game's own wrapper
(`0xe39fe0`) whose first instruction reads the `CharacterDisplay` eligibility
byte at `+0x12d`. That violates the stated requirement that the original
Eligibility/lock checks decide, whatever the outcome for the hold. This round
runs the confirmed original wrapper instead, holds an owned copy of the action
class object the game itself used, re-checks the target at the moment of the
call, and adds policy tests for eligibility true/false, withdrawn/restored, a
locked skill, the selection limit, panel closed and contact cancelled. Roster and
trinkets remain untouched; no original NSP/NSO/RomFS/DLC/shader/save was
modified; `main` at `6dcf9868582388173f81f4f02385cd4cdb125b3e`, no branch, commit
or push.

The correction confirmed as right in the previous round is kept: the value the
`0xe39118` observation returns in `r[0]` is a 48-bit object pointer, not a
"hovered" bit, and is still tested as `r[0] & 1` exactly as before (12.1).

### 12.1 Why the third build's hold did nothing

`dd_skill_after` armed the hold only when the observation at `0xe39118`
returned an odd `r[0]`:

```c
if (!(r[0] & 1)) { ... return; }        // "hovered"
```

`r[0]` is the return value of the call at `0xe39114` (`bl 0x73c780`). Decoded
in `main` (`ff2bf225…`, text `0xe6afb0`):

- `0x73c780` ends with `and x0, x19, #0xffffffffffff` (`0x73caac`), a 48-bit
  masked object pointer;
- `x19` is the return of `0x73bf90` (`0x73c9c8 bl`, `0x73c9cc mov x19,x0`), whose
  epilogue is `mov x0, x22` (`0x73c558`) — an object it has been filling (it
  writes the per-skill name/description at `+0x1fc` / `+0x27c`, e.g. `0x73c004`).

That value is 16-byte aligned, so `r[0] & 1` was **always 0**: the target was
never armed, the `0.5 s` press never replayed anything, and the game's own
enqueue at `0x717370` never ran from the adapter either. The hover the user sees
comes from the game's own touch-to-pointer path (`0x74c09c/0x74c0a8`,
`0x74c1fc/0x74c228`).

Two further defects of that build are also gone: the capture could only be made
inside a `0xe39118` observation that happened to be `PRESS` in the same frame
(a timing the adapter never controlled), and `dd_frame_tick` set
`dd_blocked_generation` on *any* stale frame, which permanently blocked the
whole contact after one missed observation.

### 12.2 The blocking defect: the replay bypassed the wrapper

The third build's press called

```c
((void (*)(uintptr_t, uintptr_t *, uint32_t *))(dd_base + DD_TOGGLE))(copy, &hero, &skill);
```

directly. It checked the action's vtable, owner, the panel's vtable, hero and
state, but the wrapper's own check — `ldrb w8,[ [this+0x10] + 0x12d ]`, return
unless 1 — never ran for the replay. A skill that had become ineligible between
the click and the press would still have been toggled, which is exactly what the
requirement forbids, and the build let the adapter's own guesses stand in for the
game's qualification. No such call exists in the tree now.

### 12.3 The replay now runs the game's own wrapper

The press builds the wrapper object and calls it:

```c
dd_wobj w; memset(&w, 0, sizeof w);
w.vt = dd_base + DD_WRAPPER_VT; w.owner = panel; w.action = copy; w.hero = hero; w.skill = skill;
((void (*)(void *))(dd_base + DD_WRAPPER))(&w);        // 0xe39fe0
```

Decoded facts this rests on (all from the same `main`, build
`ff2bf22565188d11ea0981ee0e2b53ce`; the queue drain and the object layout were
already recorded in 10.2, and are repeated here because the replay now depends on
them):

| Fact | Evidence in `main` |
| --- | --- |
| The game's click is this wrapper's `operator()` | vtable `0x11956b8` `+0x30` = `0xe39fe0`; the frame's action-queue drain at `0x8b5dd0` iterates 0x30-byte entries, loads `x0 = [entry+0x20]`, `x8 = [x0]`, `x8 = [x8,#0x30]`, `blr x8` (`0x8b5de0…0x8b5df0`) |
| Eligibility is read there, live | `0xe39fec ldr x8,[x0,#0x10]`; `0xe39ff0 ldrb w8,[x8,#0x12d]`; `0xe39ff4 cmp w8,#1`; `0xe39ff8 b.ne 0xe3a028` (return, no call) |
| Arguments are the callable's own fields | `0xe39ffc ldr x8,[x0,#0x50]` → `[sp,#8]` (hero); `0xe3a004 ldr w9,[x0,#0x58]` and `0xe3a00c str w9,[sp,#4]` (skill); `0xe3a008 ldr x0,[x0,#0x40]` (action); `0xe3a018 add x1,sp,#8`; `0xe3a01c add x2,sp,#4`; `0xe3a020 ldr x8,[x8,#0x30]`; `0xe3a024 blr x8` |
| A null action aborts instead of being called | `0xe3a010 cbz x0,0xe3a034` → `bl 0x6ea730` (the C++ call-through-empty-object path); the adapter never passes one |
| The object layout is the game's own | copy constructor `0xe39e70`: `mov w0,#0x60; bl 0xe69a80`, vtable `0x11956b8` at `+0`, owner (`[src+0x10]`) at `+0x10`, action at `+0x40`, hero at `+0x50`, skill at `+0x58`; move constructor `0xe39f10` writes the same fields |
| The action's clone and release are its own slots | copy `+0x10` = `0xe3b520` (`mov w0,#0x10`; vtable `0x1195228`; `[src+8]`), release `+0x28` = `0xe3b590` → `[vtable+8]` = `0xe3b510` (`mov w1,#0x10; b 0xe69a20`), call `+0x30` = `0xe3b5a0`; the wrapper's destructor `0xe39e00` and deleting destructor `0xe39fa0` release the action through `+0x28`, and its copy/move constructors clone it through `+0x10` — the same pair the adapter uses |
| `+0x12d` is not a lone flag written for the adapter | the byte is accessed six times in `main`: `strb` at `0x1a292c` and `ldrb` at `0x1a2a68` (a different object), and reads at `0xe33194`, `0xe354d4`, `0xe387f4`, `0xe39ff0`; only the last is on the queued click's path |

Equivalence with the game's own click, stated as narrowly as the evidence allows:

- same function (`0xe39fe0`), same vtable slot the drain calls, same argument
  registers (`x0` = the wrapper object, and the wrapper forms `x1`/`x2` itself);
- same eligibility read, at the moment of the call, against the same live
  `CharacterDisplay` (`w.owner` is the panel the game's click named), so a
  withdrawn/locked skill returns before the action exactly as the game's click
  would;
- same action class, same owner pointer and same `(hero, skill)` values: the
  object is a clone made by the class's own copy slot from the very action the
  game handed the filter;
- the action's own guards therefore run too: `0xe3b5a0` starts with
  `[hero+0x1298]` → `+0x121c` must be 1 (`0xe3b5cc…0xe3b5dc`, else return 0),
  then reads the hero's selected-skill vector at `hero+0x1340/+0x1348`, compares
  the capacity at `[hero+0x1298]+0x1220` (`0xe3b654…0xe3b65c`, `b.ls` return 0
  when full) and either removes the skill or appends it. A locked or
  capacity-limited selection therefore behaves exactly as the game's own click,
  because it is the game's own code that decides.

What is *not* identical, and is not claimed: the game's queue holds a copy of
the wrapper made by the wrapper's copy constructor, destroyed after the drain;
the adapter builds the same 0x60-byte object on its own stack with only the four
fields `operator()` reads, and calls `operator()` on it. The wrapper is a
plain function object here — `operator()` reads `+0x10`, `+0x40`, `+0x50`,
`+0x58` and nothing else, touches no other member, and returns `void` (no
register or `errno` effect), so the call is expressible without guessing: one
pointer argument, no return value. `dd_init` verifies eight instructions of the
wrapper and all three vtable slots (`0x11956b8+0x30` = `0xe39fe0`,
`0x1195228+0x10` = `0xe3b520`, `+0x28` = `0xe3b590`, `+0x30` = `0xe3b5a0`), and
refuses the policy if any of them differs, rather than calling into an
unverified build.

### 12.4 The object the replay calls is owned by the adapter

- **Made at the click.** When the game's own click arrives while the finger is
  down, the filter withholds it and asks the action class for its own clone
  (`+0x10`). Nothing else is kept: the clone carries the vtable and the owner
  pointer, and `str x9,[x0]`/`str x9,[x0,#8]` in `0xe3b520` are the whole
  construction. The game's object may be destroyed by the drain immediately
  afterwards; the adapter never holds it.
- **Checked again at the press.** `dd_target_live` requires: the clone's vtable,
  `clone+8 == panel`, the panel's vtable `0x11946c0`, the panel's current hero
  (`+0x120`), the panel's state (`+0x2c0 == 1`) and the eligibility byte
  (`+0x12d == 1`). Only then is the wrapper entered.
- **Not freed while in use.** Before the mutex is dropped for the guest call,
  the clone is detached from the shared hold state (`dd_replay` names it); after
  the call the same thread clears that name and releases the clone outside the
  lock. Another gate reached during the call therefore cannot free the object the
  wrapper is using, and no guest code runs with `dd_mu` held.
- **Released on every other path.** A new contact generation, a cancel, more than
  8 px of movement, a second finger, a lost pointer, the close observation
  (`0xe274c0`), the destructor observation (`0xe3d7d0`), a withdrawn
  eligibility/target, and the end of the contact all release the clone and block
  the rest of that contact, including the click the game sends on lift. The
  policy test asserts the balance (`clones 9, releases 9`).
- **Residual risk, unchanged and not hidden.** A `CharacterDisplay` rebuilt in
  place that reaches neither the close nor the destructor observation could
  reuse the captured storage. The adapter then re-reads the vtable, the hero, the
  state and the eligibility from that storage; if all still match, the toggle
  applies to whatever selection the storage now describes. Closing that needs an
  object-identity guarantee the game does not expose, so it is recorded, not
  patched, and no dangling pointer is dereferenced silently: the clone is the
  adapter's own object, and the panel is only read through the checks above.

### 12.5 The 0.5 s clock does not touch the recognizer

`dm_touch_contact_snapshot` promotes one still finger that has been down for
0.5 s from `DOWN`/`HOLDING` to `PRESS` **in the copy it returns**, under `g_tl`,
and only while `g_touch_policy` is set:

```c
if (g_touch_policy && out->count == 1 && out->down_ns && (out->phase == DM_CONTACT_DOWN || out->phase == DM_CONTACT_HOLDING) &&
    dm_touch_now_ns() - out->down_ns >= 500000000ull) out->phase = DM_CONTACT_PRESS;
```

`g_contact` itself is not modified; `gesture_fill` builds `GestureState` from its
own `g_gf`/`g_gr` history and never calls the snapshot; `touch_fill_n` is
untouched. `g_touch_policy` is set only by `dm_touch_policy_activate`, which
`dd_init` calls with the verified result and only on iOS with
`DM_DD_TOUCH_POLICY=1`. With the setting off, on the Mac, on another game or on
an unverified build, no caller ever sees the promotion. The policy test shows
both views of one physical hold: with the policy off the snapshot reports
`DOWN`/`HOLDING`, with it on the same finger reads `PRESS`, and the recognizer
suites (`t_gesture` 43 checks, `t_touch` 13 checks) are unchanged.

### 12.6 Policy tests (43 checks)

`dm/host/tests/t_dd_touch.c` (built with `-DDM_DD_TOUCH_TEST`) drives the gates in
guest order against a fake 40 MB module image whose `0xe39fe0` page holds **real
ARM64 code with the wrapper's own instructions** (18 words: save `x30` and make
the frame, `ldr [x0,#0x10]`, `ldrb [x8,#0x12d]`, `cmp #1`, `b.ne` to the
teardown, load hero/skill/action, load `[action]`, load `[vtable,#0x30]`, `blr`,
restore and `ret`), and a fake action class whose `+0x10` clones, `+0x28`
releases, and `+0x30` counts entries, re-enters the filter exactly as the gate
does, and can refuse the change internally (a locked skill or a full selection).
No "always allow" toggle stands in for the game:

| Case | Checks |
| --- | --- |
| the wrapper itself | an eligible click reaches the action; an ineligible one never does |
| short tap | click withheld, captured as an owned copy, released at lift, no lift click, 0 toggles |
| hold, click at touch-down | withheld at the click, **1 toggle at 0.5 s through the wrapper**, the copy released after the call, a second click during the hold withheld, no lift click |
| hold, click only on lift | nothing at Press, **1 toggle on lift**, a repeat lift click withheld |
| eligibility true → false | no wrapper entry at Press, capture released, no lift click |
| false → true again | the capture was already dropped, so still no replay and no lift click |
| locked skill (the game never delivers a click) | nothing reached the filter, no toggle at Press or on lift |
| native refusal (locked or selection limit) | the wrapper runs the toggle once, a duplicate click is not retried |
| panel not open (state 2) | click withheld, nothing captured, no toggle at Press or on lift |
| panel closed during the hold | capture discarded at once, no toggle at Press or on lift |
| move > 8 px | 0 toggles at Press and on lift |
| second finger | 0 toggles at Press and after it lifts |
| policy off | every click runs unchanged, nothing captured, no replay |
| host-clock Press | only with the policy active; the snapshot is untouched otherwise |
| 200 ms hold | 0 toggles on lift |
| leak check | `clones == releases` |

```
$ make -C dm/host/tests GAME=01008F1008DA6000 build/t_dd_touch && build/t_dd_touch
== 43 checks, 0 failed (clones 9, releases 9) ==
```

What the test does **not** execute: the game's real toggle body. The refusal
cases (`native refusal`, `locked skill`) are the fake action returning early, and
the real body's own guards (12.3) were read, not run. The wrapper, by contrast,
is real code on the replay path, so a replay that skipped the eligibility check
would fail this test rather than pass it.

### 12.7 The iOS limitation: the toggle happens on lift

The adapter can only replay a click the game has already delivered. On the
iPhone this grid's click arrives with the lift: what appears under the finger
while it is down is the game's hover, and a tap's click is the one the game sends
when the touch ends. That is also why a tap must be *withheld* rather than
ignored — there is a click to withhold. Consequently:

- **a 0.5 s hold toggles once, at lift** (the filter allows the game's own
  lift click after a 0.5 s hold), not at the 0.5 s instant;
- **a tap or a hold shorter than 0.5 s toggles nothing**;
- the press path of 12.3 (replaying a captured click at 0.5 s) is exercised by
  the policy test and would act at 0.5 s only on a build that delivers the click
  while the finger is down. This round does not claim the iPhone build does.

This is a real limit of this delivery, not a wording choice: "hold for 0.5 s and
it acts while you are still holding" is not implemented on iOS.

### 12.8 Tests, artifacts and build evidence

Other suites this round: `t_touch` 13/13, `t_gesture` 43/43, `t_touch_threads`
5/5, the rest of `make -C dm/host/tests GAME=01008F1008DA6000 run` exit 0;
`make … tsan` (audio SPSC, touch threads) clean; from `dm/tools`,
`python3 -m unittest tests.test_entry_filters tests.test_patches
tests.test_spin_waits` 19 tests OK. Logs:
`/Volumes/MacData/code/.worktmp/darkest-dungeon-1.3.0/tmp/touchpolicy-verify-20261029/host_tests_round4.log`
and `tsan_round4.log`.

| Artifact | Size | SHA-256 |
| --- | --- | --- |
| `deliver-touchpolicy-eligibility-20261029/DarkestDungeon-touchpolicy-eligibility.ipa` | 1,688,269,332 | `ed05d0c8409d735ba25bb376a7ad49e63abfe4bc4159127b9d5cb884abfc3d1b` |
| `.../Darkest Dungeon 1.3.0-touchpolicy-eligibility.app` (tree) | 3.3 GB, 11,434 files | `bb08a0c28e7a24a791eec42a4f14b11cc88626a9f4fb51206f248a77979d0d6f` |
| `...app/Contents/MacOS/dmhost` | 2,460,232 | `7c455a55b03be7d693b58b219824497265239100271fbd4b580cb654dcfb2e16` |
| `...app/Contents/MacOS/launch` | 900,696 | `bcfa1db5c44bb469447a9f0cf534ad2685b860148ee65b6c2245660979816308` (unchanged) |
| `Payload/DmIOS.app/DmIOS` inside the new IPA | 42,918,776 | `7bac05e1a0f96c45da67e03d3ed27acd097be41804523740083ee4f4dd7ec826` |

Absolute paths:

- `/Volumes/MacData/game/darkest-dungeon/deliver-touchpolicy-eligibility-20261029/DarkestDungeon-touchpolicy-eligibility.ipa`
- `/Volumes/MacData/game/darkest-dungeon/deliver-touchpolicy-eligibility-20261029/Darkest Dungeon 1.3.0-touchpolicy-eligibility.app`

The prepared modules were not rebuilt: `main.patched.bin` is still
`e88d948e9f3248d0de2db1c6ad21ea95e3e40d4ab3e45256e434c6dd0c91d08d`, and
`patch_nso.py` `69d6fb5c…d76c0` and `dm/games/01008F1008DA6000/patches.py`
`8381985b…47e` still equal the hashes in
`patched_v393216/build_src.sha256`. Both packages carry `obs 22/24/25/26/27` and
`filter 1 0xe3b5a0`, and a `launcher.json` `DM_DD_TOUCH_POLICY` toggle with
`"default": "0"`.

Build commands, from the repository root (the working tree is the only source):

```
python3 scripts/build_ipa_from_nsp.py /Volumes/MacData/game/darkest-dungeon \
  -k /Volumes/MacData/game/darkest-dungeon/prod.keys -p v393216 \
  -o /Volumes/MacData/game/darkest-dungeon/deliver-touchpolicy-eligibility-20261029/DarkestDungeon-touchpolicy-eligibility.ipa

python3 scripts/build_ipa_from_nsp.py /Volumes/MacData/game/darkest-dungeon \
  -k /Volumes/MacData/game/darkest-dungeon/prod.keys -p v393216 \
  --mac-app "/Volumes/MacData/game/darkest-dungeon/deliver-touchpolicy-eligibility-20261029/Darkest Dungeon 1.3.0-touchpolicy-eligibility.app"
```

Evidence that these sources were compiled, not inferred from mtimes:
`host__hle_dd_touch.o`, `host__hle_touch.o`, `front_ios.o` and `DmGamepad.o`
were deleted before the build; the `xcodebuild` log
(`01008F1008DA6000_build/ipa/build/ios/pkg/build.log`) lists
`CompileC … host__hle_dd_touch.o … dm/ios/Gen/src/host__hle_dd_touch.c`, 55 files
compiled; `dm/ios/Gen/src/host__hle_dd_touch.c` is a symlink to
`dm/host/hle_dd_touch.c`; the new `DmIOS` contains this round's strings
(`press (0.5 s): entering the original wrapper once`,
`eligibility or target withdrawn`) and `_dd_skill_filter` calls `_dm_touch_now_ns`;
the Mac host, one `clang` invocation over `hle_*.c` with `front.h` as a
dependency, was rebuilt after the last source edit.

The shipped `_dd_frame_tick` shows the new order in machine code
(`otool -tV -p _dd_frame_tick Payload/DmIOS.app/DmIOS`):

```
0x100096104  bl   _pthread_mutex_unlock
0x100096108  ldr  x8, [x21, #0xe60]        ; the loaded base
0x10009610c  add  x8, x8, #0xe39, lsl #12  ; + 0xfe0 → 0xe39fe0, the wrapper
0x100096114  add  x0, sp, #0x10            ; the 0x60-byte wrapper object
0x100096118  blr  x8
0x10009611c  mov  x0, x20
0x100096120  bl   _pthread_mutex_lock
0x100096124  str  xzr, [x22, #0xe68]       ; dd_replay = 0
0x10009612c  bl   _pthread_mutex_unlock
0x100096134  bl   _dd_action_release       ; the clone, outside the lock
```

Previous deliveries verified unchanged by hash after this round:
`deliver-touchpolicy-longpress-20261029` `48b8c9bb…c8dd`,
`deliver-touchpolicy-safety-20261029` `70ef894f…e28d`,
`deliver-touchpolicy-verify-20261029` `23bff8d3…c6fe`,
`deliver-20261029` `e638f3c7…1084`. The packaged `main.patched.bin` in the new
Mac App is byte-identical to the prepared module
(`e88d948e…d08d`), and the IPA's `Payload/DmIOS.app/dm/main.gates.tsv` carries
`obs 22/24/25/26/27` and `filter 1 0xe3b5a0` with the toggle defaulting to `0`.

### 12.9 Status and what is still unverified

| Item | Compiled | Tested | In a running game |
| --- | --- | --- | --- |
| Original wrapper runs on replay (eligibility +0x12d, live) | yes | 43 policy checks with a real wrapper stub | **no** |
| Eligibility true/false, withdrawn/restored, locked, selection limit, panel open/closed, cancel | yes | policy tests (the action body's own refusal is simulated) | **no** |
| One toggle per contact after a 0.5 s hold | yes | policy tests, both click timings | **no** |
| Tap, short hold, move, second finger, cancel → 0 | yes | policy tests | **no** |
| Toggle at the 0.5 s instant on iOS | not reachable (12.7) | press path only | **no** |
| Hover handoff | unchanged from section 11 | — | the hover the user sees is the game's own |
| Roster long press, trinkets | not implemented | — | unchanged |

Manual acceptance for this build:

1. Setting off: unchanged behavior; no `DD touch policy: enabled` line.
2. Setting on, combat skill grid: a short tap leaves the selection unchanged and
   shows the hover; a 0.5 s hold changes the selection **once, when the finger is
   lifted**; nothing toggles at the moment the finger passes 0.5 s.
3. Hold, then move > 8 px, add a second finger, close the panel, or take the
   controller: no toggle at all, including on lift.
4. With `DM_DD_TOUCH_DEBUG=1` in the app's `Documents/env.txt`, the log's lines
   say which of these happened (`hold armed`, `entering the original wrapper
   once`, `toggle withheld (phase …)`, `eligibility or target withdrawn`), which
   is the evidence to send back if the hold still does nothing.
5. A crash, a doubled toggle, a toggle after a tap, or a toggle inside a closed
   panel is a failure, not a partial success.

## 13. Primary-agent continuation: character camping skills and Nomad merchandise

Date: 2026-10-30. Branch `main`, HEAD
`6dcf9868582388173f81f4f02385cd4cdb125b3e`. The delegated source task stopped
with an HTTP 429 quota error; the primary agent then took over at the user's
explicit request. All pre-existing changes were retained. No commit or push.

### 13.1 User-confirmed baseline and the missing camping gate

The user confirms character combat-skill touch behavior and existing camping
long-press behavior work. They explicitly clarified that the remaining camping
short-tap problem concerns **the character-details camping-skill list**, not the
in-dungeon camp overlay which spends respite points and selects targets.

The previous delivered `touchpolicy-eligibility` App's `program/main.gates.tsv`
contains only `filter 1 0xe3b5a0`; there is no camping filter. The working tree
already contained an unshipped extension for the separate camping action class
and `filter 2 0xe3a6d0`. This explains why that delivered package could not apply
the new short-tap policy to the camping list. This is a package/source mismatch,
not evidence that the user's observed long press failed.

Original-module decoding rechecked these contracts:

- `0x11955b8` is `CharacterDisplay::ShowCampingSkillGrid::$_5,
  bool(Hero*, unsigned)`; copy/release/call slots are `0xe3a650`, `0xe3a6c0`,
  `0xe3a6d0`.
- The camping action starts `sub sp,sp,#0x70` (`d101c3ff`), then reads Hero from
  `[x1]` at `0xe3a6e8`, skill from `[x2]` at `0xe3a6ec`, owner from `[x0+8]`
  at `0xe3a6fc`. It uses the separate Hero camping selection vector at
  `+0x1310/+0x1318`; combat uses another vector.
- The existing original wrapper `0xe39fe0` and native camping action remain in
  charge of eligibility and mutations. The adapter does not implement camping
  costs, targets, or in-dungeon skill execution.

The camping source extension was retained and its formerly unused fake camping
class was wired into policy tests: short tap, release-only long click, one
wrapper replay, duplicate/release suppression, revoked eligibility, explicit
cancel, missing camping gate and policy-off fallback. Native mutation bodies
are simulated in these tests, not executed from the retail game.

### 13.2 Nomad binding: narrow operation suppression before dispatch

New source implementation, pending actual iOS acceptance:

1. `TrinketSupplyDisplay::PreChildrenShowInternal` (`0xc2fab0`) constructs the
   unique purchase callable vtable `0x117a678` at `0xc2fcac..b4`, copies it into
   the grid's primary binding at `0xc2fd18`, then calls `0xe16370` at
   `0xc2fdbc`. Its factory installs `TrinketSupplyDisplay` vtable `0x117a078`
   at `0xc32730..5c`. Comet constructs a distinct callable `0x117a7c0`.
2. `0x117a678+0x30` is `0xc30760`. The function reads the slot index from `[x1]`
   at `0xc30798`, checks capacity at `0xc30864`, can show
   `not_enough_room_confirm_nomad_wagon`, and later deducts currency and removes
   merchandise. Thus blocking only a shared renderer or ItemValid predicate is
   unnecessary and would lose unrelated UI behavior.
3. The grid builds two owned action wrappers, `InventoryButtonInGrid::$_0/$_1`,
   vtables `0x11933a8` and `0x1193428`, at `0xe17784..f4`. Each copies the
   grid parameters into object+0x10 using `0xe17c20`. The original primary
   callable is consequently at wrapper+0x70. This is checked live, not inferred
   from a rectangle or a generic inventory-slot vtable.
4. Primary wrapper `0xe18410` chooses a bound callable at +0x70 or +0xd0 and
   invokes it at `0xe18460`. Secondary wrapper `0xe181f0` checks its bound
   eligibility at +0x130 and invokes a secondary operation at +0x100. Entry
   filters now return before either original prologue **only when** the wrapper
   vtable matches and its primary callable's vtable is exactly `0x117a678`.
5. The Nomad renderer initializes the other action bindings to null, including
   original parameter +0xf0/+0x120 (`0xc2fb74/90`). Its call to the shared grid
   passes null DragContext and DropContext (`0xe16e2c/30`). This is the static
   basis for isolating the merchandise operation at these wrapper boundaries,
   instead of filtering a final transaction after an earlier pickup. Both
   wrappers are gated so a future native alternate event cannot enter the other
   bound operation for the same recognized merchandise binding.
6. Rendering, hit testing, tooltip construction and independent confirmation
   buttons are not gated. No callback pointer or merchandise object is saved;
   no purchase is deferred and no new long-press purchase is introduced. The
   original shop code still drives the cursor and tooltip. The separate
   transaction function itself is deliberately not patched, so an independently
   reached confirmation is not globally disabled.

New gates (original words asserted by the rewriter):

| Entry | Original word | Filter ID | Scope |
| --- | --- | --- | --- |
| `0xe3a6d0` | `d101c3ff` | 2 | Character-details camping toggle |
| `0xe18410` | `d10083ff` | 3 | Nomad-bound primary merchandise operation only |
| `0xe181f0` | `d101c3ff` | 4 | Nomad-bound secondary merchandise operation only |

Shop activation additionally requires both shop gates, exact neighboring
instructions, both inventory-wrapper call slots and the Nomad purchase call
slot. Missing gates/signatures leave shop behavior original. The existing exact
Title/main/SDK checks still apply. No new generic gate kind or recognizer change
was needed this round; only filter IDs and the explicit DD profile entries grew.

The shop filter is iOS-source-only and requires the game's non-controller
ownership. Mac, UNKNOWN/script input, controller-owned input, Comet, ordinary
items, equipment and other bindings pass. The shop's recognized merchandise
operation is suppressed for both short and long contacts: there is **no new iOS
purchase gesture**. If buying was only possible by tapping that merchandise,
that touch purchase path is unavailable with this experimental option enabled.
Disable the option to restore it. Actual price/stock/pickup/tooltip observations
on iPhone remain required; unit tests do not constitute that acceptance.

### 13.3 Town roster: additional evidence, still no production hook

Rechecked `0xc61890` (predicate owner+0x140, then owner+0xb0) and `0xc615b0`
(selection/highlight and roster callback). Further forwarding was resolved:
`RosterList::AddChildPanel::$_0` vtable `0x117db68`, operator `0xc70430`, forwards
into list+0xe0; `::$_1` vtable `0x117dbf8`, operator `0xc70330`, forwards into
list+0x110. These are real owner-dependent callbacks, not a proof that one is
universally the right-hand town roster's double-click action. No final
right-list-only callback identity or reliable double-event mapping was closed.
No guessed CharacterDisplay call, global double-tap replacement, or roster
filter was added.

The primary agent used Computer Use for a real Mac run, bounded to 180 seconds,
with a fresh copy of the pre-existing **isolated test save** from
`mouse-ui-dynamic-20261028/run-trinket/save` into
`/private/tmp/dd-touch-main-20261030/save`. The running App was selected by its
full path because several Apps share the bundle identifier. Actual observations
were the introduction and campaign screen, whose copied estate was still
**The Old Road, Week 0**. The bound expired before town; the process terminated
normally. This did not reach the right-side roster and did not produce LLDB
callback evidence. It is not a town-portrait acceptance run. No personal save
was opened or overwritten. Host log and fixture provenance are in that temp
folder; no input-mode, auto flag, UI-coordinate or game-memory injection occurred.

### 13.4 Changes and verification boundaries

This continuation extended `dm/host/tests/t_dd_touch.c`, completed the existing
camping source extension, added the narrow shop filter/activation checks in
`dm/host/hle_dd_touch.c`, added explicit filter IDs in `dm/host/dm.h`, added the
shop entries in the DD `patches.py`, and updated the existing setting's help text.
It did not rewrite the already user-confirmed combat interaction.

Results obtained by the primary agent:

- `t_dd_touch`: **63 checks, 0 failures** (43 previous + 10 camping + 10 shop
  identity/source/fallback checks). Combat clone/release counts remain 9/9;
  camping copies balance. Shop tests exercise the real filter but simulate
  merchandise and callback objects; they do not execute retail transactions.
- `tests.test_entry_filters`, `tests.test_patches`, `tests.test_spin_waits`:
  **19 tests, OK**.
- Full `make -C dm/host/tests GAME=01008F1008DA6000 run`: exit 0 after running
  with normal local audio access. The sandbox-only attempt failed at AudioUnit
  initialization; touch/gesture checks had passed before that environment error.
- `make ... tsan`: touch concurrency **5/5**, no reported data race.
- `git diff --check`: clean.

Logs: `/private/tmp/dd-touch-main-20261030/` (`policy.log`, `python-tests.log`,
`host-tests-unsandboxed.log`, `tsan.log`). Default Python lacked build modules;
the existing `/private/tmp/nsz-venv/bin/python` environment supplies them. No
packages were downloaded or installed for this continuation.

All iOS effects remain pending user acceptance. In particular, this round has
not dynamically proved that merchandise hover is preserved while currency,
stock and drag/pickup context remain unchanged, nor that a long contact fires
before lift rather than on lift. Do not interpret mock action counts as proof
of original game transaction behavior. Town portrait long press remains absent.

### 13.5 Compiled artifacts and final package audit

Both targets were built by the primary agent from the current working tree using
`/private/tmp/nsz-venv/bin/python scripts/build_ipa_from_nsp.py`, input folder
`/Volumes/MacData/game/darkest-dungeon`, version `v393216`, and the existing local
key file (no key values logged). Build commands used `-o` for the IPA and
`--mac-app` for the App, each with an independent new output path.

Output directory:
`/Volumes/MacData/game/darkest-dungeon/deliver-touch-camping-20261030/`.
The final artifacts are:

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `DarkestDungeon-touch-camping-nomad.ipa` | 1,688,270,100 | `f1665c9d9d279343a78929fd6c112f7c0547a9a9de53cd58b260fb04f7c02381` |
| `Darkest Dungeon 1.3.0-camping-nomad.app` | 3,514,397,995 (11,434 files) | directory tree: `9f5cc27c8d85b0a2219eb17d9a5c8f30ec7410db6582269b90ccf938ae28b907` |
| Mac `Contents/MacOS/dmhost` | — | `f4aa6c7b7cde0c95db2a7655db2ae73e9ed4c07245a318b8c880c958d3930e6a` |
| IPA `Payload/DmIOS.app/DmIOS` | 42,918,960 | `4b623f272ed916aceec50306f66f4e26863622f15c40f133be3cd5d4f73165b7` |

The App tree digest is SHA256 of UTF-8 lines `file_sha256`, two spaces,
relative POSIX path and newline, sorted by path. It is not a file digest of an
App archive. `manifest.json` in the output directory records this definition,
source digests, exact artifact paths and the default-off launcher setting.

`ipa-camping-nomad.log` records a successful fresh module preparation and
`xcodebuild`: **55 files compiled**, including `host__hle_dd_touch.o` and
`host__hle_touch.o`, followed by successful packaging. `mac-build.log` records
successful Host compilation and App packaging. The binary contains the new
`Nomad focus-only` activation string. Both packages contain **filters 1, 2, 3,
4**, and the existing observations. The launcher setting note describes combat/
camping character skills and Nomad focus-only; its default is `"0"`.

The IPA contains 7,962 RomFS files, all five AOC groups (`1` through `5`, 3,444
files), and the existing GL shader libraries. The build checks 48 shader stages,
47 programs and 48 Metal functions for each platform. No diagnostics or test
logs were embedded in the App/IPA; `validation-logs/` is a sibling in the
output directory. The earlier camping-only intermediate IPA is not the final
Nomad delivery. Previous delivered Apps/IPAs were not overwritten.

Signing audit: the IPA's extracted `DmIOS` is **not signed at all**; it requires
the user's existing signing/sideload flow. The Mac launcher has only its
linker's ad-hoc signature (`TeamIdentifier` absent, no sealed resources), not a
Developer ID signature or notarization. No signing identity was used and no
App/IPA was installed on a device. The new Mac App was compiled and audited,
not launched for a claim of functional acceptance.

The freshly regenerated DD `sdk` (which has no FILTERS) is byte-identical to the
pre-change baseline for `patched.bin`, gates, fixups, obs, sites and cuts. The
previous verified Rhythm Heaven/Mario Kart outputs were not regenerated this
round; their recorded rewriter source hash equals the current rewriter hash.
This round did not edit `patch_nso.py`, `hle.c`, `hle_touch.c`, `front.h` or the
Mac/iOS frontends further; those pre-existing changes remain. The new per-build
FILTERS entries belong only to DD's exact main Build ID. No other game's profile
was changed.

Minimum iOS acceptance with `DM_DD_TOUCH_POLICY=1`:

1. Character camping list: short tap only hovers; hold and release changes the
   original selection once; costs/locked/selection-limit behavior stays native.
2. Combat list: retain the user's working behavior, including no extra release
   toggle.
3. Nomad merchandise: tap/hold show original price/tooltip without a purchase,
   currency change, stock change, pickup/drag or late operation. There is no new
   touch purchase gesture. Disable the setting to recover original purchasing.
4. Ordinary provisions, backpack, equipment and Comet shop remain unchanged.
5. Option off and controller/Mac sources retain original actions.

Town portrait holds are still **not implemented**, so there is no portrait hold
acceptance claim. The current `main` HEAD is unchanged and all source, tests and
report changes remain uncommitted/unpushed.

## 14. Continuation: the Nomad hold's callback lifetime, Mac pointer review, roster ABI, trinket-box MOD (2026-10-30)

Date: 2026-10-30. Branch `main`, HEAD
`6dcf9868582388173f81f4f02385cd4cdb125b3e`. The previous delegated agent stopped
on a quota error after it had started reworking the Nomad hold. This round
reviewed that work against the original module, found and fixed a
use-after-free in the Nomad capture path, reworked its tests to model the real
object lifetime, reviewed the Mac pointer path read-only, closed the roster
action ABI (but not its hover anchor), and analysed the trinket-box MOD layout.
No commit or push; no original NSP/NSO/RomFS/DLC/shader/save was modified. No
game was launched and no GUI action was taken in this round.

### 14.1 The Nomad long press could never fire: it kept the game's per-frame queued callable

The working tree's shop design captured the game's own wrapper object at the
click and re-read it every frame and at the press (`dd_shop_hold_state.action`,
`dd_shop_target_ok(action, copy)`). Decoded from the same `main`
(`ff2bf22565188d11ea0981ee0e2b53ce`, text `0xe6afb0`), that object cannot outlive
the click's frame:

- `0xe171c0` (called per frame by the shared grid `0xe16370` at `0xe16e34`)
  builds the two `InventoryButtonInGrid` action wrappers with `_Znwm(0x310)` and
  `0xe17c20` at `0xe17784..f4`; they are owned by that frame's control and
  released at `0xe17b54`/`0xe17bb4`.
- The click is a `std::function` pushed into the frame's action queue, so the
  entry the filter sees is a *copy* made by the queue's `push_back`
  (`0x717370`, vtable `+0x10` clone). The frame's drain walks the queue
  (`0x8b5dd4..0x8b5dfc`) and then **destroys every entry** it has just called
  (`0x8b5e9c..0x8b5eb4`, `ldur x0,[x20,#-0x10]` = the entry's `__f_`, then
  `vtable+0x20` for an inline target or `vtable+0x28` for a heap target) before
  clearing the vector end (`0x8b5e1c`). The queue is cleared in the same frame,
  after the callback and the UI update.

The filter therefore stored a pointer that was freed before the 0.5 s press:
`dd_shop_target_ok` dereferenced freed memory on every following frame (and at
the press), and even when that read happened to survive, the capture was dropped
because the freed object no longer matched — the hold could not purchase. The
previous test kept its fake wrapper object alive and so could not see this.

ABI confirmed against the module for the fix (all `S`):

| Fact | Evidence |
| --- | --- |
| Wrapper classes | `0x11933a8` / `0x1193428` are `__func<Inventory::Display::InventoryButtonInGrid(...)::$_0 / $_1, void()>`; slots `+0x10/+0x28/+0x30` are `0xe18350 / 0xe18400 / 0xe18410` (and `0xe18110 / 0xe181e0 / 0xe181f0`) |
| The wrapper entry | `0xe18410`: `ldrb w8,[x0,#0x300]`, mode 1 uses `[x0,#0xd0]`, else `[x0,#0x70]`; `ldr w9,[x0,#0x304]`; `ldr x9,[callable]`, `ldr x9,[x9,#0x30]`, `mov x0,callable`, `blr x9` with `x1=&param` |
| The purchase callback | `0x117a678` is `__func<TownUI::Panel::TrinketSupplyDisplay::PreChildrenShowInternal()::$_1, void(unsigned)>`, slot `+0x30` = `0xc30760`; its copy slot `+0x10` = `0xc30600` copies the captures `[+0x10]/[+0x18]` |
| The clone is the class's own | `0xe18350` allocates `0x310`, sets the vtable, copies the parameters through `0xe17c20` (which clones each nested `std::function` through its own vtable `+0x10`) and copies `+0x300/+0x304` as one 8-byte word; `0xe18400` is the deleting destructor slot |
| The parameter is an *available-slot* index | `0xc307b4..0xc307f0` counts entries whose first word is `>= 1`, compares that running count with `[x1]`, and returns the raw array index; `0xc307a8..0xc307ac` fixes the stride at `0x580` |
| Entry identity | `0xc30850..0xc30868` uses `begin + raw*0x580`; the item keys compared against the global item list are at `+0x44` and `+0x88` (`0xc308b8..0xc308e8`) |

Fix (all in `dm/host/hle_dd_touch.c`): the hold no longer stores the game's
object. At the click it snapshots the adapter's own clone, the container and
model the clone's captured purchase callback points at, the parameter, the raw
resolved index, and the two item keys. At the press it re-derives the same slot
from the live container and requires the same raw index and the same keys; it
reads the clone's variables only. The game's callback still makes every price,
capacity, currency and confirmation decision. The replay-identity check
(`dd_shop_replay`) also moved under `dd_mu`; it was read outside the lock.

`dm/host/tests/t_dd_touch.c` now models the lifetime: every click builds a fresh
deep copy (as the queue's `push_back` does), calls it, then destroys and poisons
it, and the container is a real vector of `0x580`-byte entries with available,
unavailable and key-changing cases. A regression to the old design fails the
"purchase once at 0.5 s" check instead of crashing.

### 14.2 What the Nomad policy does and does not claim now

- One purchase per contact: the game's own lift click is allowed after a 0.5 s
  hold, or, when the game dispatched on touch-down, the adapter replays the
  click-time wrapper once at 0.5 s (the clone carries its own deep copy of the
  purchase callback and its captured container/model pointers).
- Short tap, a shorter hold, movement beyond 8 px, a second finger, cancel,
  controller-owned mode, non-iOS sources, the secondary `0x1193428` binding,
  ordinary inventory bindings and modules without the gates keep the original
  behaviour. The Comet supply's own callable (`0x117a7c0`) is accepted since
  2026-10-31 and otherwise follows exactly the same rules.
- A changed merchandise entry (keys), a removed/unavailable entry, or a replaced
  container cancels the capture and suppresses the lift click as well.
- The wrapper's mode byte `+0x300` must be 0 (the `+0x70` binding the Nomad
  renderer installs at `0xc2fd18`). A mode-1 dispatch (the `+0xd0` binding) is
  never captured or replayed; the click is withheld, and the game's own lift
  click is still eligible for the `>= 0.5 s` rule (the safe fallback of 15.1).
- The DLC/Comet supply is enabled on the same terms (2026-10-31). Its purchase
  callback is a different class: vtable `0x117a7c0` =
  `__func<CometTrinketSupplyDisplay::PreChildrenShowInternal()::$_1, void(unsigned)>`,
  operator `0xc31e00`, and a different display class (`TownUI::Panel::CometTrinketSupplyDisplay`,
  vtable `0x117a198`). It builds its rows through the *same* builder
  (`0xe16370`, call site `0xc31530`) and the same `0x11933a8` wrapper with mode 0,
  so the display gate is unchanged; only `dd_shop_binding_ok` had to accept the
  second callable, which was verified independently (RTTI name, `+0x30` slot,
  bound at `+0x70` of the mode-0 wrapper). Its currency is the shard wallet
  entry (`persist.estate.json` `wallet[6]`, `shard`) and the price/stock/capacity
  decisions stay in the game's own callback. Static and live evidence:
  `docs/darkest-dungeon-dlc-shop-test.md`.
- Not claimed: device acceptance; hover/price/tooltip preservation on iPhone;
  and there is still no display-lifetime gate for the Nomad screen. If the shop
  is torn down between the click and the press while its town-model container
  keeps the same available entry and keys, the replay would run the original
  callback on that entry. Closing that needs a Nomad panel close/destruct
  observation that is not established, so it is recorded, not patched.

### 14.3 Mac pointer path: review only, no change

Reviewed read-only: `hle_dd_pointer_mac.c`, `dd_pointer.h`,
`front_mac.m`'s tagging, `LauncherSettings.swift` and
`LauncherSettingsChecks.swift` (the last two belong to the primary agent and
were not edited).

- The bridge still writes only `main+0x27e0890/894`, still requires a fresh
  Mouse HID revision, main `mode == 0` and the auto-controller byte clear,
  never writes either field, and refuses unless the exact main/SDK Build IDs,
  observation 22 and the two neighbouring words at `0x8b5dbc/0x8b5dc4` match.
- The new contact tagging does not change the game-visible streams: `g_contact`
  and its phase/generation are read only by `dm_touch_contact_snapshot` (policy
  adapters and tests); `touch_fill_n` still builds TouchScreenState from `g_f`,
  and `gesture_fill` from `g_gf`/`g_gr`. The explicit-cancel path is entered
  only while `g_touch_policy` is set, which `dd_init` does only on iOS for this
  title/build and only with a verified module.
- Mac left button, right button, wheel, drag clamping and HID publication are
  unchanged apart from the source tag (`DM_CONTACT_MAC_LEFT`).
- Delivery dependency to keep in mind for the primary agent's GUI check: the
  Launcher only offers the DD bridge when the App's `Info.plist` carries
  `NXTitleID == 01008F1008DA6000`; a Mac App built without that key shows the
  Mouse HID switch but not the pointer switch, and the host then still refuses
  the bridge. That is a packaging/launcher matter, outside this review.

No host-side regression was found in the reviewed pointer path; the reported
Mac regression's confirmed cause remains the launcher's missing environment
export, which the primary agent fixed.

### 14.4 Town roster: the double-click-only action ABI is closed, the hover anchor is not

The dynamic evidence of section 13.3 stands (single click: `0xc61890` then
`0xc70430`; double click adds `0xc615b0`; a hold adds neither). Decoding the
same module closes what `0xc615b0` is:

- `0x117cdc0` is `__func<TownUI::Panel::RosterElement::PreChildrenShowInternal()::$_2, void()>`;
  slot `+0x30` is `0xc615b0`.
- `0xc615b0` reads the element only through `[x0,#8]` (it never touches another
  field of the function object): it tweens `[element+0x410]`, sets
  `[element+0x231] = 1`, walks the list at `[element+0x80]` (vector at
  `+0x90/+0x98`, stride `0x40`, first word = element) to find the element's
  index, clears the shown byte of the other elements and calls `0xcb59a0` with
  `w4 = index` and two callables whose RTTI is
  `RosterList::ShowCharacterDisplay(unsigned)::$_0` (`0x117e618`) and `::$_1`
  (`0x117e698`). So this lambda is the roster's character-details action, and
  the double click is exactly the extra execution of it.
- A guard exists that is better than RTTI alone: `element` vtable
  `0x117c8d0` (`TownUI::Panel::RosterElement`), `[element+0x80]` vtable
  `0x117cfd0` (`TownUI::Panel::RosterList`) and the element found in that
  list's vector. Both are read from the element itself, not from a rectangle.
- The same entry is also reachable with a small host-built object
  `{vtable = 0x117cdc0, element}` because `0xc615b0` reads only `+8`, exactly
  as the skill wrapper replay builds its 0x60-byte object.

What is **still missing**, and why no roster hook was written:

1. No per-frame observation identifies the hovered `RosterElement` while the
   finger is down. The only current callback with the element, `0xc61890`, runs
   in the click path (its caller frame is `0x8b9d28` inside `0x8b97c0`, not the
   queue), i.e. on the tap's release for iOS; the queue drain only calls the
   list callable `0xc70430` afterwards. Capturing at the click cannot arm a
   0.5 s press.
2. A lift click after the hold would still run the single-selection action
   (`0xc61890`/`0xc70430`). Suppressing it needs a filter on that path and a
   proof that omitting the duplicate selection is harmless while the details
   are open; neither is established.
3. The left/right or town/embark instance distinction is now reduced to the
   list class but not proven for every place `RosterElement` appears; a
   position-based classifier was explicitly not used.

The implementation therefore needs one new observation at
`PreChildrenShowInternal` (`0xc5c6c0`) or at the control dispatch
(`0xc60080`) carrying the element and the hover bit, plus a lift-click
suppression filter and the list/generation checks above. That is a next round's
work; this round adds no roster gate, timer or synthesized double tap, and the
Mac left button remains the game's own.

### 14.5 Trinket-box MOD

The trinket-box MOD analysis and its reversible compatibility module are in
`docs/darkest-dungeon-mod-1099001958-layout.md`. In short: the mod's active
`realm_inventory.layout.darkest` is a stale partial file that omits the
unequip-button position and the whole `trinket_sort_dialog_*` group that both
the base game and 1.3.0 define and that `main` looks up by name, which explains
the misaligned buttons above the trinket grid and the clipped/black sort popup.
The mod's Nomad/provision layout paths do not exist in this port, so those
overrides are dead. Nothing was overwritten; the fix is an additive module to be
loaded after the mod and needs visual acceptance.

### 14.6 Commands run this round

| Command | Result |
| --- | --- |
| `make -C dm/host/tests GAME=01008F1008DA6000 build/t_dd_touch && build/t_dd_touch` | `91 checks, 0 failed (clones 9, releases 9)` |
| `make -C dm/host/tests GAME=01008F1008DA6000 run` | exit 0; `t_touch` 13, `t_gesture` 43, `t_touch_threads` 5, `t_dd_touch` 91, all other suites pass |
| `make -C dm/host/tests GAME=01008F1008DA6000 tsan` | `t_audio_spsc` and `t_touch_threads` pass under ThreadSanitizer |
| `python3 -m unittest tests.test_entry_filters tests.test_patches tests.test_spin_waits` (dm/tools, existing venv) | 19 tests, OK |
| `git diff --check` | clean |

Log: `/private/tmp/dd-touch-20261030/host-tests.log`, `tsan.log`.

### 14.7 Status

| Item | Source | Tests | In a running game |
| --- | --- | --- | --- |
| Nomad hold no longer keeps the game's queued callable; identity re-derived from the clone + supply entries | yes | 91 policy checks with a queue-lifetime fixture | **no** |
| One purchase per contact, short tap/hold/tap-move/cancel/controller/other bindings unchanged | yes | policy checks + real filter | **no** |
| Nomad display close between click and press | not patched (no gate) | — | recorded risk |
| Mac pointer path | unchanged | reviewed read-only | primary agent's GUI check |
| Town roster hold | not implemented | — | gap listed in 14.4 |
| Trinket-box MOD layout | compatibility module written | file/key/diff evidence | needs visual check |

The minimum game/GUI steps remain the primary agent's: iOS packaging and the
Nomad hold/price/currency observation with an isolated save, the Mac click/hover
path with both launcher switches, and the trinket-box screen with the
compatibility module loaded after the mod.

## 15. Second continuation: Nomad store/model lifetime, roster dispatcher mapping (2026-10-30)

Date: 2026-10-30, later the same day. `main` at
`6dcf9868582388173f81f4f02385cd4cdb125b3e`; no commit or push; no original
NSP/NSO/RomFS/DLC/shader/save or mod file changed. The primary agent's Swift
files and `docs/darkest-dungeon-mouse-input.md` were not edited. This round
answers the lifetime question left open in 14.1/14.2, adds the campaign guard
and a safe fallback for the Nomad hold, and closes the dispatcher mapping for
the town roster without adding a hook.

### 15.1 The Nomad container and model are campaign lifetime, not panel lifetime

Decoded from the same `main` (`ff2bf22565188d11ea0981ee0e2b53ce`):

- **The supply is a building store of the town/campaign data.**
  `campaign/town/buildings/nomad_wagon/nomad_wagon.building.json` declares
  `"stores": [ { "id": "trinket_supply", ... } ]`, with
  `on_start_town_visit_priority: 1` (the stock is regenerated when town is
  entered). The panel factory `0xc326c0` hashes the supply object's virtual name
  and compares it with two records whose names are `trinket_supply`
  (`0xef0e0e`) and `shard_trinket_supply` (`0xedd008`), selecting
  `TrinketSupplyDisplay` or `CometTrinketSupplyDisplay`; the hash records live at
  `0xb19c80e88`/`0xb19c80ecc` and the factory reads `0xb19c80ec8`/`0xb19c80f0c`.
- **The display borrows both objects.** The factory allocates 0x90 bytes, stores
  the vtable `0x117a078`, then `stp x21, x20, [x0, #0x70]` (0xc32758): +0x70 is
  the `NomadWagonDisplay` panel, +0x78 the supply object. The complete
  destructor (0xc31070) and the deleting destructor (0xc2fa50) reset the vtable,
  destroy only the `std::function` at +0x20..+0x40 and (deleting) free the 0x90
  bytes — **neither releases +0x70 nor +0x78**, so the store and the panel are
  borrowed. The display does not own the container.
- **The purchase callback's captures are campaign state.** In
  `0xc2fab0`/`PreChildrenShowInternal`, `x19 = [[x0+0x78] + 0x70]` becomes the
  callback's +0x10 capture (the store's item container: vector at +8/+0x10,
  stride 0x580), and the +0x18 capture is
  `[0xb18ef7c8] + (0x40|0xa0) + 0xe20` (0xc2fb84..0xc2fbac) — a member of the
  current campaign object, the pointer the builder asserts on as
  `Campaign does not exist.` (`g_pCurrent`). Neither capture belongs to the
  screen.

**Answer to the open question:** closing the Nomad panel or switching the page
does not free the container or the model; they are campaign lifetime. What can
end while a phone finger is held is the campaign itself (save unload, returning
to the main menu, a new game). That is now guarded *before* the container is
read: `dd_shop_raw` refuses unless `[0xb18ef7c8]` still equals the campaign
captured at the click (a null campaign is refused too), and `dd_init` refuses
the shop unless `dd_main->size` covers `0xb18ef7c8` (this build's
`IMAGE_SIZE` is `0xb1a98000`). The store's own stock can be regenerated on a
town visit, but only after the screen was left, which requires a touch that
already cancels the contact.

**Safe fallback added.** When the click cannot be identified at all (mode byte
not 0, no resolvable slot/entry, or the model does not belong to the current
campaign), no capture is kept and nothing is replayed — but the game's own lift
click is left eligible for the `>= 0.5 s` rule instead of being suppressed for
the whole contact. A short tap's lift click is still refused by that rule, so
the "short tap focuses only" behaviour holds; a hold still buys through the
game's own click. This path reads no container.

**Residual, recorded and not patched.** If the panel closes between the click
and the press while the campaign and the store stay alive and the same
available entry with the same keys is still resolvable, the replay would run
the original purchase callback on that entry (an invisible purchase). The
display's deleting destructor entry `0xc2fa50` (`stp x29,x30,[sp,#-0x20]!`,
`0xa9be7bfd`) would be a valid observation site, but a gate on it can only be
added after a run shows whether the display is rebuilt per frame; if it is, the
gate would invalidate every hold. No gate was added, and that run is part of the
pending acceptance list.

### 15.2 Town roster: the dispatcher mapping, and the read-only plan

Static closure this round (same `main`):

- `TownUI::Panel::RosterElement::PreChildrenShowInternal` (`0xc5c6c0`) calls
  `0x73b6d0` at `0xc60080` with `x0 = sp+0x6a0` (the widget state struct) and
  four `std::function` objects. Only two are non-empty:
  - `x1 = sp+0xa0` = `$_1` (`0x117cd40`, operator `0xc61890`); its inline target
    is `{0x117cd40, element}` (`0xc5ff98`) and its `__f_` is `sp+0xa0`
    (`0xc5ffa0`).
  - `x2 = sp+0x70` = `$_2` (`0x117cdc0`, operator `0xc615b0`); inline target
    `{0x117cdc0, element}` (`0xc60068`), `__f_ = sp+0x70` (`0xc6001c`).
  - `x3 = sp+0x40` and `x4 = sp+0x10` are empty (`__f_` cleared at
    `0xc60020`/`0xc60024`).
  At `0xc60084` the element is in `x24` (it is used at `0xc600d8`
  `[x24+0x3f8]` and in the list walk at `0xc600e4..0xc60108`).
- `0x73b6d0` turns the result of the common interaction `0x738eb0` (call at
  `0x73b83c`, 48-bit masked into `x24` at `0x73ba4c`) into actions:
  - **bit 0** with `[widget+0x50]` non-null: tooltip registration `0x739cd0`
    (`0x73bc04..38`);
  - **bit 8** with `[widget+0x91] & 1` and a non-empty `x1`: after the register
    shuffle at `0x73b904..0x73b90c`, `x27` is `$_2`, so **bit 8 queues `$_2`**
    (`0x73bc3c..0x73bcbc`, `0x717370`), i.e. `0xc615b0` →
    `0xcb59a0` with `RosterList::ShowCharacterDisplay(unsigned)` (`0x117e618`)
    and its `$_1` (`0x117e698`) — the open-details action the dynamic double
    click ran;
  - bit 0x10 with `[widget+0x92] & 1`: the third argument (empty);
  - bit 0x18 with `[widget+0x91] & 1`: the fourth argument (empty);
  - bit 0x20 with `[widget+0x93] & 1`: the widget's own `+0x120` callable
    (empty here).
  `$_1` is not queued by a mask bit: it is cloned and handed to `0x747a00`
  (`0x73b870`, call at `0x73b9a4`) inside the `[widget+0x94] == 1` path — the
  primary single-click path the dynamic run observed. The details action is
  therefore gated by the game's **click** state (mask bit 8 and
  `[widget+0x91]` bit 0), not by a hover state, which is exactly the part a
  hold cannot reuse without synthesising that click state.

Right-side town guard (all read from the element):

- `[element] == main+0x117c8d0` (`TownUI::Panel::RosterElement`);
- `list = [element+0x80]`, `[list] == main+0x117cfd0`
  (`TownUI::Panel::RosterList`);
- the element is `*(u64*)(begin + 0x40*i)` for some `i` in
  `[list+0x90, list+0x98)`; the list's own `ShowCharacterDisplay` takes that
  index, so membership must be re-checked at action time;
- `[element+0x3f8]` is **recorded only**; the third run shows 0 on real
  interactive right-side elements, so an `== 1` guard is invalid (see 19.1);
- plus the live contact/hover condition below.

**Read-only observation plan (no hook).** Script:
`/private/tmp/dd-touch-20261030/c_roster_hover_trace.py` (LLDB Python,
read-only). It installs **one** breakpoint and validates the loaded build before
doing so:

- it reads the Host's own `g_mod`/`g_nmod` module table (the Host is built with
  `-g`) and refuses unless main is `ff2bf22565188d11ea0981ee0e2b53ce` and sdk is
  `b33804825108340e4cad9d080a636a3f`; the main base is cross-checked against
  `main: base 0x...` in the host log;
- it reads the mapped words and refuses on any mismatch:
  `0x73bc3c = 0x36400478` (`tbz w24,#8`), `0xc60080 = 0x97eb6d94`
  (`bl 0x73b6d0`), `0xc60084 = 0xf9404be0` (`ldr x0,[sp,#0x90]`) and
  `0x73b83c = 0x97fff59d` (`bl 0x738eb0`);
- every callback attempt (matched or not) counts against `DM_HOVER_ATTEMPTS`
  (default 20,000) and `DM_HOVER_SECONDS` (default 300); on either it disables
  **only the breakpoint it created** (`BP.SetEnabled(False)`) and writes a
  `stopped` record. It never enumerates or touches other breakpoints;
- `parent.x24` is checked explicitly: the script validates that the parent frame
  exists, that its `x24` register is available, that the value is a real pointer,
  and that `[x24] == main+0x117c8d0`; every failure writes an `error` record
  (throttled to 20) instead of silently recording a wrong element. `x24` is
  callee-saved and `0x73b6d0` stores it at `sp+0x50`, and `x29` is set at
  `0x73b6dc`, so the unwind is frame-pointer based; the vtable check makes an
  unwind failure visible rather than silent.

| Site | Register / memory | Meaning |
| --- | --- | --- |
| `main+0x73bc3c` (bit-8 test), filtered to `parent.pc == main+0xc60084` | `x24 & 0xffffffff` | the packed `0x738eb0` result: bit 0 hover; bit 8 is the first action bit, its label unverified (19.2) |
| same | `x20` | the widget struct: `+0x90..+0x94` flags, `+0x50` tooltip descriptor, `+0x120` own callable, `+0x2bc` name |
| same | parent `x24` | the RosterElement (`this`), validated against `main+0x117c8d0` |
| same | `[element]`, `[element+0x80]`, list `+0x90/+0x98` | the guard and the index |
| same | `main+0x27e0890`, `main+0x27e08b0` | the game pointer and the held-contact set |
| same (parent frame) | parent `sp` | the two callable vtables at `sp+0xa0` / `sp+0x70` (`0x117cd40`/`0x117cdc0`) |

What to do: `DM_TOUCH_LOG=1`, isolated save, reach town; move the pointer over
the right-side Dismas portrait and **hold without releasing** (10-20 frames),
then a single click, then a double click, then a short release; read
`events.jsonl`:

- during the hold: is `mask & 1` set for the element under the pointer, and is
  `mask & 0x100` clear? Is `[widget+0x91] & 1` clear? Is `element` the same
  pointer every frame?
- on a single click: `mask & 1` set, bit 8 clear, `[widget+0x91]&1` clear;
- on a double click: bit 8 set with `[widget+0x91]&1` set on the second
  dispatch (this is the game-authorised details action);
- on the left-side party portrait: does the same dispatch fire with the same
  vtables (0x117c8d0/0x117cfd0)? If not, the guard already separates the sides;
  if yes, the right-side guard needs more than the class pair.
- the element/list/index must stay valid for the held element; `[element+0x231]`
  (shown) and `[element+0x3f8]` are recorded, not used as guards (19.1).

If the hold shows `mask & 1` with a stable element and list, the target
identity for a future hold is available. What would still be missing before a
hook: the hold has to call `$_2` itself (the game only queues it for its own
double click), so a later round must prove on a disposable save that
`0xcb59a0`/`ShowCharacterDisplay` is safe and idempotent with the details
closed, that the selection/tween side effects of `0xc615b0` are acceptable for
a hold, and that the same element/list/index is re-checked at call time. Until
then no roster gate, timer or synthesised double tap is added.

### 15.3 Trinket-box MOD: hypothesis wording

`docs/darkest-dungeon-mod-1099001958-layout.md` was corrected: the missing
`unequip_button_*` keys and the five `trinket_sort_dialog_*` groups are a
**static causal hypothesis** for the misaligned buttons and the clipped/black
sort popup, not a verified explanation of every symptom. No fixed replacement
offset is recommended; the key-completion module is a compatibility candidate
that still needs the screen check (button pixel positions and popup placement
are not proven).

### 15.4 Commands run this round

| Command | Result |
| --- | --- |
| `make -C dm/host/tests GAME=01008F1008DA6000 build/t_dd_touch && build/t_dd_touch` | `99 checks, 0 failed (clones 9, releases 9)` |
| `make -C dm/host/tests GAME=01008F1008DA6000 run` | see `/private/tmp/dd-touch-20261030/host-tests-round2.log` |
| `make -C dm/host/tests GAME=01008F1008DA6000 tsan` | see `/private/tmp/dd-touch-20261030/tsan-round2.log` |
| `python3 -m unittest tests.test_entry_filters tests.test_patches tests.test_spin_waits` | see `/private/tmp/dd-touch-20261030/python-tests-round2.log` |
| iOS branch syntax check (`clang -target arm64-apple-ios16.0 -isysroot … -fsyntax-only -Wall hle_dd_touch.c`) | see `/private/tmp/dd-touch-20261030/ios-syntax-round2.log` |

Still unverified: device acceptance of the Nomad hold (price/currency/stock
unchanged on a tap, exactly one purchase on a held lift), the campaign teardown
behaviour in a real run, the roster observation above and the trinket-box
screen. The primary agent's GUI work covers those.

## 16. Third continuation: the Nomad deferred replay is withdrawn (2026-10-30)

This section supersedes 14.1/14.2/15.1 on the shop delivery. A purchase from a
closed panel is an unacceptable outcome, so the adapter no longer defers or
performs any purchase call. `main` at
`6dcf9868582388173f81f4f02385cd4cdb125b3e`; no commit or push; no game or mod
file changed.

### 16.1 What the click chain can and cannot reach (static)

- The click is a `std::function` copy of the control's
  `__func<InventoryButtonInGrid::$_0>` wrapper. Its parameters at +0x10 hold the
  grid parameters copied at `0xe17c20`: the first field is the static table
  `0xb199f018`, the rest are the bound `std::function`s, and +0x70 is the
  purchase callback `__func<TrinketSupplyDisplay::PreChildrenShowInternal()::$_1,
  void(unsigned)>`. The callback's captures are +0x10 = the supply store's item
  container and +0x18 = `[0xb18ef7c8] + 0x40|0xa0 + 0xe20` (a current-campaign
  member).
- No pointer to the `TrinketSupplyDisplay` (0x90 bytes, vtable `0x117a078`) or
  to its panel is in that chain. The factory `0xc326c0` stores the panel at the
  display's +0x70 and the supply object at +0x78 (`stp x21, x20, [x0, #0x70]`,
  `0xc32758`), but nothing back-references the display. The display's own words
  are zero-initialized by the factory (`0xc32734..0xc32754`: +0x10, +0x58,
  +0x5a, +0x6c), with +0x80 holding the factory's count argument; none was
  identified as a visibility flag, and no observation reaches the display. Its
  only close events are the destructors `0xc2fa50` (deleting) and `0xc31070`
  (complete), which free only the 0x90 bytes and a `std::function` and never
  release +0x70/+0x78.
- Therefore the store and campaign member are memory-safe across a hold (15.1),
  but **no state observable at the click proves the screen is still open**. A
  deferred call could buy after the panel closed, and storing the display/panel
  to test visibility would itself be a use-after-free with no close gate whose
  call frequency is known.

### 16.2 The withdrawal (implementation)

- Removed: the shop hold state, the wrapper clone and its copy/release slots, the
  container/entry/campaign snapshot, the frame gate's replay call, the campaign
  guard, and every `dd_shop_raw`/`dd_shop_replay_ok` read. The adapter does not
  call `0xe18410` or the purchase callback `0xc30760` anywhere.
- `dd_shop_filter` (both filter IDs) identifies the binding **at the live click**
  only: primary wrapper vtable `0x11933a8` with mode byte `+0x300 == 0` (the
  `+0x70` binding) or the secondary `0x1193428`, plus `+0x70`'s vtable
  `0x117a678` (and, since 2026-10-31, the DLC page's `0x117a7c0`). Every other
  binding, a mode-1 `+0xd0` dispatch, non-iOS sources and controller-owned input
  pass unchanged.
- An identified click is withheld unless it is the game's own live dispatch and
  the contact qualifies: phase `PRESS` (the policy snapshot promotes a still
  finger after 0.5 s) or phase `RELEASED` with `now - down_ns >= 0.5 s`. One such
  click per contact is allowed; later clicks of the same contact are refused.
- A contact the frame gate saw cancelled, moved beyond slop, multi-finger or
  controller-taken is blocked for the rest of its generation, so the later lift
  click cannot buy either. All of this state is host-side (a generation number
  and two flags); no game pointer or game state is stored.
- Closed panel: the game can only dispatch the purchase callback through a live
  click on a live control; a control destroyed with its panel cannot dispatch,
  and the adapter never re-issues the call. A purchase after close is therefore
  impossible by construction, not by a heuristic.

### 16.3 Behaviour that remains (and its proof)

| Situation | Result |
| --- | --- |
| tap, or hold shorter than 0.5 s | focus only; no purchase (the touch-down click and the short lift click are both refused) |
| hold >= 0.5 s and release | the game's own lift click buys **once** (the native long-press release path) |
| a build that dispatches its click at Press (>= 0.5 s) | that one dispatch is allowed once |
| a build that only dispatches at touch-down | a hold buys nothing (fail-closed; no deferred call exists) |
| move > 8 px / second finger / cancel / controller takeover | nothing buys, including the later lift click |
| a hold with no game click at all | nothing buys; the adapter never calls the callback |
| ordinary inventory, empty slot, mode-1, Mac, policy off, old module | original behaviour |
| the DLC/Comet page | same rules as the Nomad page since 2026-10-31 (§14.2); the game decides price in shards and refuses an unaffordable row |

### 16.4 Tests run for this section

`dm/host/tests/t_dd_touch.c` was reworked around the queue-lifetime fixture
(each click is a fresh deep copy that is destroyed and poisoned after the call)
and the new shop suite: touch-down click withheld, no adapter call during a hold,
press click once, duplicate refused, lift after a press refused, tap refused,
long lift once, repeat refused, short lift refused, move/cancel/second-finger
refused (including their later lift clicks), withheld click leaves no game
pointer, and Comet/ordinary/empty/mode-1/Mac/controller/off unchanged.

`make -C dm/host/tests GAME=01008F1008DA6000 build/t_dd_touch && build/t_dd_touch`
→ **80 checks, 0 failed** (skill clones/releases still balanced 9/9). The full
suite, ThreadSanitizer, the Python rewriter tests and the iOS syntax check are
in the round-3 logs under `/private/tmp/dd-touch-20261030/`.

### 16.5 What is still unverified

- Device/GUI: that a 0.5 s hold and release buys exactly once with price,
  currency and stock changing only on success, and that a tap/short hold does
  not (isolated save; the audit's earlier acceptance list still applies).
- A build whose click is dispatched at touch-down only: a hold then buys
  nothing. This is the accepted cost of removing the deferred call.
- The 0.5 s instant itself does not buy on iOS unless the game dispatches then;
  the expected iPhone path is the release.

## 17. Fourth continuation: which event carries a Nomad click, and the MOD order claim (2026-10-30)

Read-only static work; no production code changed in this round (the shop policy
stays the lift-only one of section 16). `main` at
`6dcf9868582388173f81f4f02385cd4cdb125b3e`; no commit or push.

### 17.1 The gesture chain: what a live click is, and what a hold produces

Decoded from `main` (`ff2bf22565188d11ea0981ee0e2b53ce`):

- The input poll `0x74ac70` reads `nn::hid::GetGestureStates` (`0x74b58c`) and
  maps each SDK gesture type (`[x26+0x10]`) to an **internal event code** stored
  at `[sp,#0x28]`:
  - Tap (type 5) at `0x74b9a8`: single point only; attributes `[x26+0x30]` are
    tested for bit `0x100` (IsDoubleTap) at `0x74bc1c`, and the code is **3**
    (single) or **4** (double), stored at `0x74bc3c`.
  - Press (type 4) at `0x74b7a0` -> `0x74bcf8`: code **5** (`0x74bd24`), stored
    at `0x74bd50`; the handler only appends the pressed points to the local
    vector at `sp+0x30`.
  - Touch (type 3) at `0x74ba90` -> `0x74bc4c`: code **1** for a single point
    (`0x74bde4`), **6** for several (`0x74bde0`).
  - Cancel (type 2) at `0x74b684`: code **7**. Complete (type 1) sets no code.
- **Only the Tap codes 3/4 reach the click/pointer state.** At `0x74c238` the
  code is checked as `code-3 <= 1` (`sub w8,w8,#3; cmp w8,#1; b.hi 0x74c760`);
  codes 3/4 then update `main+0x27e0890/894` and the double-tap timer
  (`0x74bf24..30`) and append the tap position (`0x74a620`). The Press code 5
  takes the `0x74bcf8` path, which never writes the pointer, the timer or the
  click state.
- The pending click slots that the UI consumes (`[main+0x27e0600]`, byte code at
  +6/+0x10/+0x20 with the control ID at +8/+0x18/+0x28; consumed by `0x738eb0`
  at `0x738fb8..0x739108`, code must be `1`) are filled by **control code**, not
  by the poll. The producers decoded so far (`0x9651b0`, `0x965320`, `0x965460`,
  `0x965a00`, `0x96ff60`, `0x978950`, `0x9790e0`, `0x97b4c0`, `0x97b630`,
  `0x989a50`, `0x98be00`) all gate on `mode==1 || auto_flag==1` (the
  controller/keyboard path). The producer for touch (mode 0, auto 0) has **not**
  been located yet; this is the remaining static gap.
- `DM_CONTACT_PRESS` is a **host-side label only**: `dm_touch_contact_snapshot`
  promotes its own copy of a still contact to `DM_CONTACT_PRESS` after 0.5 s
  (`hle_touch.c`); the game never sees that field. The game only sees the
  `GestureState` stream the host recognizer writes (`gesture_fill`), where a
  still finger becomes Press after 0.5 s and the release of a Press becomes
  Complete, **not Tap**. So no click may be inferred from our PRESS label.

What the earlier dynamic evidence adds (section 13.3, Mac left button on the
town roster): a hold of 800 ms and its release ran the **primary** action
(`0xc61890` -> `0xc70430`) but not the double-only action (`0xc615b0`). That
gesture sequence is Press -> Complete, not Tap, so that primary call came from
the touch/pointer release path, not from a Tap. It is evidence that a hold's
release **can** dispatch the primary action; it is not proof for the Nomad
binding or for iOS, and the double-only action is never produced by a hold.

Consequence for the shop policy: the Nomad purchase is the **primary** binding
(`+0x70`), and the current policy allows exactly such a live dispatch once, on a
lift after `>=0.5 s`. If the device run shows the Nomad purchase click on a
hold's release, the policy works through the game's own click with no synthetic
call. That must be observed; it is not claimed from the label.

### 17.2 If the device shows no purchase on release: the minimal same-frame plan

Do not add this now. The plan below is what a later round would need; each item
has to be proven read-only first.

1. **Same-frame live target.** The grid rebuilds the two
   `InventoryButtonInGrid` wrappers every frame at `0xe17784..0xe177a8` inside
   `0xe171c0` (called by `0xe16370` at `0xe16e34`). At `0xe177a8` the new
   wrapper holds the vtable `0x11933a8`, the copied parameters and the mode/param
   word `+0x300/+0x304`, and `+0x70` is the purchase callback. An observation
   there can report, per frame, the slot parameter and whether the binding is the
   Nomad purchase, for the **currently live** control - no stored object.
2. **Same-frame hit.** The press must be associated with the control under the
   finger in the *same* frame: either the `0x738eb0` hit result for the widget
   whose wrapper is being built, or the grid's own hover state. This is the
   missing association also needed for the roster (15.2/17.1); no rectangle
   classifier is acceptable.
3. **Panel liveness.** Only an observed open state may authorize the call. The
   candidates are the `TrinketSupplyDisplay` destructors `0xc2fa50`/`0xc31070`
   (the deleting entry `0xc2fa50` starts with `stp x29,x30,[sp,#-0x20]!`,
   `0xa9be7bfd`, a valid observation site) and the panel's own close path. Before
   using them, a read-only run must show whether the display is rebuilt per frame
   (then the gate would invalidate every hold) or lives for the screen.
4. **The call itself** would be made inside that same frame's construction tick
   (after `0xe177a8`), on the live wrapper, once per contact, with the press and
   the same-frame hit re-checked; no clone, no cross-frame pointer, no stored
   container. That is the only shape this audit would accept as safe; it still
   needs a new filter/observation and a rebuilt prepared module.

If instead the native release click is confirmed on the device, none of this is
needed: the shipped lift-only policy already delivers the purchase through the
game's own click.

### 17.3 MOD order: the previous "load it after" instruction was not verified

`docs/darkest-dungeon-mod-1099001958-layout.md` and the compat module's README
claimed the module must be loaded **after** Inventory Expansion Lite "since the
later mod wins". That was a guess and is corrected:

- The host's `DM_ROMFS_OVERLAY` is a **file-tree overlay**, not a mod manager:
  `hle_fs.c` lists roots `:`-separated and **first root wins**; the launcher
  passes one root (`ModOverlay.swift` resolves `mods/`, `romfs/` or a project
  directory to the single root). Within a root a mod file simply replaces the
  container path (unit test `t_fs_mod.c`, expectation 1). The host has no
  per-mod priority at all.
- The **game** enumerates `mods/.*/project.xml` (`main+0x8c2b34`, `0x8c2b3c`)
  and reads each `mods/<id>/modfiles.txt` (`0x8c2e38`) at startup. The existing
  multimod run logs show the enumeration order `1099001958, 1172190166,
  840387268`, but the mod chosen for the shared
  `inventory/base.inventory.system_configs.darkest` differed between the two
  experiments: `priority-high-a/host.log:839` opened
  `mods/1099001958/...`, `priority-high-b/host.log:839` opened
  `mods/840387268/...`. So the game's own mod list/priority decides which mod's
  copy is read, not the host and not the folder enumeration.
- The **direction** of that list (first entry wins or last entry wins) is not
  established by any written result in this repository: `load_order\.json` is
  in `main` (`0xed8544`) and `load_order` as a JSON key at `0xebe257`, but no
  order file was found in the save or the overlay, and the `priority-high-a/b`
  and `ui-restart/order-a-first.png` artifacts do not state which position was
  the high one. No claim is made.

The compat document now says: the module overrides exactly one RomFS path and
only wins if the game reads it for that path, which the game's list decides.
Place it and check the trinket box; if unchanged, move it to the other end of the
list and check again (both reversible). The order-independent alternative is a
copy of Inventory Expansion Lite with that one file replaced (not built, not
run). Nothing was overwritten; the original mod and every game file are
unchanged.

## 18. Fifth continuation: the observer's real failure, the saved-slot proof, and B's open producer (2026-10-30)

Read-only analysis and one tool fix; no production code changed, no game started,
no commit or push. The primary agent's new run is at
`/private/tmp/dd-roster-followup-20261030/` (`result.md`, `trace/events.jsonl`,
`roster_saved_register.py`).

### 18.1 What the first observer actually did (the failure, recorded)

- The script imported only after `SBSymbolContextList.GetContext` was replaced by
  `GetContextAtIndex` (the temporary script did that); the version in
  `/private/tmp/dd-touch-20261030/` had the same bug and is now fixed.
- After the fix the preflight passed for real: the Host's module table gave the
  two Build IDs, `main: base 0x7002000000`, and all four original instruction
  words matched. One read-only breakpoint was installed at `main+0x73bc3c`.
- The run then produced **20 records, all errors**:
  `unwind: parent x24=0x0 is not an element (pc=0x7002c60084 attempts=…)`. The
  caller PC was exactly `0xc60084`, so the breakpoint did reach the roster
  element's dispatch, but `SBFrame.parent.FindRegister('x24')` returned 0: LLDB
  did not recover the callee-saved x24 across `0x73b6d0` (no debug info for this
  guest module, so its unwinder falls back to a heuristic). The callback
  correctly refused to treat 0 as an element, so **no hover/click data and no
  element identity were produced**. This was a script/tool failure, not a game
  observation; the game state was not written and no hold was claimed.

### 18.2 The prologue, proved, and the saved slot

`0x73b6d0` with entry `sp = S`:

| Instruction | Effect |
| --- | --- |
| `0x73b6d0 stp d11,d10,[sp,#-0x80]!` | sp = S-0x80 |
| `0x73b6d4 stp d9,d8,[sp,#0x10]` | S-0x70 |
| `0x73b6d8 stp x29,x30,[sp,#0x20]` | S-0x60 |
| `0x73b6dc add x29, sp, #0x20` | **x29 = S-0x60** |
| `0x73b6ec stp x22,x21,[sp,#0x60]` | S-0x20 |
| `0x73b6f0 stp x20,x19,[sp,#0x70]` | S-0x10 |
| `0x73b6f4 sub sp, sp, #0x4d0` | sp = S-0x550 |

- The caller's x24 is saved by `0x73b6e8 stp x24,x23,[sp,#0x50]` at
  S-0x30 = **x29+0x30**.
- The caller's sp at the call is S = **x29+0x60**, so the two callables are at
  **x29+0x100** (fnA, `sp+0xa0`) and **x29+0xd0** (fnB, `sp+0x70`).
- A scan of every instruction in `0x73b6d0..0x73bc3c` finds exactly one write to
  x29 (the prologue) and **no store whose address range covers x29+0x30**
  (including `stp`/`stnp` and the `sp+0x520` alias), so the saved slot is intact
  at `0x73bc3c`; the intervening calls preserve x29 by the ABI. This is the
  evidence the temporary fallback used; it is now the observer's primary path at
  that site instead of `parent.FindRegister`.

### 18.3 The replacement observer (runnable, bounded)

`/private/tmp/dd-touch-20261030/c_roster_hover_trace.py` (read-only, imports with
`command script import`):

- **BP1 `main+0xc60084`** (default): reads the *current* register `x24` as the
  element - no unwinding at all. Validates `[x24] == main+0x117c8d0`, the list
  `[x24+0x80]` against `main+0x117cfd0`, the element's index in the list vector,
  and reads `[x24+0x231]/[x24+0x3f8]/[x24+0x410]`, the widget at `sp+0x6a0`
  (flags `+0x90..+0x94`, `+0x50`, `+0x120`, name `+0x2bc`), the two callable
  vtables at `sp+0xa0`/`sp+0x70`, the game pointer `main+0x27e0890`, and the
  frame's action queue (`main+0x257e530` begin, `+0x538` end, 0x30 stride,
  callable `__f_` at +0x20) after this dispatch has pushed its actions. One
  record per element per second (`DM_HOVER_ALL=1` disables the dedupe).
- **BP2 `main+0x73bc3c`** (only with `DM_HOVER_MASK=1`, high frequency, short
  window): mask in the current `x24`, widget in `x20`, element from `[x29+0x30]`,
  callables from `x29+0x100`/`x29+0xd0`; records `hover`/`details` and the widget
  flags, throttled to one record per element per 250 ms or on a mask change.
- Preflight: module table (`GetContextAtIndex`), both Build IDs, `main: base`
  cross-check, the four words; per-site attempt caps (`DM_HOVER_ATTEMPTS`,
  default 20000), record cap (`DM_HOVER_LIMIT`, 240), wall-clock cap
  (`DM_HOVER_SECONDS`, 300); it disables only the breakpoints it created and
  writes a `stopped` record. Errors (invalid register, wrong vtable, element not
  in the list) are recorded explicitly, throttled to 20.

Run instruction: town with the isolated save, `DM_HOVER_MASK=1`, hold on the
right-side Dismas portrait without releasing for 1-2 s, then a single click, then
a double click, then lift. Expected: during the hold, BP2 records the same
element with `hover=1, details=0` each frame (stable pointer), BP1's
`queue_len` stays 0; on the double click BP2 shows `details=1` and BP1's queue
contains the `0x117cdc0` (`$_2`) callable. This has since been executed: the
third run (19.1) produced 242 records with zero errors and real elements, so the
saved-slot path is confirmed; the open question is the action authorization, not
the element record.

### 18.4 B: the mode-0 touch click producer is still not located

Established this round (static, same `main`):

- The poll's event-code mapping and the fact that **only Tap codes 3/4 reach the
  click/pointer state** (`0x74c238`, `code-3 <= 1`), while **Press code 5 only
  collects points** (`0x74bcf8`), remains as in 17.1.
- The pending click slots at `[main+0x27e0600]` are consumed by `0x738eb0`
  (code must be 1, payload = control id) and are written by control code; every
  producer decoded so far (`0x9651b0`, `0x965320`, `0x965460`, `0x965a00`,
  `0x96ff60`, `0x978950`, `0x9790e0`, `0x97b4c0`, `0x97b630`, `0x989a50`,
  `0x98be00`) gates on `mode==1 || auto_flag==1`, i.e. the controller/keyboard
  path. The `0x747a00` button state machine (0x747a00..0x748608) receives the
  control geometry, the fnA/fnB/fnD callables and their presence flags, and is
  the path that ran the roster's primary lambda on a Mac hold-release.

Not established: **which code or control state produces a touch (mode 0) click**,
and therefore whether a long press in the Nomad shop produces the same primary
call. The Mac roster hold-release evidence must not be used as iOS shop evidence;
the shop is a different control class (`InventoryButtonInGrid`) and its click was
not observed.

Next static step (no hook): trace the per-control input state table
`main+0x27dec28 + id*0xc` and the touch-event id `0x4000e1` the poll's state
machine writes (`0x74c4ac` `0x74ceb0`, field `+0x14 = 2`), and find the control
code that reads it for mode 0; alternatively instrument `0x747a00`'s state
comparisons for the roster's fnA call. Only after the touch producer and the
consumed event (TouchDown vs Release) are known can the shop's long-press path be
judged.

### 18.5 Four-task status (nothing here is acceptance)

| Task | Static/source | Compiled/unit | In a game | Next |
| --- | --- | --- | --- | --- |
| A Mac pointer | reviewed read-only (14.3) | launcher Swift tests run by the primary agent | primary agent's GUI | none from this side |
| B Nomad hold | lift-only policy; touch click producer not located | `t_dd_touch` 80/80 (round 3) | **not verified** | device/GUI release test; then 17.2/18.4 analysis |
| C roster hold | dispatcher mapping closed; hover anchor real since 19.1 | first run zero errors (19.1); callback comparison pending | **not verified** | run 19.4 callback comparison |
| D MOD layout | static hypothesis; compat module built | file evidence only | **not verified** | order-agnostic screen check |

D remains downgraded: the missing-key explanation is a hypothesis and the game's
list direction is not established, so no order is asserted. The two production
source files (`hle_dd_touch.c`, `t_dd_touch.c`) are frozen this round.

## 19. Sixth continuation: the third run's real data, script review, and the callback comparison (2026-10-30)

Read-only analysis and one new observer script; no production code changed, no
game started, no commit or push. Data:
`/private/tmp/dd-roster-third-20261030/result.md` and `trace/events.jsonl` (242
lines: 176 mask, 64 dispatch, 2 stop records; zero errors).

### 19.1 What the data proves, and what it refutes

- The saved-slot observation **works**: the element read at `[x29+0x30]` matches
  the direct dispatch read; the town's right-side list has two elements,
  Reynald `0x7008b7b800` (index 0) and Dismas `0x7008b7be00` (index 1), list
  `0x7005e94850`; both callable vtables are `main+0x117cd40` / `main+0x117cdc0`.
  No errors, no unwinding. **C now has a real, reusable hover anchor** (same
  live element + native hover), not a missing-element gap. This supersedes the
  candidate document's "no usable hold-target evidence" line, which describes
  only the failed follow-up before the saved-slot observer ran.
- `elem_3f8 == 0` on these interactive elements. The earlier proposed
  `[element+0x3f8] == 1` guard is **invalid** and was only ever recorded by the
  script; no production logic may adopt it.
- Mask counts over two elements per frame: `0x0` 120, `0x1` 54, `0x101` 2. With
  two elements, one hovered and one not, `0x1` on the hovered element and `0x0`
  on the other matches **bit 0 = hover** and the visible native tooltip. The two
  `0x101` records (bit 0 + bit 8) were on Dismas with the pointer at the same
  place (`1070,187`), one in each budget.
- `w90..w94 == 1` for **every** roster dispatch (176/176), `w50 == 0`,
  `w120 == 0`. The bit-8 branch of `0x73b6d0` gates on `[x20+0x91] & 1`, so for
  this control that gate is always open; the branch depends on the mask bit 8
  alone here.
- Every dispatch record has `queue_len == 0`, but the dispatch observer dedupes
  to one record per element per second, so those reads are **not in the same
  frame** as the `0x101` masks; `queue_len 0` there is not evidence that the
  bit-8 enqueue did not happen.

### 19.2 Script review (queue address, std::function offset, mask semantics)

- **Queue addresses and offsets are right**: the vector is `{begin at
  main+0x257e530, end at +0x538, capacity at +0x540}` (push at
  `0x73bc50..0x73bcc4`, drain at `0x8b5dc8..0x8b5e1c`), entry stride `0x30`, the
  callable pointer `__f_` at entry `+0x20` (`str x0,[x25,#0x20]` at `0x73bc7c`;
  the drain loads `ldur x0,[x20,#-0x10]`), and the callable's vtable at
  `[__f_]`. The read code is correct.
- **But the bit-8 enqueue has two paths**: for the roster's inline `$_2` the
  push is the **inline fast path** `0x73bc98..0x73bcb8` (it copies the callable
  into the queue entry and stores the new end at `0x73bcb8`); `0x717370` is only
  the *grow* path (`0x73bc90`). My earlier "push breakpoint at `0x73bc90`" was
  therefore wrong for the roster; the correct event site is **`0x73bcbc`**
  (reached after either path, and not reached when bit 8 is clear).
- **Mask semantics: labels are not facts.** `x24` at `0x73bc3c` is the packed
  `0x738eb0` result (48-bit masked at `0x73ba4c`). Bit 0 is hover (data above).
  Bit 8 is the first action bit tested (`0x73bc3c tbz w24,#8`), whose branch
  enqueues one of the two std::function arguments when `[widget+0x91]&1`.
  **Correction (20.1):** the callback trace shows that branch enqueues the
  **primary** (`$_1`, vtable `0x117cd40`, operator `0xc61890`); the earlier
  static reading "second argument / `$_2`" was wrong. The details callable
  (`$_2`, `0x117cdc0`, `0xc615b0`) is the *other* argument and the game enqueues
  it only on a genuine double. The two `0x101` records therefore mean
  "hovered + that action bit set", **not** "double/detail", until the callback
  trace proves the enqueue and the action.

### 19.3 Why this run's clickCount=2 did not open the details (hypothesis to test)

The earlier successful double (13.3) was observed with **event** breakpoints
only (`0xc61890`, `0xc615b0`, `0xc70430`, ...). This run kept a per-frame
breakpoint at `0x73bc3c` and took **1,367-1,491 traps per budget**; such
overhead can push the two clicks of a `clickCount=2` outside the game's 350 ms
double-tap window (or split them into two separate taps), which yields a
single-tap/primary path and no details. The data are consistent with that: the
0x101s are click-frame masks, but no details action was observed and the
momentary drag image fits a press/drag interpretation. This is a hypothesis;
the callback comparison below decides it, and no static label should be promoted
to a fact before then.

### 19.4 The lower-interference read-only callback comparison

`/private/tmp/dd-touch-20261030/c_roster_callback_compare.py` (new, event-only,
no per-frame breakpoint):

| BP | Site | Meaning |
| --- | --- | --- |
| `details` | `main+0xc615b0` (`0xd10283ff`) | `$_2` entry: `x0` lambda, `[x0+8]` element, `x30` caller return (recorded; the earlier double's caller was `0x8b9d28`, **not** the drain's `0x8b5df4` - that discrepancy is part of what must be reconciled) |
| `primary` | `main+0xc61890` (`0xa9be7bfd`) | `$_1` entry: element and caller (the earlier trace's caller was `0x8b9d28`; recorded, not assumed) |
| `enqueue` | `main+0x73bcbc` (`0xf000f208`) | after the bit-8 enqueue: `x24` mask, `x20` widget, element at `[x29+0x30]`, same-frame queue length and vtables |

Preflight uses `GetContextAtIndex`, both Build IDs, the base cross-check and the
seven words above; caps are 200 records, 3000 attempts/site, 180 s; only its own
breakpoints are disabled; errors are explicit.

Run in one session, no per-frame observer: hover, single click, **two separate
clicks 100-150 ms apart**, a native double click (`clickCount=2`), and
hold+release. Expected comparison: a genuine double shows `enqueue` with
`queue_len 1` and a `0x117cdc0` entry, then `details`, and the panel opens; a
single click shows `primary` only; hold+release shows which of the two actually
fires. Record the `caller` offsets in every case: the earlier double's `c615b0`
came from `0x8b9d28`, while the action queue's drain calls at `0x8b5df4`, so the
caller itself tells whether the details action came from the bit-8 enqueue or
from the `0x747a00`/`0x8b97c0` path. If the two separate clicks also fail to open
the details, the problem is not the observer timing and the bit-8/`$_2` chain
must be re-read from the original instructions.

### 19.5 Status after this round

| Task | State | Evidence |
| --- | --- | --- |
| A Mac pointer | unchanged (reviewed, primary agent GUI) | 14.3 |
| B Nomad hold | lift-only policy; mode-0 touch click producer still not located; no acceptance | 17.1/18.4; device/gui pending |
| C roster hold | **hover anchor real** (element/list/index + mask bit 0 + native tooltip); action authorization not established; no hook | 19.1, callback comparison pending |
| D MOD layout | downgraded hypothesis + compat candidate; no order guess | 15.3/17.3 |

No production hook was added; the two production sources stay frozen; the
earlier "bit 8 = details/double" wording is withdrawn pending the callback
comparison.

## 20. Seventh continuation: corrected roster binding and the implemented long-press details action (2026-10-30)

New real data: `/private/tmp/dd-roster-callback-20261030/result.md` and
`trace/events.jsonl` (three event breakpoints only, actual main/SDK and seven
words verified, 7 valid events, zero errors). Implementation added to
`dm/host/hle_dd_touch.c`, `dm/host/dm.h`,
`dm/games/01008F1008DA6000/patches.py` and `dm/host/tests/t_dd_touch.c`. No App or
IPA was built, no commit/branch/push, and the primary agent's Swift files were
not touched.

### 20.1 The observed binding (supersedes the earlier static labels)

The callback comparison recorded:

| Input | 0x73bcbc enqueue | callbacks (caller) |
| --- | --- | --- |
| single click | mask `0x101`, queued callable vtable **`0x117cd40`** | `c61890` (caller `0x8b5df4`) |
| genuine double | (same primary) | `c61890` then `c615b0`, both caller `0x8b5df4` |
| hold 900 ms | (primary only) | `c61890`, no `c615b0` |

So the bit-8 branch of `0x73b6d0` enqueues the **primary** (`$_1`, vtable
`0x117cd40`, operator `0xc61890`), not `$_2`. The earlier reading of the
std::function parameter order (bit 8 -> the second argument / `$_2`) is
withdrawn. The details action is `$_2` (vtable `0x117cdc0`, operator `0xc615b0`,
`0xcb59a0` -> `ShowCharacterDisplay`); the game enqueues it only for a genuine
double, and the drain calls it with the same caller (`0x8b5df4`).

The stack mapping now used (and verified dynamically by the vtables): the
primary function object is at the roster frame's `sp+0xa0`, the details at
`sp+0x70` (vtable `0x117cdc0`, inline `__f_` at `+0x20` pointing to itself,
captured element at `+8`). **Correction (21.1):** those `sp` offsets are the
*roster* frame's; at the observation at `0xc60084` the register `x29` is the
roster frame's `x29 = S-0x60`, so the current sp is `x29-0xa50`, the primary is
`x29-0x9b0` and the details `x29-0x9e0`. The earlier `x29+0x100`/`x29+0xd0`
reading applied to `0x73b6d0`'s inner frame and was used with the outer `x29`:
wrong, fixed in 21.1.

### 20.2 The queue ABI and clone ownership (verified)

- `0x717370` is `std::vector<std::function<void()>>::push_back(vector*, const
  std::function*)`: it clones the argument through the callable's vtable `+0x10`
  (heap target) or copies it inline through `+0x18`, sets the new entry's `__f_`
  at `+0x20` (inline: to the entry itself), returns the **new end**
  (`0x717528 mov x0,x20`), and leaves the source function untouched.
- The drain (`0x8b5dc8..0x8b5e1c`) walks the vector (`0x30` stride, `__f_` at
  `+0x20`), calls `vtable+0x30` on each callable, then destroys every entry
  (`vtable+0x20` for inline, `+0x28` for heap) and clears the vector. The queue
  therefore owns a clone of what the adapter appends; no game object is stored
  across frames.

### 20.3 Implementation: one native details action per held contact

- **New observation**: `OBS_DD_ROSTER_CLICK = 28` at `main+0xc60084`
  (`ldr x0,[sp,#0x90]`, `0xf9404be0`), the instruction after the roster
  element's dispatch. It runs once per visible roster element per frame (two in
  the isolated town), not per control. The rewriter accepts it as "right after a
  `bl`" (`0xc60080` is `bl 0x73b6d0`, word `0x97eb6d94`, opcode `0x25`), which
  is the site class where x9-x17 are dead after the call; the gate restores
  x0-x30 (except x18) after the callback, so the nested guest push cannot
  disturb the caller's post-call state.
- `dd_roster_click` (iOS only, `DM_DD_TOUCH_POLICY` on, prepared module with
  OBS 28, `0x73b6d0` prologue, the push helper word, both operator slots):
  1. snapshot: `DM_CONTACT_IOS`, pointer owner (`mode==0`, auto flag clear),
     single finger (or a release), phase `PRESS` or `RELEASED` with
     `now - down_ns >= 0.5 s`, not a blocked generation (cancelled/moved/
     multi-finger/controller-taken), not already fired for this contact;
  2. live target: element = `x24` with vtable `0x117c8d0`, its list
     (`[element+0x80]`) with vtable `0x117cfd0`, element found in the list
     vector (stride `0x40`), details function at `x29+0xd0` with vtable
     `0x117cdc0`, inline `__f_`, captured element equal; **the `0x3f8` byte is
     not a guard**;
  3. same-frame click confirmation: the queue's **last** entry is the primary
     (`__f_` vtable `0x117cd40`, captured element = this element) - i.e. the
     game just queued this element's click - and no entry is already the details
     (a native double), otherwise nothing is appended;
  4. append once with the game's own `0x717370(queue, details_function)`, which
     clones it; the normal drain later calls `0xc615b0` (the original action).
- No double-tap flag is written, `CharacterDisplay`'s toggle is not called, and
  no UI function is invoked directly; the adapter only appends to the game's
  queue. A cancelled/moved/second-fingered/controller-owned contact, a Mac
  (`DM_CONTACT_MAC_LEFT`) source, the policy off, or an old module without OBS
  28 append nothing (fail closed). The Mac behavior is therefore unchanged; an
  explicit decision would be needed to enable any Mac policy.
- Costs/risks recorded: the append happens on the game's last click of the
  contact (press or lift, whichever is >=0.5 s), so on this build it is the lift;
  the order is primary then details (matching the double); the helper allocates
  a clone inside the observation (guest code from a gate is already used by the
  skill replay; the gate restores x0-x30).

### 20.4 Tests

`dm/host/tests/t_dd_touch.c` now drives the adapter's observation with a fake
live frame/queue and the game's push semantics (inline clone, `__f_` at +0x20,
new end): append once and queue grows by one, the entry is the details callable
for the element, one action per contact, a fake drain runs the primary and the
details once, tap/shorter hold append nothing, a long lift appends once, and no
append for an empty queue, another element's primary, a details already queued,
an unverified details callable, an unverified element, cancel, Mac source,
controller ownership or the policy off.

`make -C dm/host/tests GAME=01008F1008DA6000 build/t_dd_touch && build/t_dd_touch`
-> **96 checks, 0 failed**. Full suite, ThreadSanitizer, the Python rewriter
tests and the iOS syntax check are in the round-4 logs under
`/private/tmp/dd-touch-20261030/`.

### 20.5 Status

| Task | State |
| --- | --- |
| A Mac pointer | unchanged; primary agent's GUI |
| B Nomad hold | lift-only policy unchanged; touch click producer still open; no acceptance |
| C roster hold | **implemented** (source + unit tests); device/GUI acceptance pending; requires a rebuilt prepared module (OBS 28) and Host |
| D MOD layout | downgraded candidate; no order claim |

The same-frame hit confirmation deserves its exact wording: the adapter does
**not** read the 0x738eb0 hover bit in production (that would need a per-control
gate). The confirmation is the game's own click on the element: the queue's last
entry is this element's primary, which the game enqueues only for a clicked
control (the earlier run's click masks were `0x101`, i.e. hover + that action
bit). The element/list/function identities are re-checked in the same frame.

Source files changed in this round (for the primary agent's rebuild, not packed
here): `dm/host/hle_dd_touch.c`, `dm/host/dm.h`,
`dm/games/01008F1008DA6000/patches.py`, `dm/host/tests/t_dd_touch.c`, and the
user-facing note of the existing `DM_DD_TOUCH_POLICY` row in
`dm/games/settings.tsv` (text only; the row's semantics are unchanged).

## 21. Eighth continuation: the two blocking bugs, the Mac path and the gate contract (2026-10-30)

Review found two certain blockers in the section 20 implementation. Both are
fixed, the fixture is rebuilt on the real frame, the Mac long press is
implemented, and the gate/thread contract is recorded. No App/IPA was built, no
commit/branch/push, and the primary agent's Swift files were not touched.

### 21.1 The bugs and the fixes

**Bug 1 - wrong frame register.** The observation at `0xc60084` runs inside
`PreChildrenShowInternal` (`0xc5c6c0`), not inside `0x73b6d0`. The register
`x29` there is the roster frame's: `stp d11,d10,[sp,#-0x80]!` (sp = S-0x80),
`add x29,sp,#0x20` (x29 = S-0x60), `sub sp,sp,#0xa30` (sp = S-0xab0), so
**sp = x29-0xa50**. The two std::function objects are at that `sp+0xa0`
(primary, `x29-0x9b0`) and `sp+0x70` (details, `x29-0x9e0`). The section 20
implementation used `x29+0xd0`, which points into the caller's stack; the test
fixture had placed the same wrong object there, so the 96 checks were a false
positive. Fixed `dd_roster_click` to `sp = fp - 0xa50`, details at `sp+0x70`,
primary at `sp+0xa0`, both verified (vtable, inline `__f_`, captured element);
the frame prologue words are validated at init (`0xc5c6c0 6db82beb`,
`0xc5c6c8 a9027bfd`, `0xc5c6cc 910083fd`, `0xc5c6e4 d128c3ff`). The fixture now
allocates the real frame (`fsp`, `fp = fsp+0xa50`), puts the real objects at
`sp+0x70`/`sp+0xa0`, a decoy at the old `fp+0xd0`, and adds a rejection test: a
valid-looking details callable only at the old offset must append nothing.

**Bug 2 - the init checked the rewritten hook.** `dd_instruction(0xc60084,
0xf9404be0)` reads the runtime word; a prepared module replaces it with a branch
to the gate, so the roster was always refused. Fixed: the roster validation uses
`gate_obs_present(OBS_DD_ROSTER_CLICK)` plus the two neighbouring, unpatched
instructions (`0xc60080 97eb6d94` = `bl 0x73b6d0`, `0xc60088 eb14001f` = `cmp
x0,x20`), the frame prologue, `0x73b6d0`'s prologue, the push helper and the two
operator slots. A new `dd_test_validate()` runs the same `dd_validate()` and the
test now exercises a prepared-like module: 0xc60084 is written as a gate branch
and must be accepted; a changed neighbour, a changed prologue, a missing OBS 28
or a changed operator slot must be refused. The behavior tests still use the
shortcut `dd_test_init`, but the prepared-module path is no longer only asserted.

**Bug 3 - Mac.** The Mac path no longer returns early. `dd_validate()` now
computes a common core (main/sdk image, the frame observation), the roster
availability, and the iOS-only skill/shop bindings; `dd_init()` on Mac calls
`dm_touch_policy_activate(0)` (the iOS gesture policy stays off, so the Mac
touch/gesture stream and the pointer bridge are unchanged) and logs the roster
state. `dd_roster_click` accepts `DM_CONTACT_IOS` and `DM_CONTACT_MAC_LEFT` (the
only Mac button the front publishes as a touch; right/middle are HID and never a
contact), reads mode/auto only, and the frame tick's ownership/blocked
bookkeeping treats the Mac left source like the iOS one so a Mac contact is not
falsely marked blocked. The skill and shop callbacks still require
`DM_CONTACT_IOS`, so they are inert on Mac; `dd_camp`/`dd_shop` are 0 there and
only the roster reports enabled.

**Bug 4 - hold-release semantics.** The append happens only when the game
dispatches its primary click for the element. On this build that dispatch is the
lift, so the details opens on the **release** after >=0.5 s, not at the 0.5 s
instant during the hold; a build that dispatches a click at 0.5 s would open it
then. The audit and the settings note now say "hold then release" and do not
claim a mid-hold trigger.

**Bug 5 - gate, TLS and stack contract.** `entry.S` `_dm_gate` saves x0-x30,
calls `gate_dispatch`, then restores every general register except x18 (the
Apple platform register; the guest's x18 thread slot is deliberately left
alone), plus FP/SIMD and NZCV/FPSR/FPCR. The C callback therefore runs on the
guest thread with the guest's x18 and a 16-byte aligned stack; the nested guest
call to `0x717370` uses the same thread and x18, its own SVCs reach the same
gate table by return address, and the adapter drops its mutex before the call,
so no guest code runs under it. This is the same call class the skill policy
already uses (`0xe39fe0` from OBS 25).

### 21.2 Tests (round 5)

`dm/host/tests/t_dd_touch.c`: **104 checks, 0 failed** (new: six
prepared-module validation checks, the old-offset decoy rejection, the Mac left
hold, plus the corrected real-frame fixture). Full suite (all binaries) exit 0;
ThreadSanitizer exit 0; the 19 Python rewriter tests OK; the iOS arm64 syntax
check and the macOS host syntax check both exit 0. Logs:
`/private/tmp/dd-touch-20261030/{host-tests,tsan,python-tests,ios-syntax}-round5.log`.

### 21.3 Status

| Task | State |
| --- | --- |
| A Mac pointer | unchanged; primary agent's GUI |
| B Nomad hold | lift-only policy unchanged; touch click producer still open; no acceptance |
| C roster hold | implemented for **Mac and iOS** (Mac left button, iOS touch), unit-tested on the real frame; device/GUI acceptance pending; needs a prepared module with OBS 28 and a rebuilt Host |
| D MOD layout | downgraded candidate; no order claim |

The prepared module and the Host must be rebuilt before the GUI check; the
previous candidate package does not contain OBS 28 or this fix. No final App/IPA
was built here.

## 22. Ninth continuation: a same-frame cancellation+release, confirmed and latched (2026-10-30)

The independent round-5 build started and proved the Mac/iOS initialization on
real hardware (log: Mac roster enabled, iOS skills/shop inactive, PointerBridge
enabled). This round reviews one compatibility risk only; no game was run, no
App/IPA was built, no commit/branch/push.

### 22.1 The risk, confirmed by tests first

`touch_publish` set `g_contact.phase = DM_CONTACT_CANCELLED` for a move, a
second finger, a changed id or an explicit cancel, but a zero-point release in
the same frame then set it to `DM_CONTACT_RELEASED` without starting a new
generation. The only record of the bad contact the policies had was
`dd_blocked_generation`, set by the frame tick (OBS 25); when the release
happened before the next frame tick, the shop's lift branch and the roster's
release branch saw a clean release and allowed the action.

Six new adapter tests reproduce it, with no `dd_test_frame` between the
cancellation and the release: for the shop and the roster, move+up, cancel+up,
and two fingers+all-up. Before the fix all six failed (the shop bought, the
roster appended); one existing shop state check also failed because the extra
purchases moved its absolute counters. After the fix all pass.

### 22.2 The fix

- `hle_touch.c` `touch_publish`: a zero-point release no longer overwrites
  `DM_CONTACT_CANCELLED`; the cancellation stays latched for the rest of the
  generation and a fresh contact (new generation) clears it. Only
  `g_contact.phase` changes. The game's touch/gesture states (`g_f`, `g_gf` and
  the emitted GestureStates) are written by the same function below the phase
  assignment and are untouched; the gesture code already ignores a CANCELLED
  contact and a release with count 0, so its output is unchanged (the gesture
  test binary passes).
- `hle_dd_touch.c`: the roster comment said "every non-iOS source refused",
  which contradicts the implemented Mac left-button support; corrected to "a
  source other than the iPhone touch or the Mac left button".

No ABI offset, gate, profile or Swift file changed. The prepared main from
round 5 (OBS 28) is unchanged this round.

### 22.3 Compatibility

The contact snapshot is consumed only by the Darkest Dungeon adapter
(`hle_dd_touch.c`; grep finds no other reader besides the tests), so other games
keep the same touch and gesture states. The latch only makes the opt-in
policies stricter (a release after a bad contact is refused); with the setting
off nothing reads the snapshot phase. The shop's and skill's one-shot state and
the roster's one-append-per-generation behaviour are unchanged.

### 22.4 Tests and handoff

- `t_dd_touch`: **110 checks, 0 failed** (the six same-frame checks included).
- Full suite exit 0; ThreadSanitizer exit 0; the 19 Python rewriter tests OK;
  iOS arm64 and macOS host syntax checks exit 0. Logs:
  `/private/tmp/dd-touch-20261030/{host-tests,tsan,python-tests,ios-syntax}-round6.log`.
- Source changed: `dm/host/hle_touch.c` (the latch), `dm/host/hle_dd_touch.c`
  (comment only), `dm/host/tests/t_dd_touch.c` (the same-frame tests). The Host
  must be rebuilt; the prepared main (OBS 28) from round 5 needs no change.
- GUI check: a move, second finger or cancel followed quickly by a lift (before
  the next frame) must not buy or open the details; a clean hold+release still
  performs exactly one action.

## 23. Primary integration and user acceptance (2026-10-30)

After the round-5 frame-layout and prepared-gate fixes, the primary built a new
Mac Host and rewrote main into `/private/tmp/dd-roster-verify-round5/`, leaving
existing distributed Apps/IPA files untouched. `host-bundled.log` confirms the
roster capability enabled, Mouse Pointer Bridge enabled, and iOS skill/shop
policies inactive on Mac. The temporary runner used a separate copy of the town
fixture, not a personal save. The user subsequently reported that long-press was
working. Record this as **user-reported acceptance in the current Mac test
context**, not an automated iPhone test or a full regression of all targets.
No repeat of this accepted clean-hold interaction is required.

The final contact-cancellation fix in section 22 changes only policy snapshot
metadata. The primary reran the full Host test suite (exit 0), 110 touch-policy
checks, TSan (exit 0), the 19 entry-filter/patch/spin tests (all passed), and the
shared launcher settings checks (passed). Logs are
`/private/tmp/dd-input-unified-round6.log`, `/private/tmp/dd-tsan-unified-round6.log`,
`/private/tmp/dd-input-patches-round6.log` and
`/private/tmp/dd-settings-unified-round6.log`.

Delivery uses a new directory:
`/Volumes/MacData/game/darkest-dungeon/deliver-roster-hold-20261030/`.
Its manifest records exact paths, sizes, hashes, signing status and limitations.
The prepared main must include OBS 28 at original offset `0xc60084`, alongside
the existing pointer gate and skill/shop filters. The Host must be rebuilt after
the cancellation fix; the older input-candidate package is not this delivery.

Remaining boundaries:

- Mac launcher export of both Mouse HID and DD pointer options is tested; this
  round does not establish button-free hover acceptance on all four UI classes.
- Ordinary Nomad hold-release buying is still a candidate: the original live
  purchase callback is permitted once for a qualifying contact, but iOS gameplay
  dispatch has not been verified. No delayed purchase replay remains.
- Comet/DLC shop behavior remains original. No broad inventory click filter was
  introduced for unverified classes.
- Right-side town portrait hold-release is implemented for Mac left contacts and
  iOS touch; the iPhone end-to-end interaction still needs user acceptance.
- MOD 1099001958 key completion is a separate, reversible, unverified compatibility
  candidate. It is not bundled into the App/IPA, and no original MOD is overwritten.
- No branch, commit, merge or push was made. HEAD remains
  `6dcf9868582388173f81f4f02385cd4cdb125b3e`; existing work remains uncommitted.

## 24. Tenth continuation: the Nomad click's producer, and the recognizer fix (2026-10-30)

Read-only work on the same `main` (`ff2bf22565188d11ea0981ee0e2b53ce`) and one
host change in `dm/host/hle_touch.c`. No gate, patch, ABI or prepared module
changed, no App/IPA was built, no commit/branch/push.

### 24.1 The click chain in the original instructions

| Site | What it does |
| --- | --- |
| `0x74ac70` poll | reads the pads (`0x74adb4`..`0x74b090`) and `nn::hid::GetGestureStates` (`0x74b58c`); before that, clears the three pending click slots of `[main+0x27e0600]` every frame (`0x74b554..0x74b57c`: code byte, payload pointer at `+8`, and the same at `+0x10/+0x18`, `+0x20/+0x28`) |
| `0x74b9a8` / `0x74b7a0` / `0x74ba90` / `0x74b684` | gesture type → internal code: Tap 3 (4 if `attributes & 0x100`), Press 5, Touch 1 (6 for several), Cancel 7 |
| `0x74c238` Tap path | `code-3 <= 1`; stores the tap point at `main+0x27e0890/894` and appends it, then `0x74c7d4` (with `main+0x27e07f4 == 1`, the touch-pointer mode) sets the pointer's **click** state `main+0x27e0901 = 2` (`0x74c810`; the second point sets `0x27e0903`, `0x74c818`) |
| `0x74c484` Press path | sets `main+0x27e0901 = 3` (`0x74c490`) - the **drag** state - and dispatches the UI event `0x4000e1` with payload type 2 (`0x74c4ac..0x74c4b8`); the `0x74c7d4` block then clears that state for code 5 (`0x74c828`) in the touch-pointer mode |
| `0x8f644c` consumer | `main+0x27e0901 == 3` → the hold/drag flag `main+0x257e70e` (and `+0x70f = state & 1`); `== 2` → the **one-shot** click pulse `main+0x257e710`, which also clears `main+0x27e0901` (`0x8f65c0..0x8f65dc`) |
| `0xe156b4` | the shop control calls its click callable `[control+0x1d0]` (`ldr x8,[x0]; ldr x8,[x8,#0x30]; blr x8`) only when the interaction query's flag byte is set |
| `0xe134fc` | that query: a by-pointer call fills a result struct at `sp+0x540`, whose byte at `sp+0x580` is copied to the flag at `[x29-0x58]` and tested at `0xe15694` |
| `0x73c780 → 0x73bf90 → 0x738eb0` | the query itself. The click byte (`w20`) is set only when a pending slot at `[main+0x27e0600]` has `+6 == 1` and its node id at `+8` equals the control's (`0x738fb8..0x738fdc`); hover is byte 0 |
| slot producers | `0x9652ac`, `0x965418`, `0x971fd0`, `0x978fd0`, `0x979220`, `0x97a750`, `0x97b5f4`, `0x97d2d8`, `0x983690`, `0x989c84`, `0x98c3b0`, `0x98ec5c`, `0xd4a0b0`, `0x8e8514/30/4c` - the controller/keyboard navigation producers the earlier rounds found gated on `mode==1`; the touch-mode route is the pointer state above |

In the pointer model the only thing a touch ever turns into a click is the
one-shot pulse a Tap sets. A still finger becomes Press (code 5), which this
build turns into the hold/drag state and never into that pulse, and the release
of a Press is Complete (no code at all). The control side has the same shape: its
click callable runs only when its own interaction query reports a click
(`0x738fb8`), and the click slots that query reads are cleared each poll while
the producers identified so far are the controller/keyboard ones.

### 24.2 Why the lift-only policy could not fire

The host recognizer is what made a hold a Press (yuzu's rule; Horizon does the
same), so on iOS a >=0.5 s contact produced Press → Complete: no Tap, no click.
`dd_shop_filter`'s lift branch therefore could never run, while its refusal of
the contact's *only* click - the short tap's - left the Nomad shop unable to buy
at all. Both of its branches were unreachable for the contact they were written
for; the withholding was not harmful to the game's data, but the feature was
inert.

### 24.3 The fix that was tried and withdrawn (2026-10-30, not accepted)

**Withdrawn in 25.2.** `hle_touch.c` briefly made `dm_touch_policy_activate`
set a second flag, `g_gesture_hold_tap`, which stopped a still single finger
from being promoted to Press in the gesture history, so its release became a
Tap. A moving finger was still a Pan.

That changed `nn::hid::GetGestureStates` for **every** control in the game for
as long as the policy was on, not only the Nomad merchandise: the review
rejected it because a title-level switch is not a licence to widen a behaviour
past the one control the user asked about. The flag, its two branches, the eight
`t_gesture` checks that exercised it and the settings text that described it are
removed; `dm_touch_policy_activate` again only sets the contact-snapshot mode,
and the gesture history is untouched for every title. What remains from this
round is the static map in 24.1/24.2 and the bounded design in 25.

### 24.4 Boundaries

- 24.3 was withdrawn before any device run; there is no iPhone result for it.
  The round-7 claim that the lift branch had become reachable is void.
- The static map below still holds: a still finger is a Press, a Press makes no
  click, so on iOS a >=0.5 s contact still cannot buy.
- `dd_pointer_owner()` reads the mode `main+0x27dee2c` and `main+0x27dec24`. The
  poll's debounced writer (`0x74b500..0x74b530`) derives the latter from
  `(mode != 2) | byte[0xb17ec444]`; its runtime value should be recorded if a
  future Nomad rule ever fails to engage.
- The round-5 prepared module (OBS 28) and the round-6 Host latching are
  unaffected by the withdrawal: no rewriter entry, no ABI and no OBS number
  changed, and only `hle_touch.c`, `t_gesture.c` and one settings string were
  touched.

### 24.5 Four-task status

| Task | State |
| --- | --- |
| A Mac pointer | unchanged; primary agent's GUI |
| B Nomad hold | static click chain closed (24.1/24.2); round-7 recognizer change **withdrawn**; bounded same-frame design and its read-only probe in 25; **no implementation, nothing accepted** |
| C roster hold | unchanged this round; user-reported Mac acceptance stands (23) |
| D MOD layout | unchanged, still a downgraded candidate |

Tests this round: `t_gesture` 51 checks, 0 failed (eight new: the opt-in mode
and its removal); `t_dd_touch` 110 checks, 0 failed; the full host suite, the
ThreadSanitizer binary and the Python rewriter tests are in
`/private/tmp/dd-b-round7/`.

## 25. Eleventh continuation: the withdrawn broad change and the bounded Nomad design (2026-10-30)

Read-only analysis on the same retail `main`
(`ff2bf22565188d11ea0981ee0e2b53ce`, `sdk b33804825108340e4cad9d080a636a3f`),
one withdrawal in the Host and one new read-only probe script. No gate, patch,
OBS number, ABI or prepared module changed; no App/IPA was built; no commit,
branch or push.

### 25.1 The review's scope

The user's request is a long press on **one** Nomad merchandise row. The review
rejected the round-7 approach for two reasons:

1. it changed `nn::hid::GetGestureStates` for the whole game while the policy was
   on, so every panel in this title saw a different gesture stream, not only the
   shop;
2. it treated the opt-in switch as permission to widen the behaviour, which it
   is not.

A rule that is on for "this title" is not a rule that is scoped to "this control
under this finger". What follows is the design that is scoped that way, and the
observation that has to settle it before any code is written.

### 25.2 The withdrawal, exactly

Removed from `dm/host/hle_touch.c`: the `g_gesture_hold_tap` flag, its
assignment in `dm_touch_policy_activate`, and the two conditions that skipped
the Press step in `gesture_sample` (`if (!upd && !g_gesture_hold_tap && ...)` and
`} else if (ltype == GT_TOUCH && !g_gesture_hold_tap) type = GT_PRESS;`). The
comment added beside the gesture history and the one in
`dm_touch_policy_activate` went back to their round-6 form, which now states the
limited effect explicitly.

Removed from `dm/host/tests/t_gesture.c`: the declaration of
`dm_touch_policy_activate`, the two test blocks ("hold-tap mode" and "policy off
again", eight checks) and the extra three reads they needed. The file is byte
identical to HEAD again.

Restored in `dm/games/settings.tsv`: the round-6 wording of the Nomad sentence
("short tap focuses; the game's own click after a 0.5 s hold is allowed"), so no
success is claimed for the withdrawn behaviour.

Kept unchanged: round-6's cancellation metadata latching (`g_gcancel`, the
cancel entry, the contact phase), the contact snapshot's Press promotion, all of
`hle_dd_touch.c`'s filters, the roster work (23) and its tests.

Re-run after the withdrawal: `t_gesture` 43 checks, 0 failed (the pre-round-7
count); `t_dd_touch` 110 checks, 0 failed (cases 3 and 4 still exercise the shop
filter's refusal and its one-shot permission through the contact snapshot, not
through the gesture stream).

### 25.3 The chain, from the retail instructions

Two facts are new since 24.1 and both matter for a bounded rule.

**(a) The click is a one-shot event addressed by node id, not a per-control
flag.** `[main+0x27e0600]` holds a pointer to a 0x30-byte struct (allocated once
at startup, `0x1e2e20` stores it). Its fields, as the code uses them:

| Offset | Use |
| --- | --- |
| `+0x00`, `+0x02` | header bytes |
| `+0x03`, `+0x04`, `+0x05` | the controller/keyboard producers' flags, mapped to `main+0x257e70b..70d` by `0x8f62ec..0x8f6440` |
| `+0x06`, `+0x08` | kind **1 = click**, and the target's node id |
| `+0x10`, `+0x18` | second kind and node |
| `+0x20`, `+0x28` | third kind and node |

The poll clears all three pairs every frame (`0x74b554..0x74b57c`, right before
`nn::hid::GetGestureStates` at `0x74b58c`). The consumer is the target's own
query: at `0x738fb8..0x738fdc`, if `ev->+8 == x26` (the control's first field,
passed in as the query's identity) **and** `ev->+6 == 1`, then `ev->+6 = 0`,
`w20 = 1` (the click bit) and `ev->+8 = 0` - consumed, once. There is no hover
test in that comparison: the click branch trusts whoever addressed the event.

**(b) The Nomad item builds its wrapper and queries in the same call.**
`0xe16370` (the grid, called from `TrinketSupplyDisplay::PreChildrenShowInternal`
at `0xc2fdbc`) calls `0xe171c0` at `0xe16e34`. Inside it, `0xe17780`/`0xe177d0`
allocate the two `0x310`-byte wrappers, `0xe17c20` copies the grid parameters,
`0xe177a8`/`0xe1780c` store the mode/parameter word at `+0x300`/`+0x308`, and
then `0xe1788c` calls `0xe13120` for that item - still inside the same call, no
frame boundary. Inside `0xe13120`:

| Site | What it does |
| --- | --- |
| `0xe134d0` | presets the click byte `[x29-0x58] = 1` and its neighbour `0` |
| `0xe134d8` | `cbz x0` - no interaction provider means the preset stands |
| `0xe134fc` | `x0->vtable[0x30](sret = sp+0x540, &[x26], &x21)` - the item's own query, which runs `0x738eb0` |
| `0xe13500..0xe13534` | the result is copied to `[x29-0x98] .. [x29-0x58]` (click byte = result `+0x40`) |
| `0xe15690` | `ldurb w8,[x29,#-0x58]`, `tbz w8,#0` |
| `0xe15698` | `ldr x0,[x26,#0x1d0]` - the click callable is the wrapper just built |
| `0xe156b4` | `ldr x8,[x0]; ldr x8,[x8,#0x30]; blr x8` with `x1 = sp+0x540`, `x2 = sp+0xf0` |

The vtables, read from the image:

| Vtable | Slot `+0x30` | Identity |
| --- | --- | --- |
| `0x11933a8` | `0xe18410` | `InventoryButtonInGrid::$_0`, the primary wrapper |
| `0x1193428` | `0xe181f0` | `InventoryButtonInGrid::$_1`, the secondary wrapper |
| `0x117a678` | `0xc30760` | `TrinketSupplyDisplay::PreChildrenShowInternal()::$_1`, the purchase |
| `0x117a7c0` | `0xc31e00` | Comet's own callable, a different class |

So the game's own click for a Nomad row is exactly:
query bit → `0xe156b4` → wrapper slot `0x30` → `0xe18410` → `[wrapper+0x70]`
(vtable `0x117a678`) → `0xc30760`. The filter that already exists at `0xe18410`
sits on the fourth link, which is why it can allow or refuse a click the game
has already decided to dispatch - and why it cannot create one.

### 25.4 What is still unproven (and why no OBS was written)

1. **Who addresses the click for a touch.** The controller/keyboard producers of
   `ev->+6/+8` are known (`0x9651b0`, `0x965320`, `0x965460`, `0x965a00`,
   `0x96ff60`, `0x978950`, `0x9790e0`, `0x97b4c0`, `0x97b630`, `0x989a50`,
   `0x98be00`, all gated on `[main+0x27dee2c]==1 || [main+0x27dec24]==1`). The touch producer
   has not been located, and until it is we do not know whether a tap addresses
   the event to `x26`, to another id, or uses a different path entirely.
2. **Which result byte is hover, and whether it survives the release.** The
   query copies eight bytes of result at `[x29-0x98] .. [x29-0x60]` plus the
   click byte at `[x29-0x58]`; the earlier roster work decoded the packed mask
   of the same query (`bit 0x001` hover, `0x008` details) but not this struct.
   A release-time authorization needs to know the item is still under the
   finger at that moment, and a rectangle test is explicitly not acceptable.
3. **Whether the item's identity at build time is the same value** the event
   must carry (`x26` vs `[x26]`). The query is passed `&[x26]` at `0xe134f4`,
   which suggests `[x26]` is the id, but this is inferred, not observed.

Writing game state on those three guesses is exactly what the review forbade.
The probe in 25.6 settles all three with no write and no game-function call.

### 25.5 The bounded design, if the probe confirms it

Both variants are same-frame, per-call and scoped to the live Nomad row; neither
touches `gesture_fill`, `touch_fill`, the poll, or any other control.

**Variant A - address the game's own event (preferred if 25.4(1) shows a touch
tap does this).** A new observation site just before the item's query
(`0xe134d0` has `x26` live and `[x26+0x1d0]` already the wrapper):

- proceed only when `[wrapper] == main+0x11933a8` and
  `[[wrapper+0x70]] == main+0x117a678` (the Nomad purchase, checked on the live
  object, not on a saved one);
- proceed only when the host's contact snapshot for this contact is
  `RELEASED` after `>= 0.5 s`, or `PRESS` at `>= 0.5 s` if the release frame
  cannot prove the hit;
- prove the hit with the game's own query result (the hover byte), not a rect;
- write `ev->+6 = 1`, `ev->+8 = [x26]` once, and let `0xe134fc` consume it in the
  same call; the game then dispatches `0xe156b4` -> `0xe18410` itself.

The filter at `0xe18410` then has to allow that one call: it would consult a
host one-shot permit armed by the same code and consumed by the call, so a
click that the user did not make cannot pass.

**Variant B - authorize at the dispatch test (only if 25.4(1) shows the tap
never uses the event).** An observation at `0xe15690`, where the result is
already copied and `x26` is live: under the same binding and contact
conditions, set `[x29-0x58] = 1` so the game's own `tbz` at `0xe15694` takes its
own dispatch. Nothing is called directly either way; the wrapper, its argument
marshalling and the purchase stay the game's.

What neither variant does: no global gesture change, no cross-frame object, no
direct money/inventory write, no UI traversal, no second click, no change to a
short tap (which stays refused by the existing filter).

### 25.6 The read-only probe (no implementation until it has run)

`/private/tmp/dd-nomad-probe-20261030/nomad_click_probe.py` (LLDB, Python). It
refuses anything but the retail build: it checks the Host's module table for
`main ff2bf2...` and `sdk b33804...`, then fifteen original instruction words
(`0x738fc0`, `0x738fc8`, `0x738fcc`, `0x738fd4`, `0xe15690`, `0xe15694`,
`0xe15698`, `0xe156b0`, `0xe156b4`, `0xe156b8`, `0xe156c0`, `0xe18410`,
`0xe1841c`, `0xe18428`, `0xe18460`) and two vtable slots
(`0x11933a8+0x30 == 0xe18410`, `0x117a678+0x30 == 0xc30760`). The entry word
at `0xe18410` may be the retail prologue or the branch the rewriter puts there
for the existing shop filter; every other word must match, and the run needs the
policy off (`DM_DD_TOUCH_POLICY` unset), or the filter would refuse the purchase
the probe is there to observe.

| Site | Registers read | What it answers |
| --- | --- | --- |
| `0x738fd4` (click consumed) | `x13` = event, `x14` = `ev->node`, `x26` = identity | whether a touch click is event-addressed, and with which id (Q1) |
| `0xe15690` (result test; conditional and throttled) | `x26`, `x29-0x98..-0x58` | the hover byte and the click byte while the finger rests on the item (Q2) |
| `0xe15698` (dispatch) | `x26`, `[x26+0x1d0]`, `+0x70` | the wrapper and its bound callable on a real click (Q3) |
| `0xe18410` (wrapper entry) | `x0`, `[x0+0x70]`, `[x0+0x300]` | that the purchase callable really ran (Q3) |

The `0xe15690` breakpoint carries a read-only LLDB condition (contact exists in
`main+0x27e0901`, and the live wrapper is the primary one bound to
`0x117a678`), and disables itself after 400 stops if the condition ever fails to
hold, so it cannot flood. `DM_NOMAD_WATCH=1` additionally sets a 4-byte write
watchpoint on the event's kind byte to name the producer; it must be armed only
around one contact, because it stops on the poll's per-frame clear.

**Input, at most two contacts, on a copy of an isolated save:**

```
DM_CTL=<file>   # lines appended once the Nomad wagon lists trinkets
T<x>x<y>        # one short tap, 0.15 s (the native buy, the control condition)
T<x>x<y>~1.2    # one 1.2 s hold, released after the 0.5 s Press step
```

`<x>`,`<y>` come from a `shot` of the open shop, on the same merchandise row
both times. The Mac host runs this profile in handheld mode (`op_mode handheld`)
and the left button and `dm_touch_set` feed the same touch screen, so the run
exercises the touch path, not a mouse HID path - but it is still the Mac host
and is **not** iOS evidence; it is evidence about the game's own machinery.

**Decision table.**

| Probe result | Consequence |
| --- | --- |
| tap: a `consume` record with `ev->+6 == 1` and `ev->node == x26`, then `dispatch`, then `wrapper` with `buyer_vt == 0x117a678` | the click is event-addressed: Variant A is the faithful route |
| tap: no `consume`, but `dispatch` with `click_byte == 1` | the click comes from the pointer pulse, not the event: Variant B |
| tap: neither | the shop does not buy by tap on this build; stop and re-read 24.1 |
| hold: `sample` records with `click_byte == 0` and a stable hover byte | confirms the gap and gives the hover semantics a release-time rule needs |
| hold: any `dispatch`/`wrapper` record | the hold already buys; the existing filter is the whole problem and no new site is needed |
| `elem0 != elem` anywhere | the identity is not `[x26]`; Variant A is out |

### 25.7 Boundaries

- Nothing was implemented: no OBS number, no filter change, no ABI. The source
  is frozen as of this section; the probe is the only next step, and it is
  read-only.
- The probe was syntax-checked, not run: this environment cannot start the game
  or attach LLDB. Its first run belongs to the primary agent, with a log and the
  `events.jsonl` returned for review.
- The purchase itself is never called by the Host in any variant; the game's own
  wrapper and the game's own queue do the work, as they do for a tap today.
- `models/saves`: the run uses a copy of the isolated test save; a short tap may
  legitimately buy one trinket there, which is the native control condition.

### 25.8 Four-task status

| Task | State |
| --- | --- |
| A Mac pointer | unchanged this round |
| B Nomad hold | round-7 change **withdrawn**; chain proved statically; bounded Variant A/B defined; read-only probe written; **not implemented, not accepted, no device run** |
| C roster hold | unchanged; user-reported Mac acceptance stands (23) |
| D MOD layout | unchanged, still a downgraded candidate |

## 26. Twelfth continuation: the failed lift-only policy and the shop diagnostic (2026-10-30)

The user's iPhone report - "饰品商店长按还是不能购买" - is the first runtime
evidence about task B, and it closes the question the last two rounds kept open:
the lift-only policy does not buy, and it cannot. This section records what the
retail instructions now pin down, why no authorization is written yet, and the
one read-only diagnostic that settles the single missing byte. Same build
(`ff2bf22565188d11ea0981ee0e2b53ce`, `sdk b33804825108340e4cad9d080a636a3f`).
No commit, no branch, no push, no App or IPA built.

### 26.1 Why the lift-only policy cannot work

The shop filter allowed the game's own click at `Press` or on a lift after 0.5 s.
Neither exists on iOS. The recognizer (yuzu's rule, Horizon's too) turns a still
finger into `Press` after 0.5 s; the game's poll (`0x74c484`) turns `Press` into
its **drag** state and clears the click state (`0x74c828`); the release of a
`Press` is `Complete`, which produces no click at all. So a held contact produces
no game click for the filter to allow, at any time. The filter's refusal of the
short tap's click is therefore the only branch that ever runs: focus, no buy.

That is a dead end by construction, not a matter of verification. Two ways out
were considered and rejected earlier: making the recognizer report a hold as a
`Tap` (a change to `nn::hid::GetGestureStates` for the whole title, withdrawn in
section 25.2 and refused by review), and synthesising a touch-up or a second
click (explicitly out of bounds).

### 26.2 What the instructions now pin down

The merchandise row's own update is `0xe13120`. It is reached per frame and per
row: the grid `0xe16370` builds each row through `0xe171c0` (two 0x310-byte
wrappers at `0xe17780`/`0xe177d0`, the row's parameters at `0xe17c20`, the mode
word at `0xe177a8`/`0xe1780c`) and then calls `0xe13120` at `0xe1788c`; the same
element update also serves other grids from `0xce30f0`, `0xcf108c`, `0xcfa894`.
Inside it:

| Site | Word | What it does |
| --- | --- | --- |
| `0xe134d0` | `52802008` | `mov w8,#0x100`, then `0xe134d4 781a73a8` `sturh w8,[x29,#-0x59]`: the click byte at `x29-0x58` **defaults to 1**, its neighbour to 0 |
| `0xe134c0` | `381a03bf` | `sturb wzr,[x29,#-0x98]`: the result's first byte **defaults to 0** |
| `0xe134fc` | `d63f0120` | `blr x9` - the row's own interaction query (`x0 = [x26+0x50]`, `x1 = &[x26]`, `x2 = &x21`, result at `sp+0x540`); a null provider skips it |
| `0xe13500..0xe13534` | | the result is copied to `x29-0x98 .. x29-0x58`: `+0x00 -> -0x98`, `+0x08 -> -0x90`, `+0x10 -> -0x88`, `+0x18 -> -0x80`, `+0x20 -> -0x78`, `+0x28 -> -0x70`, `+0x30 -> -0x68`, `+0x38 -> -0x60`, byte `+0x40 -> -0x58` (`0xe1350c 395603e8`, `0xe13514 381a83a8`) |
| `0xe135e8` | | reads the click byte, ORs it with `[x26+0xe0]`, and calls `0x72dcb0` (tooltip/detail update) |
| `0xe13ef8`, `0xe14d8c` | | further reads (a saved copy, and a highlight whose colours are `[x26+0x68]` or `0xb1a600140`) |
| `0xe15690` | `385a83a8` | `ldurb w8,[x29,#-0x58]` - the **last** read; `0xe15694 36000228` `tbz w8,#0` skips the dispatch |
| `0xe15698` | `f940eb40` | `ldr x0,[x26,#0x1d0]` - this frame's click callable; `0xe1569c b4000140` `cbz` |
| `0xe156b4` | `f9401908` | `ldr x8,[x8,#0x30]`, then `0xe156c0 d63f0100 blr x8` with `x1 = sp+0x540`, `x2 = sp+0xf0` |

So the row's dispatch is the game's own, two instructions after the click byte's
last read, with the row's live wrapper in `x26+0x1d0` and the purchase callable
at `wrapper+0x70` (vtable `0x117a678` -> `0xc30760`). Setting the click byte at
`0xe15690` would give a held contact the game's own click, in the same frame, on
the row whose update is running - no game object stored, no call made by the
adapter, the wrapper and the purchase deciding everything.

### 26.3 The one byte that is missing

`0xe15690` is reached once per row per frame, so writing the click byte there
needs to know **which row the finger is on**; without it, a hold would authorise
whichever row's update runs first - buying an item the user is not pointing at.
Four candidates exist and none is proved:

| Candidate | Evidence for | Why it is not enough |
| --- | --- | --- |
| result byte 0 (`x29-0x98`) | the earlier rounds call it hover (24.5); defaulted to 0 at `0xe134c0` | never read again inside this update; the audit's source is the roster work, not this row |
| `[x26+0xe0]` bit 0 | OR'd with the click byte for the tooltip at `0xe135ec` | could be "selected"/"tooltip-wanted" rather than "under the finger" |
| `[x26+0xe1]` bit 0 | OR'd with the click byte for the highlight at `0xe14d8c..0xe14db4` | same doubt |
| `[x26+0xe4]`/`[x26+0xe5]` | read at `0xe14d68` and `0xe156c4` | purpose unknown |

Writing the click byte on a guess is exactly what the review forbade, and a wrong
guess is worse than the present behaviour: it would buy the wrong row. So this
round implements the diagnostic below and not the authorization.

### 26.4 The diagnostic (OBS 29)

`patches.py`: `(0xe15690, 29, '385a83a8', ...)` - the rewriter's `after_bl` rule
accepts it (`0xe1568c 9400c35d` is `bl 0xe46400`, and the gate replays the
`ldurb`). `dm.h`: `OBS_DD_SHOP_UPDATE = 29`. `hle_dd_touch.c`: `dd_shop_update`,
registered on that gate, gated by `dd_probe_ok`, which the real `dd_validate()`
sets only when the gate is present **and** the nine neighbouring words above are
the retail ones.

It is off unless `DM_DD_SHOP_PROBE=1`, and when on it:

- runs only for `DM_CONTACT_IOS`, only with one finger (or its release), never
  for a moved/cancelled contact, and only when `dd_shop_binding_ok` accepts the
  live `[x26+0x1d0]` (primary/secondary wrapper whose `+0x70` is the Nomad
  purchase vtable) - no other row, no other scene, no other binding;
- writes nothing: it reads the click byte, result byte 0, `[x26+0xe0..0xe5]`,
  the pointer state `main+0x27e0901` and the contact snapshot;
- records one line per row per **change** (a small 8-entry table keyed by the
  row pointer), capped at 120 lines plus one notice, so a 20-second visit costs
  tens of lines;
- logs the dwell in ms, the contact phase and count, `owner` (`dd_pointer_owner`),
  the click byte, `res0` and the six row flags.

A line looks like:

```
DD shop probe: row 0x100a59f10 dwell 610 ms phase 2 count 1 owner 1 click 0 res0 01 flags 01 02 40 77 00 00 ptr 00
```

**Reading it** (this is the experiment, one shop visit, two contacts on the same
trinket):

| Observation | Meaning |
| --- | --- |
| lines appear while the finger rests, with `click 0`, and exactly one row's `res0` is 1 | result byte 0 is the hover/current-target byte: it is the byte to require before writing the click byte |
| lines appear with `click 0`, `res0` 0 on every row, and exactly one row's `flags` byte differs | that flag is the target byte instead |
| lines appear only with `phase 4` (released) | the row update does not run while a finger rests; the per-frame model is wrong and the approach must be re-thought (the diagnostic would then say so before any write exists) |
| some row shows `click 1` during the hold | the hold already produces a click and the filter, not the producer, is the whole problem |
| no line at all, or `owner 0` | the contact never reached the row (a wrong scene, or the game is not in the touch-pointer mode); nothing can be concluded about the bytes |

Absence of a line is never treated as "the byte is clear": the table only records
changes, and a row whose update did not run has no line.

### 26.5 The iPhone test (no DM_CTL; all input by Computer Use)

The diagnostic needs the prepared module rebuilt with OBS 29 and a Host built
with this source; the assistant does not build or pack them. With that build:

1. Launch with `DM_DD_TOUCH_POLICY=1 DM_DD_SHOP_PROBE=1` (both are launcher
   toggles/environment values; the probe alone does nothing).
2. Enter the week-1 town, open the Nomad wagon, and stop when the trinket rows
   are visible. Take one screenshot.
3. **One short tap** (press and release, well under 0.5 s) on one trinket row -
   the fourth row of the grid is fine. Nothing should be bought; this contact is
   the control that proves the game's own click path.
4. **One hold**: press the *same* row and keep the finger still for about 1.5 s,
   then release. Nothing should be bought.
5. Quit normally and send `Documents/log.txt`.

The log's `DD shop probe:` lines are the whole result. The touch must be a real
finger (or the iOS simulator's touch), not a mouse: the callback only records
`DM_CONTACT_IOS`.

### 26.6 Boundaries

- This is a diagnostic, not a fix: it does not buy. The settings text now says
  so instead of claiming a 0.5 s hold is allowed.
- Nothing else changed: the skill toggles, the roster hold (user-accepted), the
  short-tap focus, the round-6 cancellation latch and the shop filter are as they
  were; the MOD work is untouched.
- The earlier LLDB probe in `/private/tmp/dd-nomad-probe-20261030/` is superseded
  by this in-package site and must not be reused as it stands: it misses
  `global MATCHED` in three callbacks, treats `SBPBreakpoint.SetCondition`'s
  (possibly `None`) return as a boolean and would disable its own sampling, and
  gates its sample window on `main+0x27e0901`, which the `Press` path clears - the
  three reasons this round uses a Host gate instead of LLDB.
- `dd_test_init` is not used to prove the site: the new tests run the same
  `dd_validate()` the game runs, with the retail words in a fake image, and check
  that a missing gate or a changed neighbour withdraws the diagnostic
  (`t_dd_touch`, 16 new checks).

### 26.7 Four-task status

| Task | State |
| --- | --- |
| A Mac pointer | unchanged |
| B Nomad hold | lift-only policy **proved ineffective on iOS** (user's device); chain and row update pinned down to the dispatch instruction; authorization blocked on one unproven byte; read-only OBS 29 diagnostic implemented, default off, tests pass. **Not a fix; no device run yet** |
| C roster hold | unchanged; user-reported acceptance stands |
| D MOD layout | unchanged, still a downgraded candidate |

## 27. Primary review: identifying merchandise in diagnostic output

The new OBS29 remains diagnostic only. The primary tightened the environment
switch to require the exact value `1` (`0` is off). Log de-duplication includes
both the live control address and the verified wrapper's argument at `+0x304`:
a reused control address must not suppress a different merchandise ordinal.
The table holds 16 such keys and retains the 120-line limit. The log includes the
contact generation, host touch position and the current game pointer position;
these are needed to distinguish a true finger target from stale selection.
No game state or purchase callback is written or invoked by this observer.

Five additional checks exercise reused-address/different-ordinal recording and
the exact opt-in values: 131 policy checks passed. The diagnostic's environment
file enables the existing touch policy and the bounded observer; it does not
change Press/Tap/Gesture semantics. It is not a purchase fix.

For useful device evidence: capture the shop with two visible merchandise rows;
short-tap A, hold A for about 1.5 seconds and release, then hold B without first
short-tapping B, and finally hold an empty area. Return Documents/log.txt and the
shop screenshot before launching again (the log may be replaced on launch).
A single unique flag is not sufficient proof of finger hit: correlate the item
ordinal, host position and game-pointer position, and compare the B/empty trials.
The source freezes for the diagnostic IPA; Mac and MOD resources are unchanged.

## 28. Thirteenth continuation: why the probe printed nothing, and the counters that say so (2026-10-30)

### 28.1 The delivered log

`Documents/log.txt` from the 1.3.0 diagnostic build is 369 lines. It has the two
start-up lines (`DD touch policy: enabled ...`, `DD shop probe: enabled (DM_DD_SHOP_PROBE=1 ...)`,
i.e. `dd_valid`, `dd_ios`, `dd_probe_ok` and `dd_probe == 1` all held), one
`DD touch policy: contact 1 ended` line, and **no row line at all**.

That `contact 1 ended` line is the boot artifact, not a tap: `dd_frame_tick`
prints it when the generation changes and the previous generation had set
`fired`, which happens on the frames before the first contact exists
(`!own`). It therefore says nothing about how many taps the game received, and
its absence later says nothing either (the same branch only prints when the
generation changes *and* something was armed or fired).

The old observer had six silent exits before the line it prints:

1. `s.source != DM_CONTACT_IOS` (line 578);
2. `s.phase == DM_CONTACT_CANCELLED`;
3. `s.count != 1 && s.phase != DM_CONTACT_RELEASED`;
4. `elem < 0x10000 || elem & 7 || fp < 0x10000`;
5. `[elem+0x1d0] < 0x10000` (the dispatch slot is empty);
6. `!dd_shop_binding_ok([elem+0x1d0])` (vtable, mode byte, bound callback).

None of them wrote a counter, so the log cannot say which one fired, and the
report that "the hover byte is 0" is not supported by it. The counter work below
is the answer to that: the next run states the layer.

### 28.2 The site, re-read against the retail main (`ff2bf225…`)

Disassembled from `ExeFile/main` of 1.3.0 (v393216), not from a patched copy:

```
e13120  str d12,[sp,#-0x90]!  ...  e131f4 str x0,[sp,#0x58]       ; the update's first argument
e13384  ldr x26,[sp,#0x58]                                        ; x26 = that argument for the rest
e134d0  mov w8,#0x100 ; e134d4 sturh w8,[x29,#-0x59]              ; the click byte's default
e134fc  blr x9                                                    ; the row's own interaction query
e13514  sturb w8,[x29,#-0x58]                                     ; the query's byte 0x40 -> the click byte
...
e15504  ... e1550c ldrb w8,[x26,#0xe6] ; e15510 tbz w8,#0 -> e15690
e15630  ldr w9,[x26,#0x120] ; e15634 cmp w9,#0x4f ; e15638 b.eq e15690
e1563c  ldr x0,[x26,#0x128] ; e15640 cbz x0,e15690
e1568c  bl 0xe46400
e15690  ldurb w8,[x29,#-0x58]        ; OBS 29
e15694  tbz w8,#0 -> e156d8
e15698  ldr x0,[x26,#0x1d0]
e1569c  cbz x0,e156c4
e156b0  ldr x8,[x0] ; e156b4 ldr x8,[x8,#0x30] ; e156c0 blr x8
```

All three predecessors of the branch at `e15630` converge on `e15690`, so the
gate is entered on **every** row update of every visible grid — it is not
conditioned on a hover. `r[26]`/`r[29]` are the guest's real `x26`/`x29`
(`entry.S` `_dm_gate` saves `x25`/`x26` at `[sp,#192]`, `x28`/`x29` at
`[sp,#224]`), and `x29-0x58` is the byte `e13514` writes, so the two offsets the
callback reads are right.

What `x26` is, however, is not the persistent button: each of the update's four
callers (`0xce30f0`, `0xcf108c`, `0xcfa894`, `0xe1788c`) passes **its own stack
temporary** as `x0`; `[x26]` is that descriptor's model pointer (`ldr x11,[x26]`
then `[x11+0x570]`).

`+0x1d0` is a `std::function`'s `__f_` word, not a plain callable field:

* `0xd21780` (the assignment used at `0xe176f0` with the destination
  `descriptor+0x1b0`) compares `[this+0x20]` with `this` itself and swaps through
  `+0x20` — the small-buffer layout of a 0x28-byte `std::function`, whose
  `__f_` is at `+0x20`. `+0x1b0 + 0x20 = +0x1d0`.
* The row builder fills it with a **copy of the row data's own callback**:
  `0xe17588 ldr x0,[x22,#0x260]`, clone into `sp+0x9e0`, then
  `0xe176f0 mov x1,x28` (`x28 = descriptor+0x1b0`) `bl 0xd21780`.
* The callable this policy was written against — vtable `0x11933a8`, allocated
  `new(0x310)` at `0xe17788` with `+0x300 = {u16 mode, u32 slot}` and
  `[+0x70] = the purchase std::function` — is passed to the update as
  **argument `x2`** in a separate function object (`0xe177a4 str x24,[sp,#0x6d0]`,
  `x2 = sp+0x6b0` is `.f_` at `+0x20`).
* Nothing inside `0xe13120` writes `+0x1b0`/`+0x1d0`: a full memory-operand scan
  of `0xe13120..0xe157b0` finds only the load at `e15698`.

`0xe18410` itself (vtable `0x11933a8` slot `+0x30`) ignores `x1`/`x2` and reads
exactly `[x0+0x300]`, `[x0+0xd0]` (mode 1) or `[x0+0x70]` (otherwise) and
`[x0+0x304]`, so `dd_shop_binding_ok`'s constants are right **for that object** —
the mistake was applying them to `descriptor+0x1d0`, which for these rows holds
the data's callback instead. `dd_shop_binding_ok` therefore rejected every row
before any logging: that, and not a zero hover byte, is what the empty log shows.

### 28.3 The diagnostic, second form (still default off, still read-only)

`dm/host/hle_dd_touch.c`, OBS 29 callback only. No new gate, no new address, no
write, no change to any policy decision.

* **Every layer counts itself**: gate entries, contacts by source, cancelled,
  `count != 1`, bad row argument, empty dispatch slot, Nomad binding, foreign
  vtable, recorded rows.
* **A periodic summary** at frames 25, 50, … up to 1000 and every 100 after that,
  at most 16 lines, printing those counters, the current generation / phase /
  count / source, and the dispatch vtables seen so far:
  `summary frame 25 gen 3 phase 4 count 1 src 1 | gate 240 ios 240 … | dispatch vt +0x117c8d0 x12`
  The first summary therefore also says "the gate was never entered" when that is
  the case — which the old form could not.
* **A foreign dispatch callable is recorded once per distinct shape**, with the
  callable's own vtable plus the vtables at `descriptor+0x170` and `+0x110`
  (each of the three is dereferenced by the game itself at `0xe13400`,
  `0xe155f8`, `0xe156b0`, so the read cannot fault where the game would not).
  The Nomad identification is no longer a precondition for a line.
* **The two Nomad bindings are still recorded in full**, and now print `mode`,
  `cb` and the callback's vtable instead of being filtered on them, so a binding
  that is not a purchase is visible rather than silent.
* Bounds unchanged: 120 detail lines plus the cap notice, plus at most 16
  summaries.

### 28.4 Reading the next log

| what the log shows | conclusion |
| --- | --- |
| `dispatch vt +0x1xxxxx` lines for the merchandise rows | that offset is the row's real click class; the next step is its `+0x30` slot, not a hover byte |
| `gate 0` in every summary | the store does not draw through `0xe13120`; the site is wrong and the filter is not the issue |
| `gate` grows, `ios 0`, `other-source` grows | the touch did not reach the host as an iPhone contact (front end, not the policy) |
| `gate` and `ios` grow, `no-fn` grows | the descriptor's dispatch slot is empty on these rows (the click is dispatched elsewhere) |
| `nomad` grows, `rows` grows | the binding was reached; the row lines now carry the four candidate bytes and the mode |

The tap/hold protocol is unchanged (short tap A, hold A, hold B, hold an empty
area), and the same log answers it.

### 28.5 What did not change

The touch policy's decisions, the gesture history, `front_ios.m`'s or
`DmGamepad.m`'s touch routing (`pad_layout touch` sends every touch to the game
as `DM_CONTACT_IOS`, and the only `DM_CONTACT_UNKNOWN` publish is
`dm_touch_set(NULL,0)` when `DM_TOUCH_INPUT` is off, which cannot change the
source of a live contact), the Mac front end, the town roster action, the
accepted character-skill hold, MOD v1/v2 and every profile file
(`patches.py` is untouched).

Verification of this round: `make -C dm/host/tests GAME=01008F1008DA6000 run`
exit 0 with no `FAIL`; `t_dd_touch` 136 checks / 0 failed (was 131);
`t_gesture` 43 / 0; `t_touch_threads` 5 / 0; `test_patches.py` 5 OK;
`test_entry_filters.py` 9 OK; `xcrun -sdk iphoneos clang -arch arm64
-fsyntax-only -Wall -Wextra` on `hle_dd_touch.c` clean.

## 29. Fourteenth continuation: the Nomad long press buys (2026-10-31)

### 29.1 The root cause, from the retail instructions

The withdrawn lift-only policy assumed the game dispatches its merchandise click
while the finger is still down, so `dd_shop_filter`'s `DM_CONTACT_RELEASED`
branch could allow the lift click. That assumption is false for this build. In
`ff2bf22565188d11ea0981ee0e2b53ce`:

* `0x74ac70` reads `nn::hid::GetGestureStates` once a frame.
* The only path that sets the pointer's one-shot **click** state
  (`main+0x27e0901 = 2`, consumed at `0x8f644c` into the pulse at
  `main+0x257e710`) is the **Tap** path, `0x74c238`, entered for gesture codes
  3/4 (`0x74c2xx: cmp w8,#3 / cmp w8,#4`).
* A still finger becomes **Press** (code 5) after 0.5 s. The Press path
  (`0x74c484`) sets the pointer's **drag** state to 3 and clears the click state.
* Its release is `Complete`; no click is ever produced.

So a hold never reaches `0xe15698`'s dispatch
(`ldr x0,[x26,#0x1d0]; ldr x8,[x0]; ldr x8,[x8,#0x30]; blr x8`), and
`dd_shop_filter` — which is entered *from* the purchase binding's first
instruction (`0xe18410`) — was never called. Loosening the filter could not help;
the filter was not the layer that stopped the hold. The symptom the user saw
(short tap focuses, hold does nothing) is exactly this: a tap arrives and is
withheld by the filter, a hold produces no click at all.

### 29.2 The fix: the game's own Tap, asked for only on the supply display

`dm/host/hle_touch.c` gains an opt-in recognizer mode, `dm_touch_hold_tap(int)`
(`front.h`): while it is on, a still single finger is **not** promoted from
`Touch` to `Press`, its release is a `Tap`, and that Tap carries no `IsDoubleTap`
attribute and does not move the double-tap clock. This is the same yuzu-shaped
Tap the game already turns into its own click; no gesture, touch state, pointer
field or double-tap attribute is written, and nothing is synthesized.

The mode is turned on only where it is wanted, and only for the contact that
went down there:

* `OBS 30` (new gate, `patches.py`) sits at `0xe177ac`, `add x0,sp,#0x80` in the
  Nomad row builder `0xe171c0`, right after the row's `0x310`-byte binding
  received its vtable (`0x11933a8`) and mode/slot word. `dd_shop_build` accepts
  it only when the freshly built binding's vtable is `0x11933a8`, its mode byte
  `+0x300` is 0, and its `+0x70` callable's vtable is `0x117a678` (the purchase
  lambda). It records only a timestamp (`dd_shop_live_ns`).
* `dd_frame_tick` (OBS 25, before the frame's gesture poll) latches the contact
  that went down while that timestamp is fresh (300 ms) and is an iPhone contact
  the game does not own; it then calls `dm_touch_hold_tap(1)` for that contact.
  A cancelled or moved contact clears the latch; a second of silence from the
  display clears it too.
* Measured on the real game (below): the supply display rebuilds its rows on
  **consecutive frames**, so the 300 ms window is refreshed continuously while
  the shop is open.

`OBS 30` is one more observation gate, so the module's gate count moves from 22
to 23; `dd_validate` now requires both shop gates (`OBS 29`, `OBS 30`) and the
builder's neighbour instructions (`0xe17784=0x940148bf`, `0xe177a4=0xf9036bf8`,
`0xe177a8=0xf9018308`, `0xe177b0=0x911b83e1`). A build without them refuses the
shop policy as before.

Nothing else changed: the filter still decides. It allows the game's own click
once per contact, only when the contact was held `>= 0.5 s` and was not
cancelled/moved/second-fingered. The purchase callback is still never called by
the adapter: the click arrives at `0xe18410`, which runs the `+0x70` callable —
`__func<TrinketSupplyDisplay::PreChildrenShowInternal()::$_1, void(unsigned)>`
(vtable `0x117a678`, operator `0xc30760`) — with the row's slot word, and the
game's own price/stock/capacity/confirm code decides everything.

### 29.3 Why a short tap still only focuses

A 120–300 ms contact ends before the recognizer's Press threshold, so the game
produces the same Tap it always did; the filter still withholds it because the
contact was down under 0.5 s. The tooltip/price/attributes path is untouched
(it is driven by the touch position and the row's hover state, not by the click
dispatch). Verified on the real game: the tap produced
`short tap: the game's click is withheld, focus only`, the tooltip appeared and
gold stayed `6,135`.

### 29.4 The chain as it now runs

```
TouchDown (iPhone)  -> contact snapshot gen n, phase DOWN
frame tick          -> display live (OBS 30 within 300 ms) -> latch n
                    -> dm_touch_hold_tap(1)
0.9 s held          -> recognizer: Touch (no Press), no gesture update
lift                -> recognizer: Tap (no IsDoubleTap attr)
game poll 0x74ac70  -> pointer click state 2 -> pulse -> row dispatch
0xe18410 (binding)  -> dd_shop_filter: phase RELEASED, down_ns >= 0.5 s,
                       not cancelled, not used yet -> allow, mark used
                    -> +0x70 callable -> TrinketSupplyDisplay purchase
                    -> game's own gold/stock/confirm -> trade
frame tick          -> generation unchanged; hold-tap cleared on the next
                       contact or after a second without the display
```

The game's own click runs at most once per contact (`dd_shop_click_used`), the
filter is entered only from the binding itself, and the adapter stores no game
object across frames, so releasing after a purchase cannot buy again, and a
closed panel cannot be bought from later.

### 29.5 Evidence on the real game (Mac host, iPhone contact source)

A Mac host run cannot press the iPhone path by itself (its left button is
`DM_CONTACT_MAC_LEFT`), so the `DM_CTL` diagnostic gained one command:
`itap <x> <y> [seconds=0.8]` publishes one contact with the **iPhone source**,
holds it still and lifts it — the same publication the phone's touch path makes.
It is Mac-only (`DM_CTL` unset = absent) and buys nothing by itself. A second
diagnostic, `DM_DD_SHOP_BUILD=1`, logs the frame of each purchase-row build.

Run: the 1.3.0 town save (week 1, 6,135 gold), Nomad Wagon open, `DM_DD_TOUCH_POLICY=1`.

| action | log | screen |
| --- | --- | --- |
| `itap` 0.15 s on the 5,000 trinket | `contact 8 held in the game's own tap mode` then `short tap: the game's click is withheld, focus only` | tooltip shown, item still for sale, gold 6,135 |
| `itap` 0.9 s on the same trinket | `contact 9 held in the game's own tap mode` then `lift after a >=0.5 s hold: the game's own click runs the purchase binding once (contact 9)` | item gone, gold 6,135 → **1,135** (exactly 5,000) |
| release of the same contact | no further line | gold stayed 1,135 |
| `itap` 0.9 s on the 25,000 trinket | `contact 10 held in the game's own tap mode`, no purchase line | tooltip only, gold 1,135 unchanged |
| display rebuild rate | `purchase row built at frame 5542, 5543, 5544, …` | rows rebuild every frame while open |

The purchase is the game's own: the price was debited once, the stock slot
cleared and the row list redrew. The adapter never called the purchase callback.

### 29.6 What did not change (and the one scope addition)

* The character-skill hold (combat and camping), the town roster long press, the
  Mac pointer bridge and the MOD 1099001958 trinket box: their paths are not
  touched; `dm_touch_hold_tap` is on only for a contact latched on the supply
  display (Nomad page or its DLC/Comet page), and the host's Press promotion for skills is computed from the
  contact snapshot, not from the gesture history.
* The **DLC/Comet supply** now shares the policy (added 2026-10-31): it builds
  its rows with a different callable (vtable `0x117a7c0`,
  `CometTrinketSupplyDisplay`) through the same builder and wrapper, so
  `dd_shop_binding_ok` accepts either callable and everything else - the latch,
  the 0.5 s rule, the one-click-per-contact rule - is the same code. The game's
  own callback still decides price, shard balance, capacity and stock; live
  evidence (short tap, hold, move, insufficient shard, inventory, Nomad
  regression) is in `docs/darkest-dungeon-dlc-shop-test.md`.
* No game object, gold, inventory, item or save is written by the adapter; no
  transient TouchUp is made; the recognizer's only change is the opt-in mode.

### 29.7 Tests

* `t_dd_touch`: **154 checks / 0 failed** (was 131); new section 8 covers the
  display gate (secondary binding, drag mode, foreign callback, module without
  the gates), the armed contact producing `TOUCH → TOUCH → TAP` and exactly one
  purchase, a repeated click refused, a short tap buying nothing, cancel and move
  disarming, and a contact outside the display never arming.
* `t_gesture`: **59 checks / 0 failed**; section 10 holds a still finger at
  `Touch` through 0.6 s, its release as `Tap` without the double-tap attribute,
  and the restoration of `Press → Complete` when the mode is off.
* Full host suite `make -C dm/host/tests GAME=01008F1008DA6000 run`: exit 0, no
  `FAIL`. Python rewriter tests: all pass (`test_patches`, `test_entry_filters`,
  `test_nsp_*`, `test_nsoseg` after installing `lz4`).
* The retail main rewritten with the new `patches.py` lists OBS 30 at
  `0xe177ac` (`main.obs.tsv`) and 23 gates (`main.gates.tsv`).

### 29.8 To confirm on the iPhone

1. Open the Nomad Wagon, short-tap a trinket: tooltip and price, no purchase.
2. Press and hold a trinket for about 1 s, then lift: exactly one purchase (gold
   down by the price, item gone), no second purchase on release.
3. Hold a trinket you cannot afford: the game's own refusal, no gold change.
4. Press a trinket, move the finger off it, lift: no purchase.
5. Close the shop while holding, then lift: no purchase.
6. Confirm combat/camping skill holds, town portrait long press and the trinket
   box MOD still behave as before.
7. Switch the wagon to the DLC (Comet) page (the switch at the bottom-left of the
   panel) and repeat 1-4 with shards: short tap = tooltip and price, no shard
   spent; ~1 s hold = one purchase (shard count down by exactly the price, row
   gone, trinket in the inventory); a move before the lift buys nothing; an
   unaffordable item is refused by the game itself. Mac-host evidence for all of
   these is in `docs/darkest-dungeon-dlc-shop-test.md`.

Set `DM_DD_TOUCH_POLICY=1` (as the app does) to get the two policy lines in
`Documents/log.txt`; with `DM_DD_TOUCH_DEBUG=1` the arming and allow lines are
also printed (capped at 120).
