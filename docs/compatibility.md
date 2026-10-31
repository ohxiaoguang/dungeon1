# Compatibility and acceptance

Product baseline: Darkest Dungeon 1.3.0/v393216. Main Build ID
`ff2bf22565188d11ea0981ee0e2b53ce`, subsdk0
`bd9af3397f38608dba3f01510fd206e8`, SDK
`b33804825108340e4cad9d080a636a3f`.

## Inherited evidence (not new-project acceptance)

The user accepted the earlier iPhone ordinary Nomad shop short-focus/hold-buy
behavior and prior input work. The Comet change has two Mac-host iPhone-source
runs: 20,000 to 19,975 shards and 40 to 15, one native 25-shard purchase per
contact, named trinket in inventory, insufficient-shard refusal, move cancellation
and ordinary-shop regression. See the historical
[DLC record](darkest-dungeon-dlc-shop-test.md). No iPhone DLC acceptance was claimed.

## New standalone build evidence

The split's compiled/source and live verification results are appended below after
execution; inherited results above do not establish the new package's behavior.
Private logs/screenshots stay outside this repository.

## Device checklist still open

Sign/install the new IPA, import a **copy** of a backed-up save, and verify skill,
camping, roster, ordinary shop and Comet behavior. Confirm one debit/one inventory
addition per qualifying contact; short tap never buys; insufficient funds stay
refused. Exercise multi-touch, focus loss, changing rows, refresh, closing the shop
while held and controller takeover. Check save persistence and MOD layout on the
actual device. No new iPhone/iPad run is claimed by this initialization.

## Standalone execution results (2026-10-31)

- Complete Host suite passed in the new checkout, including 154 touch-policy
  checks, 59 gesture checks, save/MOD filesystem tests and both Mouse HID modes.
- NSO/entry-filter/observation/patch tests: 81 passed, including ARM64 execution
  through unicorn (no skips in this run). Six GL uniform tests and 28 retained
  packaging/platform/GL-library tests passed. The removed tests belonged to the
  omitted multi-game packaging GUI/catalogue; synthetic core parser tests remain.
- All three modules were reprocessed from original ExeFS by Dungeon1's own
  rewriter. The resulting program bytes exactly match the stable modules. No
  other profile or old checkout is needed. Both platform GL caches were validated
  and reused; no new full shader translation was necessary.
- The actual Mac launcher opened, identified embedded 1.3.0 resources, selected a
  private data directory and started its included Host. The new storage chooser
  was changed to an asynchronous sheet after a live run exposed the inherited
  blocking chooser issue. Five DLC were reported at runtime; audio callbacks
  produced output. This is separate from device acceptance.
- A diagnostic run used the exact final App's Host, modules, GL libraries,
  RomFS and DLC, with iPhone-source DM_CTL contacts. It loaded the copied town
  save: gold 13,480, shard 40. Nomad short tap showed Tooltip without buying; a
  0.9 s hold bought once for 10,000 gold (3,480 left). Comet short tap showed
  Tooltip without buying; a 0.9 s hold bought one 25-shard lens (15 left). A
  30-shard item with 15 shards stayed for sale and balance remained 15.
- The town trinket inventory showed the original stone plus the purchased
  ordinary eye-patch and Comet lens. Native Save and Quit persisted gold 3,480
  and shards 15, confirmed by the structural save reader against the committed
  test save, not only a filter log. Private screenshots/logs are retained outside
  source. No user's formal save was modified.
- Final IPA: Dungeon1 / com.ohxiaoguang.dungeon1 / 1.3.0, bundled directory mode,
  13,367 entries, five DLC, touch policy default on, required shop FILTER/OBS
  tables present. No console keys, NSP/XCI, Mac dylib or code-signature folder.
  It is unsigned and has not been installed on a device.
- Both final local artifacts use the supplied 1024-pixel lantern icon. The Mac
  artifact passes deep/strict ad-hoc signature verification; no Developer ID
  signing or notarization is claimed. The icon images remain private inputs.

### Remaining live coverage limits

The initial transformed-window-thumbnail problem was resolved by switching the
private QA bundle to fullscreen using the native window button. Computer Use
then operated the actual mouse: a left click closed hero details, a 0.9 s
left-button hold on the roster reopened native details, and moving the mouse
(with a small wheel event, no left button) onto the first combat skill displayed
its original Tooltip. HID logs record the coordinate delta, zero buttons and
wheel event; the rendered game shows the Tooltip. This QA bundle changes only
application metadata so the UI tool can address the Host process: its dmhost,
programs and resources are exact copies of the final App, not another build.
The external local MOD overlay was mounted read-only in this run. Full MOD
1099001958 layout acceptance and every MOD combination remain unclaimed.
Movement cancellation, second-finger and close-while-held protections passed unit
tests; full new-device lifecycle acceptance remains open. Full playthrough, every
MOD combination and new-iPhone execution are not claimed.

The native roster hold was also verified with iPhone-source input in the
standalone Host before the physical-mouse run, with original hero details shown.

An additional Comet test with the local MOD overlay and **40** shards used a
0.9 s iPhone-source drag beyond the slop: the item grid stayed unchanged and the
balance remained 40. Thus the refusal was observed with enough funds, not inferred
from an already unaffordable item. Native mouse clicks also opened the wagon and
switched between its ordinary and Comet pages in this QA run.
