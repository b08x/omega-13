# Omega-13 Enhancements

## Goal
Enhance the Omega-13 daemon by exposing new UI toggles in the GNOME extension for OSD display and auto-record capabilities. Furthermore, introduce a robust mechanism for retrying failed transcriptions from a temporary manifest, overhaul the CLI config menu, and provide a real-time streaming mode alternative to the retroactive capture flow.

## Fact Sheet
The expected outcomes and behaviors for this goal are outlined in [facts.md](./facts.md).

## Execution Plan
The step-by-step implementation strategy is documented in [plan.md](./plan.md).

## Done Condition
This goal is considered done when:
- The `config.py` defaults are updated and temporary storage uses `/run/user/1000/omega13`.
- The `SessionManager` correctly implements a 10-item failed transcription manifest.
- The GNOME extension displays working toggles for OSD and Auto-Record, an Auto-Record threshold slider, and a responsive "Retry" button.
- The `omega13 --config` wizard is overhauled with a robust menu (e.g., using `gum` or `rich`).
- A 'Streaming Mode' toggle is fully integrated to support real-time continuous transcription.
- Standard desktop notifications are off by default while critical errors continue to show.
