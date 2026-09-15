# Goal: Active Window Injection (Whisp)

Modify the text injection process to use a GNOME Shell D-Bus call to locate and focus the window named "Whisp" before injecting text via `ydotool`. If the window cannot be found or focused, the injection step will gracefully abort with an error, ensuring that the rest of the transcription pipeline (like clipboard copy and daily note generation) continues without interruption.

## References

*   **Facts:** [facts.md](facts.md) - The shared understanding and requirements.
*   **Plan:** [plan.md](plan.md) - The execution steps and approach.

## Done Condition

The text injection functionality successfully focuses the "Whisp" window via D-Bus and injects transcribed text into it. If the "Whisp" window is absent or cannot be focused, the module displays an error and skips injection, but other enabled transcription outputs still execute successfully. Any required GNOME extensions do not interfere with the OSD.
