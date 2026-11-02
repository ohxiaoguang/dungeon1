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

    /* The tap window must stay under the recognizer's 0.5 s Press threshold, and the drag pause under the tap
       window: a release can then never manufacture a contact the game would have promoted to Press. */
    assert(DM_TRACKPAD_TAP_NS < 500000000ull);
    assert(DM_TRACKPAD_DRAG_HOLD_NS < DM_TRACKPAD_TAP_NS);

    const float slop = dm_trackpad_slop(1280);   /* the recognizer's threshold, in points at full picture size */
    dm_tp_gesture g; float dx = 0, dy = 0;

    /* 1. A tap: putting the finger down publishes nothing, and the release is one click. */
    dm_tp_reset(&g);
    assert(dm_tp_down(&g, 0, 1, 400, 300, 0, 0) == DM_TP_NONE);
    assert(g.state == DM_TP_SINGLE);
    assert(dm_tp_up(&g, 120 * MS, 0) == DM_TP_CLICK);
    assert(g.state == DM_TP_IDLE);

    /* 2. A wobble inside the slop is still that tap. */
    dm_tp_reset(&g);
    assert(dm_tp_down(&g, 0, 1, 400, 300, 0, 0) == DM_TP_NONE);
    assert(dm_tp_move(&g, 10 * MS, 1, 400 + slop * 0.9f, 300 + slop * 0.9f, 0, 0, slop, &dx, &dy) == DM_TP_NONE);
    assert(dm_tp_up(&g, 200 * MS, 0) == DM_TP_CLICK);

    /* 3. Leaving the slop moves the cursor and can never click: the first move reports the whole offset from where
       the finger went down (no travel is lost at the crossing), every later one its own delta. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 400, 300, 0, 0);
    assert(dm_tp_move(&g, 16 * MS, 1, 400, 300 + slop + 0.5f, 0, 0, slop, &dx, &dy) == DM_TP_CURSOR);
    assert(dx == 0 && fabsf(dy - (slop + 0.5f)) < 1e-4f);
    assert(dm_tp_move(&g, 33 * MS, 1, 410, 320, 0, 0, slop, &dx, &dy) == DM_TP_CURSOR);
    assert(dx == 10 && fabsf(dy - (20 - (slop + 0.5f))) < 1e-4f);
    assert(dm_tp_up(&g, 100 * MS, 0) == DM_TP_NONE);              /* a swipe never clicks */

    /* 4. A still finger held past the tap window is inert, however long it stays and whenever it lifts: this is what
       used to become the game's Press and start a pickup, a purchase or a skill toggle. */
    dm_tp_reset(&g);
    assert(dm_tp_down(&g, 0, 1, 640, 360, 0, 0) == DM_TP_NONE);
    assert(dm_tp_up(&g, 600 * MS, 0) == DM_TP_NONE);
    assert(dm_tp_up(&g, 3000 * MS, 0) == DM_TP_NONE);             /* the same answer on a second release */

    /* 5. A long hold that then moves is a cursor move, and its release still publishes nothing. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 640, 360, 0, 0);
    assert(dm_tp_move(&g, 700 * MS, 1, 640, 360 + slop + 1, 0, 0, slop, &dx, &dy) == DM_TP_CURSOR);
    assert(dm_tp_up(&g, 800 * MS, 0) == DM_TP_NONE);

    /* 6. Two fingers that move before the pause are a swipe: one contact at the pointer, following the fingers - the
       game's own touch drag, which is what its lists and the torch answer to. It is a separate state from the drag,
       so it can never turn into one (or into a click), and its release lifts the contact. */
    dm_tp_reset(&g);
    assert(dm_tp_down(&g, 0, 1, 300, 300, 0, 0) == DM_TP_NONE);
    assert(dm_tp_down(&g, 40 * MS, 2, 300, 300, 500, 400) == DM_TP_NONE);
    assert(g.state == DM_TP_TWO);
    assert(dm_tp_move(&g, 60 * MS, 2, 300, 300 - (slop + 2), 500, 400 - (slop + 2), slop, &dx, &dy) == DM_TP_SWIPE_DOWN);
    assert(g.state == DM_TP_SCROLL);
    assert(dx == 0 && dy == -(slop + 2));                     /* the travel past the slop, from the two-finger pivot */
    assert(dm_tp_move(&g, 100 * MS, 2, 300, 260, 500, 360, slop, &dx, &dy) == DM_TP_SWIPE_MOVE);
    assert(dx == 0 && dy == -29);                             /* and then each move's own delta */
    assert(dm_tp_move(&g, 2000 * MS, 2, 300, 200, 500, 300, slop, &dx, &dy) == DM_TP_SWIPE_MOVE);   /* never a drag */
    assert(dm_tp_up(&g, 2100 * MS, 1) == DM_TP_SWIPE_UP);
    assert(dm_tp_up(&g, 2200 * MS, 0) == DM_TP_NONE);
    assert(g.state == DM_TP_IDLE);

    /* 6b. A swipe and a drag are mutually exclusive in both directions: once the pause has been served the gesture is
       a drag and never becomes a swipe, and a swipe can never click. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 300, 300, 0, 0);
    dm_tp_down(&g, 10 * MS, 2, 300, 300, 500, 500);
    assert(dm_tp_move(&g, 400 * MS, 2, 340, 340, 540, 540, slop, &dx, &dy) == DM_TP_DRAG_DOWN);
    assert(dm_tp_move(&g, 900 * MS, 2, 380, 380, 580, 580, slop, &dx, &dy) == DM_TP_DRAG_MOVE);
    assert(dm_tp_up(&g, 950 * MS, 0) == DM_TP_DRAG_UP);

    /* 6c. A third finger ends a swipe's contact (cancelled, never lifted), and a cancellation does the same. */
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

    /* 7. Two fingers that pause and then move are a drag: the contact starts at the cursor as it is then, and the
       later movement is published as the contact's own travel. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 300, 300, 0, 0);
    dm_tp_down(&g, 100 * MS, 2, 300, 300, 500, 500);              /* pivot (400,400) */
    assert(dm_tp_move(&g, 300 * MS, 2, 305, 305, 505, 505, slop, &dx, &dy) == DM_TP_NONE);   /* still inside */
    assert(g.state == DM_TP_TWO);
    assert(dm_tp_move(&g, 420 * MS, 2, 340, 320, 540, 520, slop, &dx, &dy) == DM_TP_DRAG_DOWN);
    assert(dx == 40 && dy == 20);
    assert(g.state == DM_TP_DRAG);
    assert(dm_tp_move(&g, 440 * MS, 2, 360, 330, 560, 530, slop, &dx, &dy) == DM_TP_DRAG_MOVE);
    assert(dx == 20 && dy == 10);
    assert(dm_tp_up(&g, 500 * MS, 1) == DM_TP_DRAG_UP);
    /* the finger left on the glass may not click, move or drag anything */
    assert(dm_tp_move(&g, 520 * MS, 1, 100, 100, 0, 0, slop, &dx, &dy) == DM_TP_NONE);
    assert(dm_tp_up(&g, 600 * MS, 0) == DM_TP_NONE);
    assert(g.state == DM_TP_IDLE);

    /* 8. A third finger ends a drag safely: the contact is cancelled, never lifted. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 300, 300, 0, 0);
    dm_tp_down(&g, 50 * MS, 2, 300, 300, 500, 500);
    assert(dm_tp_move(&g, 400 * MS, 2, 340, 340, 540, 540, slop, &dx, &dy) == DM_TP_DRAG_DOWN);
    assert(dm_tp_down(&g, 450 * MS, 3, 700, 700, 0, 0) == DM_TP_CONTACT_CANCEL);
    assert(g.state == DM_TP_CANCELLED);
    assert(dm_tp_move(&g, 460 * MS, 3, 340, 340, 540, 540, slop, &dx, &dy) == DM_TP_NONE);
    assert(dm_tp_up(&g, 500 * MS, 2) == DM_TP_NONE);

    /* 9. A cancellation (focus loss, a system gesture) never clicks, and a drag's contact is cancelled. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 640, 360, 0, 0);
    assert(dm_tp_cancel(&g) == DM_TP_NONE);
    assert(dm_tp_up(&g, 100 * MS, 0) == DM_TP_NONE);
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 300, 300, 0, 0);
    dm_tp_down(&g, 10 * MS, 2, 300, 300, 500, 500);
    assert(dm_tp_move(&g, 400 * MS, 2, 340, 340, 540, 540, slop, &dx, &dy) == DM_TP_DRAG_DOWN);
    assert(dm_tp_cancel(&g) == DM_TP_CONTACT_CANCEL);

    /* 10. Two taps in a row are two clicks: the game sees two Taps and decides for itself that a quick pair is a
       double tap, exactly as it did with physical touches. */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 500, 400, 0, 0);
    assert(dm_tp_up(&g, 120 * MS, 0) == DM_TP_CLICK);
    dm_tp_down(&g, 300 * MS, 1, 500, 400, 0, 0);
    assert(dm_tp_up(&g, 400 * MS, 0) == DM_TP_CLICK);

    /* 11. The two-finger slop is per axis, like the recognizer's: a diagonal drift that stays inside it on both axes
       leaves the gesture undecided (and therefore silent). */
    dm_tp_reset(&g);
    dm_tp_down(&g, 0, 1, 300, 300, 0, 0);
    dm_tp_down(&g, 10 * MS, 2, 300, 300, 500, 500);
    assert(dm_tp_move(&g, 900 * MS, 2, 300 + slop * 0.9f, 300 + slop * 0.9f,
                                        500 + slop * 0.9f, 500 + slop * 0.9f, slop, &dx, &dy) == DM_TP_NONE);
    assert(g.state == DM_TP_TWO);

    /* 12. A finger count going straight from 1 to 2 in one event (both landed together) is the same gesture. */
    dm_tp_reset(&g);
    assert(dm_tp_down(&g, 0, 2, 300, 300, 500, 500) == DM_TP_NONE);
    assert(g.state == DM_TP_TWO);
    assert(dm_tp_move(&g, 400 * MS, 2, 340, 340, 540, 540, slop, &dx, &dy) == DM_TP_DRAG_DOWN);

    /* The cursor stays on the picture. */
    assert(dm_trackpad_clamp(-0.5f) == 0);
    assert(dm_trackpad_clamp(0.25f) == 0.25f);
    assert(dm_trackpad_clamp(1.5f) == 0.999f);

    /* The slop follows the picture, not the pointer speed: at every gain the launcher offers the same finger travel
       is a movement (the stroke publishes a position, never a touch, so there is no published-pixel threshold to
       keep above any more). */
    {
        const float widths[] = {852, 932, 1180, 1280};
        for (unsigned i = 0; i < sizeof widths / sizeof *widths; i++) {
            const float w = widths[i], s = dm_trackpad_slop(w);
            assert(s > 0);
            dm_tp_reset(&g);
            dm_tp_down(&g, 0, 1, 100, 100, 0, 0);
            assert(dm_tp_move(&g, 16 * MS, 1, 100, 100 + s + 0.001f, 0, 0, s, &dx, &dy) == DM_TP_CURSOR);
            assert(dm_tp_up(&g, 20 * MS, 0) == DM_TP_NONE);
            /* the arrow's tip is the panel point, for a full-size picture and a letterboxed one */
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
            {0, 0, 1280, 720},          /* a picture that fills the view */
            {114, 0, 932, 524.25f},     /* letterboxed in a wider window */
            {0, 148, 852, 479.25f},     /* letterboxed above and below (a tall window) */
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
        /* the panel's own corner is the picture's corner, and the far corner stays inside the picture */
        float vx, vy;
        dm_trackpad_arrow_tip(0, 0, 114, 0, 932, 524.25f, &vx, &vy);
        assert(vx == 114 && vy == 0);
        dm_trackpad_arrow_tip(1279, 719, 114, 0, 932, 524.25f, &vx, &vy);
        assert(vx > 114 && vx < 114 + 932 && vy > 0 && vy < 524.25f);
        /* a view with no picture yet must not produce a NaN tip */
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

    def test_the_only_contacts_are_a_click_and_a_drag(self):
        gamepad = (ROOT / 'dm/ios/Sources/DmGamepad.m').read_text()
        # The tap's contact is down and up in one turn, so it can never be read as a hold.
        click = _method(gamepad, '- (void)clickAtCursor {')
        self.assertIn('[self publishTouch:YES]; [self publishTouch:NO];', click)
        self.assertEqual(click.count('publishTouch'), 2)
        # A contact is published nowhere else except the two two-finger gestures, which open it on purpose and move it
        # after: a drag (a carried item) and a swipe (the game's own touch drag, for the torch and the lists).
        published = gamepad.count('[self publishTouch:YES]')
        self.assertEqual(published, 5, 'a click, drag down/move, swipe down/move')
        self.assertIn('[self publishTouch:YES]', _method(gamepad, '- (void)swipeBy:'))
        self.assertNotIn('[self publishTouch:YES]', _method(gamepad, '- (void)trackpadBegan:'))
        # A click is produced by exactly one transition, and only on release.
        ended = _method(gamepad, '- (void)trackpadEnded:')
        self.assertIn('if (a == DM_TP_CLICK) [self clickAtCursor];', ended)
        self.assertEqual(gamepad.count('clickAtCursor]'), 1)
        # A cancelled gesture cancels, never lifts: a lift could still arrive as the game's Tap.
        self.assertIn('if (dm_tp_cancel(&_tp) == DM_TP_CONTACT_CANCEL) dm_touch_cancel_from(DM_CONTACT_IOS);', ended)
        # Each contact is released only by its own gesture's end.
        self.assertIn('else if (a == DM_TP_DRAG_UP) { [self publishTouch:NO];', ended)
        self.assertIn('else if (a == DM_TP_SWIPE_UP) { [self publishTouch:NO];', ended)
        # A swipe runs through the shared adapter (dm/host/dm_swipe.h), the same one the Mac front end uses, and the
        # pointer follows it so the arrow and the contact stay on one pixel.
        swipe = _method(gamepad, '- (void)swipeBy:')
        self.assertIn('dm_swipe_move(&_swipe', swipe)
        self.assertIn('_cursor.x = nx; _cursor.y = ny;', swipe)
        # The drag opens where the pointer is and does not move it in the same call, so the game's hit test sees the
        # item the player picked rather than a point a few pixels further on.
        moved = _method(gamepad, '- (void)trackpadMoved:')
        down_case = moved[moved.index('case DM_TP_DRAG_DOWN:'):moved.index('case DM_TP_DRAG_MOVE:')]
        self.assertIn('[self publishTouch:YES]', down_case)
        self.assertNotIn('moveCursorBy', down_case)

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
        # A drag tints it, so a carried item reads differently from a hover.
        self.assertIn('_dragging ? [UIColor colorWithRed:', gamepad)

    def test_the_gesture_is_reset_with_the_overlay(self):
        gamepad = (ROOT / 'dm/ios/Sources/DmGamepad.m').read_text()
        reset = _method(gamepad, '- (void)reset {')
        self.assertIn('[_tpTouches removeAllObjects]', reset)
        self.assertIn('dm_tp_reset(&_tp)', reset)
        self.assertIn('_dragging = _swiping = NO', reset)
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
