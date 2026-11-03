# Dungeon1 controls (macOS / iOS / iPadOS)

This guide covers **the Dungeon1 port** (game version 1.3.0) on Mac, iPhone and iPad.

It describes this port, not the Switch release. To make a game built for a controller and a mouse playable
on a touch screen, this version adds its own input modes, so some operations differ from the Switch or other
platforms. Anything marked **unverified** has not been confirmed on a device yet.

The port offers:

| Platform | Input |
|---|---|
| iPhone / iPad | Virtual gamepad (default), direct touch, virtual trackpad |
| Mac | Mouse, MacBook trackpad (including a two-finger swipe) |
| Both | A paired physical controller (Bluetooth or USB) |

The input mode is chosen in the **launcher** and cannot be changed while the game runs: quit, change it, start again.

---

## 1. iOS / iPadOS: virtual trackpad

The whole screen becomes a trackpad and a white arrow (the virtual pointer) appears on the picture. You point with
the arrow, not with your finger.

### Gestures

| Gesture | What it does |
|---|---|
| One finger, swipe | Moves the virtual pointer |
| One finger, tap | One click at the pointer |
| Two quick taps | A double click at the pointer (the game's own) |
| One finger, hold still ~0.5 s | Presses the game at the pointer: its own long press |
| Two fingers moving together | A native touch drag for the game (torch, lists, a carried item) |
| Lift the fingers | Ends the swipe or the hold |

### What you need to know

- **Your finger is not the click point.** Every click, swipe and drag happens where the **pointer** is, wherever
  your fingers are. Move the pointer onto the target first.
- **One finger never presses anything in the game.** It only moves the pointer, so hovering a trinket, lifting, and
  touching the glass again to keep moving cannot pick the trinket up.
- **Holding a finger still presses the game.** After about half a second of stillness this port puts one contact down
  at the pointer; another half second and the game's own long press starts (hold to buy, hold to toggle a skill). A
  full hold is therefore about one second, and the arrow turns **orange** while it is pressed.
- **Moving during a hold cancels it.** Once the contact is down, moving that finger cancels the press (the pointer
  stays where it was); it never turns into a drag.
- **Releasing early cancels instead of clicking.** If the game has not taken the contact as a long press yet, the
  release withdraws it rather than becoming a tap.
- **A two-finger swipe is real game touch.** The game sees a finger go down and move, so the pointer travels with
  that touch and the arrow turns **blue**.
- **A two-finger swipe also drags items.** Because the game treats it as a finger drag, a swipe that starts with the
  pointer on a draggable item picks that item up - **swipe straight away, there is nothing to wait for**.
- **Not every screen accepts a swipe.** Lists, scroll areas and the torch usually do; some panels do not, and need
  their scrollbar dragged instead.
- **Neither a swipe nor a hold clicks**, not even when you lift.

### Example A: reading a trinket

1. Swipe with one finger until the pointer is on the trinket.
2. Stop and read the game's hover tooltip.
3. To move on, lift and swipe again - the trinket is not picked up.

### Example B: clicking and double-clicking

1. Move the pointer onto the target.
2. One tap clicks there.
3. Two quick taps are the game's own double click (opening a hero's details, for example).

### Example C: carrying an item

1. Move the pointer onto the item you want to move.
2. Move two fingers together - straight away, no pause - and the item follows the pointer; the arrow turns blue.
3. Lift either finger to drop it.

### Example C2: holding to buy in a shop

1. Move the pointer onto the item and tap once to focus it.
2. Rest the finger without moving for about half a second: this port presses the game at the pointer (the arrow turns
   orange).
3. Keep holding for about another half second so the game's own long press starts.
4. Lift to finish; moving cancels it.

### Example D: the torch

1. Move the pointer onto the torch's area.
2. Swipe down with two fingers (no pause needed).
3. The game receives a downward native touch drag.

> **Device acceptance**: the user has verified single-finger hold, the unified two-finger swipe and mode-switch setting resets. The torch retains the game's native touch-drag behaviour.

---

## 2. iOS / iPadOS: direct touch

Direct touch hands the whole screen to the game: no gamepad, no pointer.

- **How to switch**: launcher → **Input mode** → **Direct touch** → start the game.
- **Tap and drag**: a finger acts wherever it is; tap, drag and hold mean exactly what the game defines, as on a
  Switch in handheld mode.
- **Hold**: whether a hold works depends on the touch policy below.

**Touch interaction policy** (off by default, shown under *Direct touch*) is a set of hold behaviours this port adds
to the game's own touch handling:

| Where | With the policy on |
|---|---|
| Combat / camping skills | Hold toggles |
| Nomad wagon (gold page and the DLC page) | A tap focuses; hold 0.5 s and release runs one purchase |
| Town hero portrait | Hold 0.5 s and release opens the details |
| Guild skills (unlock and upgrade) | A tap only focuses the row (name, price, description); a 0.5 s hold buys it once |
| Blacksmith weapon / armour upgrades | Tap to inspect; hold at least 0.5 s and release to upgrade once |
| Camping trainer skills and town building upgrade trees | Tap to inspect; hold at least 0.5 s and release to purchase once |

Only version-checked upgrade trees with recognized description bindings are covered. Initial unlocks are identified from their bound callbacks even before a tooltip has been rendered. The user has completed device acceptance of guild initial unlocks and level upgrades, blacksmith, camping trainer and building upgrades. Automated checks provide additional coverage. Moving the finger, a second finger or cancellation buys nothing; one contact can buy only once.

With it off you get the game's original behaviour. It is only shown under *Direct touch*, and changing the input mode
turns it off so it cannot keep acting in a mode that does not show it.

**How it differs from the trackpad**: no pointer, clicks land under your finger, and a long press works at once. The
trackpad positions with a pointer and its hold also works, but you have to park the pointer on the target and wait an
extra half second.

---

## 3. iOS / iPadOS: virtual gamepad

The gamepad is drawn over the picture, with Nintendo Switch button positions.

### Three layouts

A small button at the top centre shows the current layout (`2D` / `3D` / `Tap`); tapping it cycles **2D → 3D → Tap**
and the choice is remembered.

| Layout | Contents |
|---|---|
| **2D** | The essentials: ZL / L top-left, ZR / R top-right, − and + at the top centre, the left stick bottom-left, A / B / X / Y bottom-right |
| **3D** | Everything in 2D plus a D-pad, L3 / R3, and an optional right stick |
| **Tap** | Only the layout button; every other touch goes to the game (for screens played by touch) |

- Buttons are placed by **Nintendo position**: A on the right, B at the bottom, X on top, Y on the left.
- The left stick is a fixed ring with a small dead zone.
- In 3D, a touch that lands in the right third of the screen on no control holds the right stick.
- A physical controller works at any time; connecting one hides the overlay but keeps your layout choice.

### The two switches under this mode

- **Disable touch input** (off by default): the game receives no ordinary touch input at all, while the gamepad, its
  layouts and a physical controller keep working. Useful when you only want the pad and want to avoid stray touches.
- **Touch feedback** (under Advanced, off by default): a light haptic click when you press a gamepad button.

---

## 4. macOS: mouse and trackpad

| Action | Behaviour |
|---|---|
| Move the mouse or the trackpad pointer | Moves the game's pointer (hover and tooltips follow) |
| Left click | A click |
| Double click | The game's own double click |
| Hold the left button and move | Drag |
| Press the trackpad and move | Drag (the same as holding the left button) |
| Two-finger trackpad swipe | A native touch swipe for the game (torch, lists) |

Worth knowing:

- **The two-finger swipe is not a mouse wheel.** The game does not read the wheel at all, so the port turns the
  gesture into **a piece of game touch** - a contact that starts at the mouse pointer and follows the swipe -
  instead of sending wheel events.
- It applies **to Dungeon1 only, and only while "Experimental mouse control" is on** (on by default).
- **Existing mouse behaviour is untouched**: left click, press-and-drag, hover and physical controllers all work as
  before. While the left button is held the swipe stays out of the way, and pressing the button ends a swipe in
  progress.
- **Direction follows your system's natural-scrolling setting**: fingers down drag downwards in the game.
- Inertia (the glide after your fingers leave the trackpad) is never sent to the game, so a drag always ends when you
  let go.
- **Not every list scrolls this way.** For the trinket storage, drag its scrollbar by hand.
- "Two-finger swipe" and "press-and-drag" are different: the first sends a touch drag, the second is a held left
  button.

---

## 5. Launcher settings

### iOS / iPadOS

| Setting | Meaning | Default |
|---|---|---|
| Input mode | Virtual gamepad / Direct touch / Virtual trackpad | Virtual gamepad |
| └ Disable touch input | Gamepad only: the game gets no ordinary touch | Off |
| └ Touch interaction policy | Direct touch only: the hold behaviours above | Off |
| └ Pointer speed | Trackpad only: 0.5×–2.0× in 0.1 steps, pointer travel only | 1.0× |
| Console mode | Docked / Handheld | Handheld |
| Interface language | Launcher and in-game interface language | System |
| Advanced → Game rumble | Vibration on the phone or a controller | Off |
| Advanced → Rumble strength | Shown only while rumble is on | 1.0 |
| Advanced → Frame-rate counter | Frame rate in the top-left corner | Off |
| Advanced → Performance HUD | Apple's performance overlay | Off |
| Advanced → Touch feedback | Haptic click on gamepad buttons | Off |
| Advanced → Show right stick in 3D mode | Display only; disabled while the gamepad is not in use (the saved value is kept) | Off |

Advanced is collapsed by default; tapping anywhere on its row (title, gap or chevron) opens it.

**Changing the input mode resets the mode's own options.** Switching to another mode returns all three to their
defaults - disable touch off, touch policy off, pointer speed 1.0x - so an option the last mode left behind cannot keep
acting in the new one. Only a real change resets them: opening the launcher, or re-selecting the mode already set,
leaves your settings alone (and they are still saved as usual).

**The question mark beside "Input mode"** opens a short guide to the current mode, with the other two a tap away.
It closes without changing anything on the launcher.

### macOS

| Setting | Meaning | Default |
|---|---|---|
| Console mode | Docked / Handheld | Handheld |
| Experimental mouse control | Mouse pointer and the Dungeon1 pointer bridge; off also disables the two-finger swipe | On |
| Interface language | Launcher and in-game interface language | System |
| Advanced → Frame-rate counter | Frame rate display | Off |
| Advanced → Game rumble | Controller vibration | Off |
| Advanced → Rumble strength | Shown only while rumble is on | 1.0 |
| Advanced → Performance HUD | Apple's performance overlay | Off |
| Advanced → Touch interaction policy | Hold town portraits for details; purchase/upgrade policies apply only to iOS/iPadOS direct touch | Off |

The Mac launcher also has the resource, save and MOD folders and an About page.

**Saved settings are kept across upgrades**; the defaults above apply to a first install.

---

## 6. Known limitations

- **The two-finger swipe is not a general mouse wheel.** It is a piece of game touch, so it only works where the game
  accepts a drag or a swipe.
- **The trinket storage and similar lists may not scroll**; drag their scrollbar instead.
- **A hold in the trackpad mode takes about a second**: half of it is the port putting the contact down at the
  pointer, the other half is the game's own long-press threshold. Releasing early cancels it instead of clicking.
- **A two-finger swipe over a draggable item drags it.** That is the game's own behaviour, not a bug; park the pointer
  beside the item if you only want to scroll.
- **The torch's brightness change is still unverified** (see example D).
- **Vibration depends on the hardware**: an iPad usually has no haptic engine, so game rumble comes from a supported
  controller; touch feedback is a light UI haptic and depends on the device too.
- There is no separate swipe-sensitivity setting on the Mac; the drag distance follows the game.

---

## 7. Frequently asked questions

**Why can't one finger drag an item?**
Because one finger only moves the pointer and sends no touch. That is what prevents "hover a trinket, touch again,
and pick it up by accident". Use two fingers to drag.

**How do I drag an item?**
Put the pointer on it and move two fingers together - no pause needed. Lift either finger to drop it.

**How do I double-click?**
Move the pointer onto the target and tap twice quickly. The game applies its own double-click rule.

**Why doesn't a two-finger swipe scroll some lists?**
The game only responds where it accepts a drag. If a list does not move, drag its scrollbar; some panels need a
selection first.

**How do I dim the torch?**
Put the pointer on the torch's area and swipe down with two fingers. If nothing happens, check that the pointer is
really on the torch - the arrow is where the game's pointer is.

**Why does a long press take so long?**
In the trackpad mode the finger has to stay still for about half a second before the port presses at the pointer, and
the game's own long-press threshold needs about another half second - roughly one second in total. For a press that
starts at once, use **Direct touch** with "Touch interaction policy" on.

**Will a hold turn into a click when I let go?**
No. If the game has not taken it as a long press yet, the press is withdrawn; once it has, the game ends it by its own
rules.

**How do I drag with a MacBook trackpad?**
Either press the trackpad and move (same as holding the left button) or swipe with two fingers (a game touch drag).
The first is for ordinary dragging, the second for lists and the torch.

**How do I switch to direct touch?**
Quit the game → launcher → **Input mode** → **Direct touch** → start the game. The choice is remembered.

**Why is there no vibration on my iPad?**
Check that Advanced → Game rumble is on. Even then, an iPad usually has no haptic engine, so rumble comes from a
supported controller; touch feedback is a light UI haptic and depends on the device.

**Does pointer speed change where a click lands?**
No. It only changes how fast the pointer moves; a click always lands where the pointer is.

---

For anything not covered here, open the question mark beside **Input mode** in the launcher, or see the more
detailed settings guide in [user-guide.md](user-guide.md).
