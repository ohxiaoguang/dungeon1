"""The Mac front end's two-finger swipe, and the shared adapter behind it, checked at the source level.

The behaviour itself is driven in `dm/host/tests/t_swipe.c` (through the real touch layer); what is checked here is the
wiring that makes that behaviour reachable, and the guarantees around it: a scroll wheel event still goes to Mouse HID
unchanged, the swipe is this title only, inertia and a held button never move the contact, the pointer is never moved
by it, no button is pressed, and every way a gesture can end cleans the contact up.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / 'dm/host/front_mac.m'
SWIPE = ROOT / 'dm/host/dm_swipe.h'


def method(source: str, signature: str) -> str:
    """The *definition* of a method (the @interface also declares it), from its signature to the closing brace."""
    at = 0
    while True:
        at = source.index(signature, at)
        line = source[at:source.index('\n', at)]
        if '{' in line:                       # a definition opens a body on its own line; a declaration ends with ';'
            body = source[at:]
            return body[:body.index('\n}\n')]
        at += len(signature)


class MacSwipeWiring(unittest.TestCase):
    def test_the_wheel_still_reaches_mouse_hid_unchanged(self):
        scroll = method(FRONT.read_text(), '- (void)scrollWheel:')
        self.assertIn('dm_mouse_scroll(e.scrollingDeltaX, e.scrollingDeltaY);', scroll)
        self.assertIn('[self publishMouse:e];', scroll)
        self.assertIn('[self swipeWheel:e];', scroll)
        # and it is still the same early-out for a build with the mouse switch off
        self.assertIn('if (!dm_mouse_enabled()) { [super scrollWheel:e]; return; }', scroll)

    def test_the_swipe_is_this_title_only(self):
        source = FRONT.read_text()
        enabled = method(source, 'static int front_swipe_enabled(void)')
        self.assertIn('dm_mouse_enabled()', enabled)                       # the launcher's mouse switch
        self.assertIn('!strcmp(DM_GAME_ID, "01008F1008DA6000")', enabled)   # Dungeon1, nothing else
        body = method(source, '- (void)swipeWheel:')
        self.assertIn('if (!front_swipe_enabled()', body)
        # a real wheel's line deltas are not a two-finger swipe
        self.assertIn('!e.hasPreciseScrollingDeltas', body)

    def test_inertia_and_a_held_button_never_move_the_contact(self):
        body = method(FRONT.read_text(), '- (void)swipeWheel:')
        # Inertia arrives with the fingers off the glass: it ends the contact instead of driving it.
        self.assertIn('if (e.momentumPhase != NSEventPhaseNone) { [self swipeEnd:NO]; return; }', body)
        # A left-button drag owns the input; the swipe gets out of its way rather than sharing the touch.
        self.assertIn('if (_mouseButtons & DM_MOUSE_LEFT) { [self swipeEnd:NO]; return; }', body)
        # MayBegin means the fingers are resting, so nothing is published yet.
        self.assertIn('if (e.phase & NSEventPhaseMayBegin) return;', body)
        # The momentum branch must come before anything that could open a contact.
        self.assertLess(body.index('momentumPhase'), body.index('dm_swipe_begin'))

    def test_the_gesture_end_lifts_and_a_focus_loss_cancels(self):
        source = FRONT.read_text()
        body = method(source, '- (void)swipeWheel:')
        self.assertIn('if (e.phase & (NSEventPhaseEnded | NSEventPhaseCancelled)) { [self swipeEnd:YES]; return; }', body)
        end = method(source, '- (void)swipeEnd:')
        self.assertIn('if (lift) dm_touch_set_from(NULL, 0, DM_CONTACT_MAC_SWIPE);', end)
        self.assertIn('else dm_touch_cancel_from(DM_CONTACT_MAC_SWIPE);', end)
        self.assertIn('dm_swipe_end(&_swipe);', end)
        # Losing the window cancels it: a lift there could still arrive as the game's Tap.
        focus = method(source, '- (void)mouseFocusChanged:')
        self.assertIn('[self swipeEnd:NO];', focus)
        # A real drag taking over also cancels, so the two never share one contact.
        self.assertIn('- (void)mouseDown:(NSEvent *)e { [self swipeEnd:NO];', source)

    def test_the_idle_timeout_ends_a_contact_nobody_ended(self):
        source = FRONT.read_text()
        arm = method(source, '- (void)swipeArm')
        self.assertIn('DM_SWIPE_IDLE_NS', arm)
        self.assertIn('dm_swipe_idle(&view->_swipe, dm_swipe_now_ns())', arm)
        self.assertIn('[view swipeEnd:YES];', arm)
        # It is armed when the contact opens, so a phase-less device cannot leave it pressed.
        self.assertIn('[self swipeArm];', method(source, '- (void)swipeWheel:'))
        # The timeout must be shorter than the title's 0.5 s Press promotion.
        self.assertIn('#define DM_SWIPE_IDLE_NS 300000000ull', SWIPE.read_text())

    def test_the_swipe_never_moves_the_pointer_or_presses_a_button(self):
        body = method(FRONT.read_text(), '- (void)swipeWheel:')
        self.assertNotIn('dm_mouse_set(', body)      # the system pointer and the HID sample stay put
        self.assertNotIn('dm_mouse_scroll(', body)
        self.assertNotIn('_mouseButtons |=', body)   # no button is ever pressed by a swipe
        self.assertNotIn('dm_touch_set_from(NULL', body)   # only swipeEnd lifts it
        # It opens at the pointer, from the same conversion the mouse path uses.
        self.assertIn('[self pointerPosition:e x:&x y:&y]', body)
        self.assertIn('dm_swipe_begin(&_swipe, now, x, y);', body)
        self.assertIn('DM_CONTACT_MAC_SWIPE', body)

    def test_the_picture_rectangle_matches_the_pointer_conversion(self):
        source = FRONT.read_text()
        picture = method(source, '- (NSRect)pictureRect')
        # The contact's travel is scaled by the picture, which is the rectangle dm_mouse_position normalizes within.
        self.assertIn('16.0 / 9.0', picture)
        self.assertIn('self.bounds.size', picture)
        body = method(source, '- (void)swipeWheel:')
        self.assertIn('(float)pic.size.width, (float)pic.size.height', body)


if __name__ == '__main__':
    unittest.main()
