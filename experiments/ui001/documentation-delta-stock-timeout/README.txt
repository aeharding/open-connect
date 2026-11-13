DOCUMENTATION-ONLY DELTA TO IMMUTABLE UI001 FINAL16 PROFILE

Original ../freeze.json and test-evidence/20261113T052952.388551Z remain unchanged.
record.json identifies all seven unchanged executable source files, their exact
pre-test snapshots and hashes, the eight frozen30 dependency pins, and current
before/after documentation copies. This delta does not revise code/wire semantics
or claim a new test run. The original frozen README/index remain in pre-test
copies; updated working documents are represented separately here.

Workspace-relative notes/ui001-timeout-decision.txt permits only
stock finite6s/47s BusyBox timeout watchers as a narrow implementation preference
exception, not a custom persistent helper/schedule. Nominal stock1.19.2 source
miscutils/timeout.c daemonizes a grandchild, polls numeric grandparent PID and
signals that PID; the original process execs the requested shell. No watched
starttime/full-argv binding exists. PID reuse, signal/scheduling/kernel behavior
and unknown CMU vendor patches limit independence/deadline/cleanup claims.
The local shim validates a contract, not BusyBox implementation equivalence.
Actual inner child cleanup still needs owned PID/PPID/start/full argv and TERM.

Workspace-relative notes/ui001-review-revision2.txt resolves the
practical code review for ONE exact sleep4 only after separate t6 handoff.
No live child/UI was executed by the developer. No UI authorization follows
from this delta or successful capability proof.

t13's byte audit establishes original watchdog-body recoverability from the
retained exact4108B rendered request by one in-memory run-assignment replacement
matching4084B original template hash. Other original source reproducibility
remains unproven. No reconstructed original was required or written here.
