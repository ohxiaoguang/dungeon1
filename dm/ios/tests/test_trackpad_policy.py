"""Exercise the virtual trackpad's gesture policy and the input-mode value, without UIKit or a device.

Both live in headers the iPhone overlay compiles: dm/host/dm_input.h (DM_TOUCH_INPUT's values, the parser the
overlay, the launcher and the iOS pointer handoff share, and the panel-point conversion all three use) and
dm/ios/Sources/TouchTrackpadPolicy.h (what a touch means). The rules that matter, and why:

  · a finger that goes down publishes nothing - that is the fix for "hovering an item and touching the glass again
    started dragging it", because the contact that picked the item up no longer exists until a gesture says so;
  · a quick still tap publishes one contact at the cursor (the game's own Tap, its click), while leaving the slop,
    or staying down longer than a tap, publishes nothing at all;
  · two fingers that move before the pause are a scroll intent and stay inert; two that pause and then move are a
    drag, and a gesture that has chosen one of those can never become the other, a click, or a second contact.

The checks at the end of this file also assert the overlay keeps those rules (no publication on a touch-down, no
touch from a cursor move, a click only from the click path) and that this build imports no mouse at all - which is
why the scroll gesture is left unimplemented rather than guessed at.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / 'dm/host/dm_input.h'
POLICY = ROOT / 'dm/ios/Sources/TouchTrackpadPolicy.h'
MAIN_PATCHED = ROOT / 'out/work-ios/prepared/patched_v393216/main.patched.bin'

CHECKS = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "dm_input.h"
#include "TouchTrackpadPolicy.h"

#define MS 1000000ull

int main(void) {
    /* DM_TOUCH_INPUT: the old switch still means what it meant, and one new value names the trackpad. */
    assert(dm_touch_input_mode(NULL) == DM_TOUCH_INPUT_ON);         /* unset: as before */
    assert(dm_touch_input_mode("") == DM_TOUCH_INPUT_ON);
    assert(dm_touch_input_mode("1") == DM_TOUCH_INPUT_ON);          /* saved by the switch-only build */
    assert(dm_touch_input_mode("0") == DM_TOUCH_INPUT_OFF);         /* ditto */
    assert(dm_touch_input_mode("2") == DM_TOUCH_INPUT_ON);          /* any other number stays "on", as atoi had it */
    assert(dm_touch_input_mode("yes") == DM_TOUCH_INPUT_OFF);       /* and a non-number stays "off", as atoi had it */
    assert(dm_touch_input_mode(DM_TOUCH_INPUT_TRACKPAD_VALUE) == DM_TOUCH_INPUT_TRACKPAD);
    assert(dm_touch_input_mode("Trackpad") == DM_TOUCH_INPUT_OFF);  /* the value is exact, never case-folded */

    /* The tap window is under the hold window, and the hold is the recognizer's own 0.5 s Press threshold: a release
       can then never manufacture a contact the game would have promoted to Press. */
    assert(DM_TRACKPAD_TAP_NS < DM_TRACKPAD_HOLD_NS);
    assert(DM_TRACKPAD_HOLD_NS == 500000000ull);

    const float slop = dm_trackpad_slop(1280);   /* the recognizer's threshold, in points at full picture size */
    dm_tp_gesture g; float dx = 0, dy = 0;

    /* 1. A tap: putting the finger down publishes nothing, and the release is one click. */
    dm_tp_reset(&g);
    assert(dm_tp_down(&g, 0, 1, 400, 300, 0, 0) == DM_TP_NONE);
    assert(g.state == DM_TP_SINGLE);
    assert(dm_tp_hold(&g, 100 * MS) == DM_TP_NONE);      /* the hold window has not passed yet */
    assert(dm_tp_up(&g, 120 * MS, 0) == DM_TP_CLICK);
    assert(g.state == DM_TP_IDLE);

    /* 1b. A tap's timer must not turn into a hold afterwards: the gesture is gone. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 400, 300, 0, 0);
    dm_tp_up(&g, 120 * MS, 0);
    assert(dm_tp_hold(&g, 900 * MS) == DM_TP_NONE);

    /* 2. A wobble inside the slop is still that tap. */
    dm_tp_reset(&g);
    assert(dm_tp_down(&g, 0, 1, 400, 300, 0, 0) == DM_TP_NONE);
    assert(dm_tp_move(&g, 10 * MS, 1, 400 + slop * 0.9f, 300 + slop * 0.9f, 0, 0, slop, &dx, &dy) == DM_TP_NONE);
    assert(dm_tp_up(&g, 200 * MS, 0) == DM_TP_CLICK);

    /* 3. Leaving the slop moves the cursor and can never click or hold: the first move reports the whole offset from
       where the finger went down, every later one its own delta. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 400, 300, 0, 0);
    assert(dm_tp_move(&g, 16 * MS, 1, 400, 300 + slop + 0.5f, 0, 0, slop, &dx, &dy) == DM_TP_CURSOR);
    assert(dx == 0 && fabsf(dy - (slop + 0.5f)) < 1e-4f);
    assert(dm_tp_move(&g, 33 * MS, 1, 410, 320, 0, 0, slop, &dx, &dy) == DM_TP_CURSOR);
    assert(dx == 10 && fabsf(dy - (20 - (slop + 0.5f))) < 1e-4f);
    assert(dm_tp_hold(&g, 900 * MS) == DM_TP_NONE);      /* a moving finger is never a hold */
    assert(dm_tp_up(&g, 1000 * MS, 0) == DM_TP_NONE);    /* and a swipe never clicks */

    /* 4. A still finger past the hold window opens ONE contact at the pointer - this is the game's own long press.
       Releasing it before the game's Press threshold cancels it (a lift there could arrive as a Tap), and releasing
       it later lifts it so the game can end the hold itself. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 640, 360, 0, 0);
    assert(dm_tp_hold(&g, 400 * MS) == DM_TP_NONE);
    assert(dm_tp_hold(&g, 520 * MS) == DM_TP_HOLD_DOWN);
    assert(g.state == DM_TP_HOLDING);
    assert(dm_tp_hold(&g, 600 * MS) == DM_TP_NONE);      /* it opens once, not once per tick */
    assert(dm_tp_up(&g, 700 * MS, 0) == DM_TP_CONTACT_CANCEL);   /* only 0.18 s of contact: no Press yet */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 640, 360, 0, 0);
    assert(dm_tp_hold(&g, 520 * MS) == DM_TP_HOLD_DOWN);
    assert(dm_tp_up(&g, 1100 * MS, 0) == DM_TP_HOLD_UP);          /* the contact outlived the Press threshold */

    /* 5. Moving out of a hold cancels the contact instead of dragging with it, and the gesture then ignores the
       finger until it lifts. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 640, 360, 0, 0);
    assert(dm_tp_hold(&g, 520 * MS) == DM_TP_HOLD_DOWN);
    assert(dm_tp_move(&g, 600 * MS, 1, 640, 360 + slop + 1, 0, 0, slop, &dx, &dy) == DM_TP_CONTACT_CANCEL);
    assert(g.state == DM_TP_CANCELLED);
    assert(dm_tp_move(&g, 700 * MS, 1, 640, 400, 0, 0, slop, &dx, &dy) == DM_TP_NONE);
    assert(dm_tp_up(&g, 800 * MS, 0) == DM_TP_NONE);

    /* 6. A second finger during a hold cancels it: a hold and a two-finger swipe never mix. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 640, 360, 0, 0);
    assert(dm_tp_hold(&g, 520 * MS) == DM_TP_HOLD_DOWN);
    assert(dm_tp_down(&g, 600 * MS, 2, 640, 360, 800, 500) == DM_TP_CONTACT_CANCEL);
    assert(g.state == DM_TP_CANCELLED);

    /* 7. Two fingers: one contact at the pointer, following their midpoint - the game's own touch drag. */
    dm_tp_reset(&g);
    assert(dm_tp_down(&g, 0, 1, 300, 300, 0, 0) == DM_TP_NONE);
    assert(dm_tp_down(&g, 40 * MS, 2, 300, 300, 500, 400) == DM_TP_NONE);
    assert(g.state == DM_TP_TWO);
    assert(dm_tp_move(&g, 60 * MS, 2, 300, 300 - (slop + 2), 500, 400 - (slop + 2), slop, &dx, &dy) == DM_TP_SWIPE_DOWN);
    assert(g.state == DM_TP_SWIPE);
    assert(dx == 0 && dy == -(slop + 2));                     /* the travel past the slop, from the midpoint */
    assert(dm_tp_move(&g, 100 * MS, 2, 300, 260, 500, 360, slop, &dx, &dy) == DM_TP_SWIPE_MOVE);
    assert(dx == 0 && dy == -29);                             /* and then each move's own delta */
    assert(dm_tp_up(&g, 200 * MS, 1) == DM_TP_SWIPE_UP);
    assert(dm_tp_up(&g, 220 * MS, 0) == DM_TP_NONE);
    assert(g.state == DM_TP_IDLE);

    /* 8. Waiting first changes nothing: there is one two-finger path, not a second "deliberate drag". */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 300, 300, 0, 0);
    dm_tp_down(&g, 10 * MS, 2, 300, 300, 500, 500);
    assert(dm_tp_hold(&g, 900 * MS) == DM_TP_NONE);            /* two fingers never open a single-finger hold */
    assert(dm_tp_move(&g, 1200 * MS, 2, 340, 340, 540, 540, slop, &dx, &dy) == DM_TP_SWIPE_DOWN);
    assert(g.state == DM_TP_SWIPE);
    assert(dm_tp_move(&g, 1300 * MS, 2, 380, 380, 580, 580, slop, &dx, &dy) == DM_TP_SWIPE_MOVE);
    assert(dm_tp_up(&g, 1400 * MS, 0) == DM_TP_SWIPE_UP);

    /* 9. Two fingers that never move publish nothing at all: no click, no purchase. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 300, 300, 0, 0);
    dm_tp_down(&g, 10 * MS, 2, 300, 300, 500, 500);
    assert(dm_tp_move(&g, 600 * MS, 2, 302, 301, 501, 502, slop, &dx, &dy) == DM_TP_NONE);
    assert(dm_tp_up(&g, 900 * MS, 1) == DM_TP_NONE);
    assert(dm_tp_up(&g, 950 * MS, 0) == DM_TP_NONE);

    /* 10. A third finger ends an open swipe contact; so does an explicit cancel. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 300, 300, 0, 0);
    dm_tp_down(&g, 10 * MS, 2, 300, 300, 500, 400);
    assert(dm_tp_move(&g, 60 * MS, 2, 300, 260, 500, 360, slop, &dx, &dy) == DM_TP_SWIPE_DOWN);
    assert(dm_tp_down(&g, 80 * MS, 3, 700, 700, 0, 0) == DM_TP_CONTACT_CANCEL);
    assert(dm_tp_move(&g, 90 * MS, 3, 300, 250, 500, 350, slop, &dx, &dy) == DM_TP_NONE);

    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 300, 300, 0, 0);
    dm_tp_down(&g, 10 * MS, 2, 300, 300, 500, 400);
    assert(dm_tp_move(&g, 60 * MS, 2, 300, 260, 500, 360, slop, &dx, &dy) == DM_TP_SWIPE_DOWN);
    assert(dm_tp_cancel(&g) == DM_TP_CONTACT_CANCEL);

    /* 11. Cancelling a tap never clicks, and after a cancellation the next touch starts clean. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 640, 360, 0, 0);
    assert(dm_tp_cancel(&g) == DM_TP_NONE);
    assert(dm_tp_up(&g, 100 * MS, 0) == DM_TP_NONE);
    dm_tp_reset(&g);
    dm_tp_down(&g, 200 * MS, 1, 500, 400, 0, 0);
    assert(dm_tp_up(&g, 300 * MS, 0) == DM_TP_CLICK);

    /* 12. Two taps are two clicks: the game decides for itself that a quick pair is a double tap. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 500, 400, 0, 0);
    assert(dm_tp_up(&g, 120 * MS, 0) == DM_TP_CLICK);
    dm_tp_down(&g, 300 * MS, 1, 500, 400, 0, 0);
    assert(dm_tp_up(&g, 400 * MS, 0) == DM_TP_CLICK);

    /* 13. The two-finger slop is per axis, like the recognizer's: a diagonal drift that stays inside it leaves the
       gesture silent. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 300, 300, 0, 0);
    dm_tp_down(&g, 10 * MS, 2, 300, 300, 500, 500);
    assert(dm_tp_move(&g, 900 * MS, 2, 300 + slop * 0.9f, 300 + slop * 0.9f,
                                        500 + slop * 0.9f, 500 + slop * 0.9f, slop, &dx, &dy) == DM_TP_NONE);
    assert(g.state == DM_TP_TWO);

    /* 14. Both fingers landing in one event is the same gesture. */
    dm_tp_reset(&g);
    assert(dm_tp_down(&g, 0, 2, 300, 300, 500, 500) == DM_TP_NONE);
    assert(g.state == DM_TP_TWO);
    assert(dm_tp_move(&g, 400 * MS, 2, 340, 340, 540, 540, slop, &dx, &dy) == DM_TP_SWIPE_DOWN);

    /* The cursor stays on the picture. */
    assert(dm_trackpad_clamp(-0.5f) == 0);
    assert(dm_trackpad_clamp(0.25f) == 0.25f);
    assert(dm_trackpad_clamp(1.5f) == 0.999f);

    /* The slop follows the picture, not the pointer speed, and the arrow's tip is the panel point. */
    {
        const float widths[] = {852, 932, 1180, 1280};
        for (unsigned i = 0; i < sizeof widths / sizeof *widths; i++) {
            const float w = widths[i], s = dm_trackpad_slop(w);
            assert(s > 0);
            dm_tp_reset(&g);
            dm_tp_down(&g, 0, 1, 100, 100, 0, 0);
            assert(dm_tp_move(&g, 16 * MS, 1, 100, 100 + s + 0.001f, 0, 0, s, &dx, &dy) == DM_TP_CURSOR);
            assert(dm_tp_up(&g, 20 * MS, 0) == DM_TP_NONE);
            int px, py; dm_panel_point(0.5f, 0.5f, &px, &py);
            float vx, vy;
            dm_trackpad_arrow_tip(px, py, 0, 0, w, w * 9.0f / 16.0f, &vx, &vy);
            assert(fabsf(vx - w * 0.5f) < 0.5f && fabsf(vy - w * 9.0f / 32.0f) < 0.5f);
            dm_trackpad_arrow_tip(px, py, 114, 0, 932, 524.25f, &vx, &vy);
            assert(vx > 114 && vx < 114 + 932);
        }
    }

    /* The arrow's tip has to be the game's own pointer: mapping the panel point back into the picture must land on
       that same panel coordinate - for a picture that fills the view, a letterboxed one and a tall (rotated) one. */
    {
        struct { float ox, oy, w, h; } pics[] = {
            {0, 0, 1280, 720},
            {114, 0, 932, 524.25f},
            {0, 148, 852, 479.25f},
        };
        const float pts[] = {0.f, 0.25f, 0.5f, 0.75f, 0.999f};
        int ok = 1;
        for (unsigned pic = 0; pic < sizeof pics / sizeof *pics; pic++)
            for (unsigned i = 0; i < sizeof pts / sizeof *pts; i++) {
                int px, py; dm_panel_point(pts[i], pts[i], &px, &py);
                float vx, vy;
                dm_trackpad_arrow_tip(px, py, pics[pic].ox, pics[pic].oy, pics[pic].w, pics[pic].h, &vx, &vy);
                float bx = (vx - pics[pic].ox) / pics[pic].w * 1280.0f, by = (vy - pics[pic].oy) / pics[pic].h * 720.0f;
                if (fabsf(bx - (float)px) > 0.01f || fabsf(by - (float)py) > 0.01f) {
                    ok = 0;
                    printf("  picture %u point %u: panel (%d,%d) maps back to (%.3f,%.3f)\n", pic, i, px, py, bx, by);
                }
            }
        assert(ok);
        float vx, vy;
        dm_trackpad_arrow_tip(0, 0, 114, 0, 932, 524.25f, &vx, &vy);
        assert(vx == 114 && vy == 0);
        dm_trackpad_arrow_tip(1279, 719, 114, 0, 932, 524.25f, &vx, &vy);
        assert(vx > 114 && vx < 114 + 932 && vy > 0 && vy < 524.25f);
        dm_trackpad_arrow_tip(640, 360, 0, 0, 0, 0, &vx, &vy);
        assert(vx == 0 && vy == 0);
    }

    printf("trackpad policy ok\n");
    return 0;
}
'''


def _method(source: str, signature: str) -> str:
    """The body of one Objective-C method, from its signature to the closing brace at column 0."""
    body = source[source.index(signature):]
    return body[:body.index('\n}\n')]


class TrackpadPolicy(unittest.TestCase):
    def test_mode_and_gestures(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'check.c'
            source.write_text(CHECKS)
            binary = Path(root) / 'check'
            subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(INPUT.parent), '-I' + str(POLICY.parent),
                            str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_a_touch_down_publishes_nothing(self):
        """The regression this round exists for: putting a finger on the glass must not create a game contact."""
        gamepad = (ROOT / 'dm/ios/Sources/DmGamepad.m').read_text()
        began = _method(gamepad, '- (void)trackpadBegan:')
        self.assertIn('dm_tp_down', began)
        self.assertNotIn('publishTouch', began)     # no contact, so nothing can be picked up or pressed
        self.assertNotIn('clickAtCursor', began)
        self.assertNotIn('dm_touch_set_from', began)   # no contact is ever created by a touch-down
        # The one thing a down may do is cancel a contact that a third finger interrupted - never lift it.
        self.assertEqual(began.count('dm_touch_cancel'), 1)
        self.assertIn('a == DM_TP_CONTACT_CANCEL', began)
        # Same for a move: it only moves the cursor.
        moved = _method(gamepad, '- (void)trackpadMoved:')
        self.assertIn('dm_tp_move', moved)
        self.assertIn('[self moveCursorBy:', moved)
        # A move publishes a contact only inside the drag branches, never on the cursor path.
        move_cursor = _method(gamepad, '- (void)moveCursorBy:')
        self.assertIn('[self publishPointer]', move_cursor)
        self.assertNotIn('dm_touch', move_cursor)

    def test_the_only_contacts_are_a_click_a_hold_and_a_swipe(self):
        gamepad = (ROOT / 'dm/ios/Sources/DmGamepad.m').read_text()
        # The tap's contact is down and up in one turn, so it can never be read as a hold.
        click = _method(gamepad, '- (void)clickAtCursor {')
        self.assertIn('[self publishTouch:YES]; [self publishTouch:NO];', click)
        self.assertEqual(click.count('publishTouch'), 2)
        # Four publications in the whole overlay: the tap, the hold that a still finger opens, the two-finger down and
        # the swipe's own moves. Nothing else ever puts a contact into the game.
        published = gamepad.count('[self publishTouch:YES]')
        self.assertEqual(published, 4, 'click, hold, swipe down, swipe move')
        self.assertIn('[self publishTouch:YES]', _method(gamepad, '- (void)swipeBy:'))
        self.assertNotIn('[self publishTouch:YES]', _method(gamepad, '- (void)trackpadBegan:'))
        self.assertNotIn('[self publishTouch:YES]', _method(gamepad, '- (void)trackpadMoved:').split('case DM_TP_SWIPE_DOWN:')[0])
        # A click is produced by exactly one transition, and only on release.
        ended = _method(gamepad, '- (void)trackpadEnded:')
        self.assertIn('if (a == DM_TP_CLICK) [self clickAtCursor];', ended)
        self.assertEqual(gamepad.count('clickAtCursor]'), 1)
        # A cancelled gesture cancels, never lifts: a lift could still arrive as the game's Tap.
        self.assertIn('if (dm_tp_cancel(&_tp) == DM_TP_CONTACT_CANCEL) dm_touch_cancel_from(DM_CONTACT_IOS);', ended)
        # Each contact is released only by its own gesture's end, and an unfinished hold is cancelled.
        self.assertIn('else if (a == DM_TP_HOLD_UP) { [self publishTouch:NO];', ended)
        self.assertIn('else if (a == DM_TP_CONTACT_CANCEL) { dm_touch_cancel_from(DM_CONTACT_IOS);', ended)
        self.assertIn('else if (a == DM_TP_SWIPE_UP) { [self publishTouch:NO];', ended)
        # A swipe runs through the shared adapter (dm/host/dm_swipe.h), the same one the Mac front end uses, and the
        # pointer follows it so the arrow and the contact stay on one pixel.
        swipe = _method(gamepad, '- (void)swipeBy:')
        self.assertIn('dm_swipe_move(&_swipe', swipe)
        self.assertIn('_cursor.x = nx; _cursor.y = ny;', swipe)

    def test_a_still_finger_opens_the_hold_only_after_the_window(self):
        """The regression that created this mode must not come back through the hold."""
        gamepad = (ROOT / 'dm/ios/Sources/DmGamepad.m').read_text()
        began = _method(gamepad, '- (void)trackpadBegan:')
        # A touch-down only starts a timer; the contact is opened later, by the tick, and only if nothing changed.
        self.assertIn('if (_tp.state == DM_TP_SINGLE) [self armHoldTimer];', began)
        self.assertNotIn('publishTouch', began)
        tick = _method(gamepad, '- (void)holdTick {')
        self.assertIn('if (_tp.state != DM_TP_SINGLE || dm_tp_hold(&_tp, dm_touch_now_ns()) != DM_TP_HOLD_DOWN) return;', tick)
        self.assertIn('[self publishPointer];', tick)
        self.assertIn('[self publishTouch:YES];', tick)
        # The timer is armed once per touch-down, at the hold window.
        arm = _method(gamepad, '- (void)armHoldTimer')
        self.assertIn('DM_TRACKPAD_HOLD_NS', arm)
        # Moving with a hold's contact down cancels it instead of dragging with it.
        moved = _method(gamepad, '- (void)trackpadMoved:')
        cancel_case = moved[moved.index('case DM_TP_CONTACT_CANCEL:'):moved.index('case DM_TP_SWIPE_DOWN:')]
        self.assertIn('dm_touch_cancel_from(DM_CONTACT_IOS);', cancel_case)
        self.assertNotIn('moveCursorBy', cancel_case)

    def test_the_published_point_is_the_cursor_never_the_finger(self):
        """The audit's central question: what the game is told about a tap is the cursor, not the glass."""
        gamepad = (ROOT / 'dm/ios/Sources/DmGamepad.m').read_text()
        publish = _method(gamepad, '- (void)publishTouch:')
        self.assertIn('_cursor', publish)
        self.assertNotIn('locationInView', publish)      # the finger's own position must never reach the host
        # The finger is read in tpPoints, which only feeds the gesture policy; the contact is built from the cursor.
        for body in (_method(gamepad, '- (void)moveCursorBy:'), publish):
            self.assertNotIn('locationInView', body)

    def test_the_pointer_speed_scales_the_cursor_only(self):
        """DM_TRACKPAD_SPEED is a gain on the cursor's travel: not on the click, not on the gesture state machine."""
        gamepad = (ROOT / 'dm/ios/Sources/DmGamepad.m').read_text()
        move_cursor = _method(gamepad, '- (void)moveCursorBy:')
        self.assertIn('_pointerGain * dx / pic.size.width', move_cursor)
        self.assertIn('_pointerGain * dy / pic.size.height', move_cursor)
        # The tap's contact and the gesture's thresholds carry no gain at all.
        self.assertNotIn('_pointerGain', _method(gamepad, '- (void)publishTouch:'))
        self.assertNotIn('_pointerGain', _method(gamepad, '- (float)tpSlop {'))
        self.assertIn('dm_trackpad_slop((float)pic.size.width)', gamepad)
        # Its own variable, with a saved fallback, clamped to the range the launcher offers.
        self.assertIn('DM_TRACKPAD_SPEED', gamepad)
        self.assertIn('launcher.DM_TRACKPAD_SPEED', gamepad)
        self.assertIn('fminf(fmaxf(v, 0.5f), 2.0f)', gamepad)
        self.assertIn('trackpad_gain(getenv("DM_TRACKPAD_SPEED")', gamepad)

    def test_the_arrow_is_drawn_only_in_trackpad_mode(self):
        """The pointer is the overlay's own drawing: it must not appear in the two other modes, and it must not be
        able to consume a touch."""
        gamepad = (ROOT / 'dm/ios/Sources/DmGamepad.m').read_text()
        # Created only for the trackpad, and hidden/absent otherwise.
        self.assertIn("if (_trackpad) {\n            // The arrow is this overlay's own", gamepad)
        self.assertIn('_arrow.hidden = !_trackpad;', gamepad)
        self.assertIn('if (!_arrow) return;', gamepad)
        # A CALayer on the view's own layer: it never hides with a physical controller (unlike _controls) and, being a
        # layer and not a view, takes no part in hit testing.
        self.assertIn('[self.layer addSublayer:_arrow];', gamepad)
        self.assertNotIn('addSubview:_arrow', gamepad)
        self.assertNotIn('_arrow.userInteractionEnabled', gamepad)
        self.assertNotIn('_controls addSublayer:_arrow', gamepad)
        # It follows the cursor and every layout change (rotation, split view, Stage Manager).
        self.assertIn('[self layoutArrow]', _method(gamepad, '- (void)moveCursorBy:'))
        self.assertIn('[self layoutArrow]', _method(gamepad, '- (void)layoutSubviews {'))
        # The picture the arrow is mapped into is the one front_ios.m lays the game out with, floor included.
        self.assertIn('floor((b.size.width - w) / 2)', gamepad)
        self.assertIn('floor((b.size.height - h) / 2)', gamepad)
        # A hold tints it orange and a swipe blue, so both read differently from a hover.
        self.assertIn('_holding ? [UIColor colorWithRed:', gamepad)
        self.assertIn('_swiping ? [UIColor colorWithRed:', gamepad)

    def test_the_gesture_is_reset_with_the_overlay(self):
        gamepad = (ROOT / 'dm/ios/Sources/DmGamepad.m').read_text()
        reset = _method(gamepad, '- (void)reset {')
        self.assertIn('[_tpTouches removeAllObjects]', reset)
        self.assertIn('dm_tp_reset(&_tp)', reset)
        self.assertIn('_holding = _swiping = NO', reset)
        self.assertIn('dm_swipe_end(&_swipe)', reset)
        # The trackpad takes every touch of its view, in one call: a per-touch loop could not see a second finger.
        self.assertIn('[self trackpadBegan:ts]', gamepad)
        self.assertIn('[self trackpadMoved:ts]', gamepad)

    def test_this_build_reads_no_mouse_so_the_wheel_is_not_a_scroll_path(self):
        """The scroll gesture is left unimplemented for this reason: main imports no mouse ABI at all, so the Switch
        Mouse HID wheel cannot scroll anything in this game."""
        if not MAIN_PATCHED.exists():
            self.skipTest('the prepared main module is not built here')
        data = MAIN_PATCHED.read_bytes()
        for symbol in (b'InitializeMouse', b'GetMouseState', b'GetMouseStates', b'GetKeyboardState'):
            self.assertEqual(data.count(symbol), 0, symbol.decode())
        # ...while the input it does read is still there, so this is a measurement and not a broken file.
        self.assertGreater(data.count(b'GetNpadState'), 0)
        self.assertGreater(data.count(b'GetGestureStates'), 0)


if __name__ == '__main__':
    unittest.main()
