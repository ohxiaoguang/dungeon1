"""Hero status panel: switch, bilingual labels and no fabricated data.

The dynamic behaviour (snapshot follows the selected actor, clears on scene
exit) is verified against the running game; these checks protect the parts a
unit test can see from the source tree.
"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'dm/games/settings.tsv'
CATALOG = ROOT / 'gui/Sources/PackagingModel/Localization.swift'
LAUNCHER = ROOT / 'dm/apple/LauncherSettings.swift'
HERO_C = ROOT / 'dm/host/hle_dd_hero.c'
HERO_H = ROOT / 'dm/host/dd_hero.h'
IOS_FRONT = ROOT / 'dm/ios/Sources/front_ios.m'
MAC_FRONT = ROOT / 'dm/host/front_mac.m'


class HeroPanelSettings(unittest.TestCase):
    def test_switch_defaults_off_and_is_dd_only(self):
        rows = [l for l in SCHEMA.read_text().splitlines()
                if l.startswith('DM_DD_HERO_PANEL\t')]
        self.assertEqual(len(rows), 1, 'exactly one hero panel row')
        cols = rows[0].split('\t')
        self.assertEqual(cols[0], 'DM_DD_HERO_PANEL')
        self.assertEqual(cols[1], 'toggle')
        self.assertEqual(cols[3], '0', 'default must be off')
        self.assertIn('01008F1008DA6000', cols[4], 'Darkest Dungeon only')

    def test_labels_are_bilingual(self):
        cat = CATALOG.read_text()
        self.assertIn('"Character status panel": "角色状态面板"', cat)
        self.assertIn("Click a hero or enemy to show health", cat)

    def test_switch_is_in_advanced(self):
        src = LAUNCHER.read_text()
        start = src.index('func settingPlacement')
        block = src[start:start + 900]
        self.assertIn('"DM_DD_HERO_PANEL"', block)
        self.assertIn('return .advanced', block)

    def test_no_hardcoded_hero_values(self):
        src = HERO_C.read_text()
        # The collector must not invent names, classes or HP/stress values.
        for bad in ('"HP"', '"Stress"', 'hp = 17', 'stress = 24', 'name = @"'):
            self.assertNotIn(bad, src)

    def test_snapshot_is_bounded(self):
        h = HERO_H.read_text()
        self.assertIn('#define DD_HERO_MAX_BUFFS', h)
        self.assertIn('#define DD_HERO_LINE_MAX', h)
        self.assertIn('char line[DD_HERO_LINE_MAX]', h)

    def test_rows_come_from_the_original_chain(self):
        src = HERO_C.read_text()
        # The lines must be produced by the game's own aggregate + row
        # formatter, not by this project's own parsing or translation. The
        # chain bypasses the tray's admission filter (it drops whole stat
        # kinds) but every rendered row is still the game's own text.
        self.assertIn('DD_ORC_AGGREGATE    0xdeba10ull', src)
        self.assertIn('DD_ORC_LINE_FULL    0xdec330ull', src)
        self.assertIn('DD_ORC_FREE         0xe69a20ull', src)
        self.assertIn('line_full(line, row, (void *)(uintptr_t)actor, w5 & 1)', src)
        self.assertNotIn('dd_hero_names.h', src)
        for gone in ('schinese.loc2', 'amount_for', 'suffix', 'label_for'):
            self.assertNotIn(gone, src)

    def test_dot_rows_use_the_games_tray_format(self):
        src = HERO_C.read_text()
        # DoT rows carry a nested key that is MISSING from the game's own
        # tables; the panel re-renders them with the game's own tray format
        # keys instead of showing raw markup, and never shows the markup.
        self.assertIn('hero_tray_format_key', src)
        self.assertIn('tray_icon_tooltip_bleed_format', src)
        self.assertIn('tray_icon_tooltip_poison_format', src)
        self.assertIn('tray_icon_tooltip_stress_dot_format', src)
        self.assertIn("if (strchr(out->line, '<')) continue;", src)
        # Verbatim-identical rows stay collapsed: the tray shows one Finale
        # icon for the damage-low/high pair (user-confirmed).
        self.assertIn('if (dup) continue;', src)

    def test_ui_draws_lines_verbatim(self):
        for front in (IOS_FRONT, MAC_FRONT):
            text = front.read_text()
            self.assertIn('b->line', text)
            self.assertNotIn('b->label', text)
            self.assertNotIn('b->value', text)

    def test_both_front_ends_do_not_take_input(self):
        ios = IOS_FRONT.read_text()
        mac = MAC_FRONT.read_text()
        self.assertIn('userInteractionEnabled = NO', ios)
        self.assertIn('- (NSView *)hitTest:', mac)
        self.assertIn('return nil', mac)


if __name__ == '__main__':
    unittest.main()
