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

## Public offline checks

Install the host package from the repository root, then run:

~~~sh
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m unittest discover -s experiments/mapped-publication -v
~~~

These checks require no captured firmware, candidate files or CMU. They use
synthetic boot records, the real Bundle API and actual host files/links/memory
mappings. Device stat/mount boundaries are shimmed; this is not RelFS proof.

Importing helpers does not validate a historical run or read private inputs.
Current persistence parsing is in src/open_connect/startup.py. Live command and
restart entry points still validate runtime dependencies before creating a bundle,
opening UART or starting video. The saved execution manifest no longer matches
this checkout and remains unchanged: live execution is refused pending a separately
qualified current profile. Passing these offline checks does not renew old authority.

Feature building still needs exact private OEM inputs and an explicitly selected
candidate profile; it validates those only when requested. The older plan builder's
saved baseline/retained-device paths are not a portable installation recipe.

Feature finding from the first run: the old native wrapper incorrectly read the
outer event's app word as the event ID. The manager actually dereferences the
payload at +12 and reads event ID at +4. The corrected native C and caller-shaped
host fixture are in experiments/disclaimer-native/. See current run results for
feature acceptance; successful publication alone is not a bypass.
