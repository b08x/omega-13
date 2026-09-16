# Goal: OSD Visual Cues & GTK4 Decoupling

## Articulated Goal

Add recording-studio tally-light visual cues (blinking red for recording, pulsing amber for processing, solid green for success, steady red for error, dim green/blue for idle) to both the GNOME extension OSD and the GTK4 OSD. Decouple the GTK4 OSD from the daemon process to resolve Wayland/Vulkan conflicts by moving it to a subprocess that communicates via D-Bus signals. Tighten all 25 broad exception handlers in headless_service.py and transcription.py to use narrowed catches with proper traceback logging.

## Shared Understanding

See `facts.md` for the 12 accepted facts that define the verifiable outcomes.

## Execution Plan

See `plan.md` for the 8-step ordered implementation, including files touched, verification commands, risks, and the OSC alternative analysis.

## Done Condition

All 12 facts in `facts.md` are verified: the GNOME extension renders state-based tally-light colors, the daemon emits OSDStateChanged D-Bus signals, the GTK4 OSD runs as a separate process spawned and killed by the daemon, all 25 broad exception blocks are narrowed with proper logging, existing tests pass, and new tests cover signal emission, subprocess lifecycle, and error handling paths.
