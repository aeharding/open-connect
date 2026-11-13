# Open Connect — living steering agreement

Last updated: 2026-11-13, from the user's explicit direction.

Read this first when starting or resuming work. It records product intent and how
we work; it is not a run log or an approval checklist. New user direction takes
precedence. Update the relevant paragraph when direction changes, removing
contradictions rather than accumulating layers of instructions. Label proposals
as proposals; never silently turn an agent's suggestion into a user decision.

## North star

The project name is **Open Connect**. Use **Mazda Open Connect** as the README
title. The bench is part of the project, not its product identity.

Build an open-source, contribution-friendly Mazda Connect project that improves
reliability and responsiveness while keeping the OEM feel. Features are optional.
Users should be able to install, change, upgrade and uninstall through deliberate
USB maintenance without needing their original stick. Configuration UX and package
compatibility policy remain open.

The autonomous bench and published reverse-engineering knowledge are valuable
deliverables too. The user provides physical resources; the primary agent owns
software implementation, bench operation, testing and recovery.

## Working style: hackathon

**“Elaborate is failure.”** Prefer a working, understandable experiment over
elaborate preparation. Build the smallest complete path from a useful question
to a patch, an actual bench result and undo.

Reverse engineering and code analysis are core work. Understand how the CMU makes
decisions, manages resources and moves through its lifecycle so patches change
the right behavior. Deep investigation is worthwhile when it resolves a concrete
design question. Coordination churn, repeated audits and speculative tooling are
not substitutes for progress.

Pursue the best correct fix. Do not choose a cosmetic workaround merely because
it is easier or less invasive. The dedicated bench exists for experimentation,
including native changes; it is separate from the user's real car. Backups and
recovery enable experiments, rather than becoming an endless prerequisite project.
Bench success does not automatically establish end-user release safety.

## Ownership and execution

- One primary agent owns the complete outcome directly. No standing specialist
  team or delegation of the main work. Any explicitly requested helper is
  ephemeral, answers one specific question, and exits.
- Decide routine implementation details and continue authorized work without
  repeated permission gates. Surface a concrete new risk or missing dependency
  when it changes the experiment; do not invent hypothetical approval chains.
- Keep one bench operator and clean up owned resources. Know what is on disk,
  what is actually loaded, and what state the device is in.
- Reuse working tools. Add tooling only to solve a demonstrated obstacle or remove
  repeated work. Avoid a new framework for each experiment.
- Test concrete failure modes and real entry points. Passing isolated mocks is
  not proof that the integrated runner works. After relevant checks pass, move
  to the useful bench experiment.
- Preserve original bytes and failure evidence, provide independent undo, and
  verify the resulting state. Do not relabel partial or reconciled results as
  an uninterrupted automated pass.
- Answer the user promptly. A status question does not pause the project.
  Report outcome, blocker and next action in plain language; do not flood the
  conversation with duplicated handoffs or leave questions unanswered.

## Current feature direction

The first real feature is startup disclaimer bypass. Understand and modify the
native startup decision while preserving OEM initialization, cleanup, focus,
last-app/audio/display-off behavior and normal frontend lifecycle.

The timer experiment shortened the warning but did not meet the goal. More timer
tuning and visual masking are parked. The native candidate must be evaluated by
actual startup behavior and demonstrated undo, not host tests alone.

Mapped native libraries require installation and recovery behavior that accounts
for loaded inode lifetime. Restoring a disk file does not unload a running module.
Resolve that concrete integration issue without expanding it into a speculative
installer platform.

## Knowledge, progress and maintenance

Keep concise, source-backed findings alongside code: applicable firmware,
what we learned, relevant evidence and remaining uncertainty. Preserve independent
implementation provenance; keep full OEM binaries and private captures out of
published source.

Document after useful results and batch updates. The remotely accessible dashboard
is the user's first progress contact; keep it honest and current after meaningful
milestones without making publication a gate for bench work.

Keep changing device state and the next concrete task in
[the current handoff](notes/afk-session-status.txt), and operational instructions
in [AGENTS.md](AGENTS.md). Product background and open UX questions are in
[the product brief](notes/product-direction.txt); historical assignments there
are not current authority.

Maintain this document when goals or working agreements change, not after every
command. Keep it short enough to read at the start of a session.
