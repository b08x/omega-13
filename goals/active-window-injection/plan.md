# Active Window Injection Plan

## Solution Approach

To ensure transcribed text is injected specifically into the "Whisp" window without aborting other transcription outputs:

1.  **Modify `src/omega13/injection.py`**:
    *   Introduce a new helper function `_focus_whisp_window()` that executes a `gdbus` command targeting GNOME Shell (`org.gnome.Shell`) to locate and focus the window named "Whisp".
    *   Update `inject_text(text: str)` to call `_focus_whisp_window()` *before* invoking `ydotool`.
    *   If focusing fails, `inject_text` will immediately return `False` and an error message, skipping the `ydotool` execution. This natively satisfies the requirement to abort injection on failure while allowing the overarching transcription pipeline (`src/omega13/transcription.py`) to continue unimpeded.

## Ordered Steps

1.  **Add `_focus_whisp_window()` helper**
    *   **File:** `src/omega13/injection.py`
    *   **Action:** Add function executing the GNOME Shell D-Bus call via `subprocess.run(["gdbus", ...])`.

2.  **Integrate focus step into `inject_text()`**
    *   **File:** `src/omega13/injection.py`
    *   **Action:** Call the new helper at the start of `inject_text`. Return early with an error if focusing fails.

3.  **Validate `transcription.py` error handling**
    *   **File:** `src/omega13/transcription.py`
    *   **Action:** Verify that `success, error_msg = inject_text(...)` gracefully handles the `False` return value by triggering `injection_error_callback` without halting subsequent steps like clipboard copy and file output.

## Verification

1.  **Step 1 & 2 (Focus and Inject):**
    *   Open a target window named "Whisp".
    *   Trigger an injection event.
    *   Verify the "Whisp" window gains focus and receives the typed text.
2.  **Step 3 (Fallback/Error Handling):**
    *   Close or rename the "Whisp" window.
    *   Trigger an injection event.
    *   Verify the OSD/logs report an injection error, but clipboard and daily note generation still succeed.

## Risks and Open Questions

*   **GNOME Wayland D-Bus Restrictions:** Modern GNOME Shell versions (41+) restrict arbitrary window management via D-Bus (e.g., `org.gnome.Shell.Eval` is often disabled). Depending on the system, finding and focusing a window by title may require a GNOME extension (like "Window Calls" or "Run or Raise") or a custom D-Bus interface. If the native `org.gnome.Shell` lacks this capability, we will need to determine the specific D-Bus path/method available on the user's environment.
