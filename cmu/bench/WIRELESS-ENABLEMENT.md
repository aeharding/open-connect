# Native wireless enablement experiment

This playground experiment tests one question on exact **74.00.324A NA**: do
Mazda's wireless service arguments and two Device Manager capability flags enable
native wireless operation while preserving actual board and GPS configuration?
It is not an installer feature or a performance/vehicle qualification.

`wireless-service-config.awk` transforms the hash-verified original normal SM
configuration. Six wireless service arguments and the wireless firewall mode
match the corresponding OEM wireless entries. Navigation, location, AAPA hardware
selection, reset/retry policy and board detection retain their original values.
One finite preparation process depends on VBS; Device Manager depends on its
ready flag. No native service initialization, cleanup or heartbeat is replaced.

`wireless-device-config.awk` changes only `bWifiSupport` and `bOOBSupport` in
Mazda's generated RAM XML. The boot trial must stage its output, check the source
has not changed, then publish atomically before signaling ready. Never publish
partial output after an unsuccessful filter. The physical master XML stays
original, so Mazda continues rendering the real vehicle/location values.

OEM inputs, generated configuration, credentials and captures stay private.
Record actual source hashes, boot IDs, applied flags, service state, pairing,
projection and restoration before drawing conclusions. A menu or an access point
alone does not establish usable wireless CarPlay.

The first private boot attempt restored the original startup inode, then refused
selection because an early read-only remount returned `EBUSY`. Neither wireless
flag was applied. A fresh post-startup check restored the read-only mount and
verified the original inode. Keep that tooling failure separate from wireless
behavior. The revised trial consumes its one-shot before selection, then restores
startup from the retained original inode after boot; it does not remount root
during Mazda's early initialization.

The revised boot reached native wireless projection. Native Devices settings
exposed Wi-Fi and the CarPlay page; selecting the OEM Apple CarPlay Wi-Fi mode
started an AP on channel 6. The owner re-paired iPhone Bluetooth before its
wireless Connect button became available, then connected and moved phone USB to
the Mac. Independent intake found no CMU phone USB link, one Wi-Fi station
exchanging traffic and a visible CarPlay dashboard on the physical display.
Record re-pairing as an observed setup step, not a reason to erase pairings
automatically. Actual phone model/iOS and audio/input performance are unqualified.

The two generated XML values changed from FALSE to TRUE; every other byte of
Mazda's rendered configuration was preserved. Physical master XML, board script,
SM files and native modules stayed original. Startup was subsequently restored
to its original inode with read-only physical root. This leaves the current
wireless services loaded until a separate restart. Stock restart, saved AP-mode
behavior, repeated connection and maintained installer integration remain next.
