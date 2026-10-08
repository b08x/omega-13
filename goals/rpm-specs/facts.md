# Facts

- A dedicated packaging directory `packaging/rpm/` is created to contain all RPM spec files, system integration assets, and build automation scripts.
- An `omega13.spec` file packages Omega-13 for Fedora 40+ and EPEL 9/10 using modern `%pyproject_*` macros, installing the `omega13` CLI binary and required runtime dependencies.
- `omega13.spec` defines a `gnome-shell-extension-omega13` subpackage that installs extension files to `%{_datadir}/gnome-shell/extensions/omega13@b08x.github.io` following Fedora GNOME extension guidelines.
- `omega13.spec` packages system integration assets including a systemd user service (`omega13.service`) in `%{_userunitdir}` and a D-Bus session service (`org.omega13.Recorder.service`) in `%{_datadir}/dbus-1/services/`.
- A `python-transcribe-cpp.spec` file packages `transcribe-cpp` supporting CPU builds by default and optional CUDA and Vulkan hardware acceleration via `%bcond_with` flags.
- Standalone spec files `python-JACK-Client.spec` and `python-dbus-next.spec` are provided for dependencies that require packaging in target enterprise/EPEL environments.
- A `ydotool.spec` file and accompanying systemd user service unit are provided in `packaging/rpm/` for Wayland text injection support.
- A build script `packaging/rpm/build.sh` automates source tarball creation, RPM build directory staging, SRPM generation, and binary package compilation.
- The project `Justfile` includes recipes `rpm-build`, `rpm-srpm`, and `rpm-lint` to build and validate all spec files.
- All spec files pass `rpmlint` validation with zero fatal errors or syntax violations according to Fedora/EPEL packaging standards.
