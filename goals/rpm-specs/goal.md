# Goal: Build RPM Spec Files for Omega-13 and Dependencies

## Articulated Goal

Create production-ready RPM `.spec` files, system integration units, and automation tooling for `omega13` and its unbundled dependencies (`transcribe-cpp`, `JACK-Client`, `dbus-next`, and `ydotool`), targeting Fedora 40+ and EPEL 9/10. Package `omega13` with pyproject macros, systemd user services, D-Bus session activation, and a dedicated `gnome-shell-extension-omega13` subpackage, providing automated build/lint recipes via `build.sh` and the project `Justfile`.

## Shared Understanding

See `facts.md` for the 10 accepted facts that define the verifiable outcomes.

## Execution Plan

See `plan.md` for the ordered 7-step implementation plan, including affected files, verification commands, and risk mitigations.

## Done Condition

All 10 facts in `facts.md` are verified: `packaging/rpm/` contains valid spec files for `omega13` (with GNOME extension subpackage and systemd user services), `python-transcribe-cpp` (with CUDA/Vulkan bcond flags), `python-JACK-Client`, `python-dbus-next`, and `ydotool`; `packaging/rpm/build.sh` and `Justfile` recipes (`just rpm-build`, `just rpm-srpm`, `just rpm-lint`) successfully stage and build packages; and all spec files pass `rpmlint` validation with zero fatal errors.
