# Darkest Dungeon 1.3.0: restore the XML metadata getters used by local MODs.
# The retail XML path finds each node but then formats an error instead of reading
# its value; the JSON path copies the value correctly. All XML MODs consequently
# have the same empty Title (the local UGC identity) and lose their preview path.
# x8 is the node found by the preceding lookup, value is at +8, and x19 is the
# project data object. A self-closing node has a null value: keep the default.
# Each replacement is ldr x1,[x8,#8]; cbz x1,end; add x0,x19,#field;
# mov w2,#0x200; bl strlcpy; nop. No original NSP or MOD file is modified.
CUTS = {
    'ff2bf22565188d11ea0981ee0e2b53ce': [
        (0x8c69b8, '013100f021381991c22f009042280491e0a30991a991ff97',
         '010540f9a10000b46002209102408052c68d16941f2003d5',
         'XML local UGC Title: copy node text to project+0x800, preserving distinct MOD identities'),
        (0x8c71e0, '013100d021381991423100f0429c0391e0a309919f8fff97',
         '010540f9a10000b46002089102408052bc8b16941f2003d5',
         'XML local UGC PreviewIconFile: copy node text to project+0x200'),
    ],
}

# Optional Mac pointer experiment: the Host callback is inert unless explicitly
# enabled. The rewriter checks this original fmov s0,s9 before inserting a gate.
# No mode, auto_flag, tooltip or control-flow branch is patched.
OBS = {
    'ff2bf22565188d11ea0981ee0e2b53ce': [
        (0x8b5dc0, 22, '1e204120', 'input polling finished; optional Mac pointer handoff before UI update'),
        (0xe39118, 24, 'f9400288', 'observe native combat-grid hover and current original action wrapper'),
        # Same straight-line frame path as 0x8b5dc0, five instructions before it and
        # still ahead of the native action-queue drain at 0x8b5dd0: the rewriter only
        # takes an observation at a function entry, after a bl, or where x9-x17 carry
        # nothing to the next call, so the drain's first store cannot carry a gate.
        (0x8b5dac, 25, '1e204120', 'optional touch-policy frame boundary before action-queue drain'),
        (0xe274c0, 26, 'd10143ff', 'invalidate touch authorization when CharacterDisplay starts closing'),
        (0xe3d7d0, 27, 'a9be7bfd', 'invalidate touch authorization before CharacterDisplay destruction'),
        # Same-frame live target for the town roster: the click's primary action
        # was just enqueued (inside 0x73b6d0); the host may append the original
        # details callable once, for a >=0.5 s iOS contact, through 0x717370.
        (0xc60084, 28, 'f9404be0', 'observe the town roster element dispatch after its click was queued'),
        # The merchandise row's own update (0xe13120) tests its click byte at
        # 0xe15690 and dispatches to [x26+0x1d0] two instructions later; the gate
        # replays the ldurb. Read-only diagnostic for the Nomad long-press work:
        # it records the click byte beside every candidate "row under the finger"
        # byte for the verified purchase binding, and is inert unless the Host
        # runs with DM_DD_SHOP_PROBE=1.
        (0xe15690, 29, '385a83a8', 'observe a merchandise row update: click byte and the row flags it is tested with'),
        # The row builder (0xe171c0) has just stored the mode/slot word into a
        # freshly allocated 0x310-byte InventoryButtonInGrid binding (vtable
        # 0x11933a8); x24 holds it. Only the Nomad supply display builds one
        # whose +0x70 is TrinketSupplyDisplay's purchase lambda (vtable
        # 0x117a678), so the Host uses this to know that the merchandise rows are
        # on screen. Read-only: the gate replays the original add.
        (0xe177ac, 30, '910203e0', 'observe a Nomad merchandise row being bound to its purchase action'),
        # The guild's upgrade rows are described through one callback per row
        # (`void(Upgrade::PurchaseIdentifier, GuiTooltipParameters::Text&)`,
        # vtable 0x1177c40, operator 0xc16d20) which runs once per drawn row per
        # frame with the price and the eligibility already resolved. Seeing it run
        # means the upgrade rows are on screen, which is what arms the iOS
        # "tap focuses, hold buys" latch. Read-only: the gate replays the
        # original prologue.
        (0xc16d20, 31, 'd100c3ff', 'observe the guild upgrade row being described (the upgrade rows are on screen)'),
        (0xbf3010, 32, 'd102c3ff', 'observe blacksmith weapon and armour upgrade descriptions'),
        (0xbff6d0, 33, 'aa0203e1', 'observe camping trainer skill descriptions'),
        (0xbfaf70, 34, 'd10103ff', 'observe building upgrade descriptions'),
    ],
}

# A narrow integer-returning entry filter, not a global GUI hit-test patch.
# Off/unsupported Hosts preserve the original arguments/prologue and operation.
FILTERS = {
    'ff2bf22565188d11ea0981ee0e2b53ce': [
        (0xe3b5a0, 1, 'd10203ff', 'optional iOS CharacterDisplay combat-skill authorization; native toggle retained'),
        (0xe3a6d0, 2, 'd101c3ff', 'optional iOS CharacterDisplay camping-skill authorization; native toggle retained'),
        (0xe18410, 3, 'd10083ff', 'optional iOS Nomad merchandise primary binding filter; other inventory callbacks unchanged'),
        (0xe181f0, 4, 'd101c3ff', 'optional iOS Nomad merchandise secondary binding filter before pickup/operation'),
        # UpgradeTreeDisplay click entry, BEFORE eligibility/resource mutation.
        # The host scopes this shared entry to identifiers observed in GuildDisplay.
        # 0xc16320 is a post-purchase notification and is too late to filter.
        (0xc98330, 5, 'a9ba7bfd', 'optional iOS guild upgrade tree click before purchase'),
        (0xc97fc0, 6, 'a9be7bfd', 'optional iOS guild initial unlock before purchase; captured identifier'),
    ],
}
