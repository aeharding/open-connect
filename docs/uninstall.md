# Uninstall direction

**Working direction; product uninstall and conflict recovery are not implemented.**
The broad intent below reflects our discussions. The mechanics remain open.

## Intended experience

- Uninstall returns affected files to their saved pre-install state. That state
  may already contain other mods; it is not necessarily factory stock.
- If another mod changed those files, save their current state before restoring
  the originals, and explain what uninstall will replace.
- Let the user reverse that conflict-uninstall using the saved state.
- If relevant state changes again before recovery, stop and preserve it.
  Do not force an overwrite or attempt another merge/recovery layer.

## Still to design

What belongs in the saved state, where it lives, how interruption is handled,
and when it can be discarded. The boot-selection architecture may change the
answers; a file-by-file procedure would be premature.

The first installer implementation should test these expectations against real
install, conflict, uninstall and recovery cases. Existing trial tools prove some
pieces, not the complete product behavior.

Tracking: [USB developer preview #7](https://github.com/aeharding/open-connect/issues/7).
