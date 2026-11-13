# Mazda Connect findings

Current evidence is for **55.00.750B North America**. These are findings, not
instructions to apply old trial payloads.

| Question | Finding and source |
| --- | --- |
| Can Entertainment work without the TAU? | The stock Audio Manager API enables silent UI testing. [Native/API review](history/bench-profile-review.md), [CLI result](history/bench-profile-result.md). This does not provide audio output. |
| Where does the disclaimer come from? | Native MMUI selects it before GUI rendering. [Startup flow](history/disclaimer-native-startup-flow.txt). |
| Can startup bypass it cleanly? | A native prototype reused stock continuation rules; a paired GUI hook improved intro cleanup. [Native result](history/native-disclaimer-v2-result.txt), [handoff result](history/native-intro-handoff-result.txt). See the [experiment index](../experiments/README.md). |
| Why can replacing a mapped library block read-only remount? | Loaded inode lifetime matters. Keeping same-filesystem hardlink holds through apply/undo resolved the observed EBUSY case. [Publication implementation](../experiments/mapped-publication/README.md). |
| What caused the startup black gap/spinner? | Intro surfaces, menu transitions and audio startup are separate behaviors. [Black gap](history/native-bypass-black-flash.txt), [loading investigation](history/loading-spinner-investigation.txt). |
| Can we replace the frontend document? | Doing so stopped the OEM heartbeat. Preserve the framework lifecycle. [Finding](history/browser-navigation-finding.txt). |

The [history](history/) contains detailed dated observations and source provenance.
Add useful findings here after experiments; do not maintain parallel notes and
research systems or a second current roadmap.
