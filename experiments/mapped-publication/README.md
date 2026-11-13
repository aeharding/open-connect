# Native library publication with inode holds

The CMU kept a removed native-library inode mapped after replacement. Its RelFS
root refused a read-only remount. Keeping a same-filesystem hardlink to each
loaded image fixes that lifetime issue without modifying mapped bytes.

The first live cycle proved apply → candidate boot → undo → original boot →
hold cleanup, with physical root read-only after every mutation. RelFS can still
label the old mapping pathname (deleted) even while the inode has a verified
hold link. Bind the inode and known aliases, not that label alone.

linked.sh.in is the independent persistent apply/verify/undo/cleanup program.
bench.py reuses the existing Session and DATA staging code. boot.py reuses the
existing video, boot parser and one-login loop. Each run retains its own plan,
source copies, originals, candidate, code and actual results under private runs/.

Tests exercise the actual shell copy/link/rename path with real open files and
memory mappings. Host shims cover device-specific stat/mount boundaries, not
RelFS implementation. The observer check uses the real Bundle API.

Feature finding from the first run: the old native wrapper incorrectly read the
outer event's app word as the event ID. The manager actually dereferences the
payload at +12 and reads event ID at +4. The corrected native C and caller-shaped
host fixture are in experiments/disclaimer-native/. See current run results for
feature acceptance; successful publication alone is not a bypass.
