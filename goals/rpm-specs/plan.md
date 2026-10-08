# Plan: Build RPM Spec Files for Omega-13 and Dependencies

## Solution Approach

This plan establishes RPM packaging for `omega13` and its dependencies, targeting Fedora 40+ and EPEL 9/10 according to modern RPM packaging standards (using `%pyproject_*` macros, systemd user service scriptlets, and GNOME Shell extension packaging conventions).

The solution encompasses:
1. **Directory layout**: Storing all specs, service units, and packaging scripts in `packaging/rpm/`.
2. **Main package spec (`omega13.spec`)**: Packages the Python CLI/daemon using modern pyproject macros, includes systemd user unit and D-Bus session activation, and creates a `gnome-shell-extension-omega13` subpackage.
3. **Hardware-accelerated C++ dependency spec (`python-transcribe-cpp.spec`)**: Packages `transcribe-cpp` with `%bcond_with cuda` and `%bcond_with vulkan` conditionals, building CPU-only by default.
4. **Target-environment Python dependency specs**: `python-JACK-Client.spec` and `python-dbus-next.spec` for enterprise/EPEL environments where these packages are unbundled or absent from core repositories.
5. **Wayland injection tool spec (`ydotool.spec`)**: Packages `ydotool` and `ydotoold` with daemon user service integration.
6. **Automation & Developer Workflows**: Standalone `packaging/rpm/build.sh` script and `Justfile` recipes (`just rpm-build`, `just rpm-srpm`, `just rpm-lint`) providing end-to-end building and `rpmlint` validation.

---

## Ordered Steps

### Step 1: Initialize Packaging Directory and System Integration Assets

**Files:**
- `packaging/rpm/omega13.service`
- `packaging/rpm/org.omega13.Recorder.service`
- `packaging/rpm/ydotoold.service`

**Details:**
- Create `packaging/rpm/` directory.
- Create `omega13.service` systemd user service unit configured to launch `/usr/bin/omega13 --no-daemon` after `pipewire.service` and `sound.target`.
- Create `org.omega13.Recorder.service` D-Bus session bus activation file pointing to `/usr/bin/omega13 --no-daemon` and referencing `SystemdService=omega13.service`.
- Create `ydotoold.service` systemd user service unit to manage the `ydotoold` daemon socket/process.

**Verification:**
- Inspect files for required systemd and D-Bus syntax.
- Verify file locations under `packaging/rpm/`.

---

### Step 2: Implement Main Application Spec File (`omega13.spec`) and GNOME Extension Subpackage

**Files:**
- `packaging/rpm/omega13.spec`

**Details:**
- Define package metadata (Name: `omega13`, Version: matching `pyproject.toml`, License: MIT/Apache-2.0, URL).
- Utilize modern Fedora/EPEL Python macros: `%pyproject_buildrequires`, `%pyproject_wheel`, and `%pyproject_install`.
- Define runtime dependencies: `python3-gobject`, `python3-cairo`, `gtk4-layer-shell`, `python3-numpy`, `python3-soundfile`, `python3-requests`, `python3-rich`, `python3-pynput`, `python3-pyperclip`, `sox`, `ffmpeg`, and `pipewire-jack-audio-connection-kit`.
- Install `omega13.service` into `%{_userunitdir}` and enable systemd user scriptlets (`%systemd_user_post`, `%systemd_user_preun`, `%systemd_user_postun`).
- Install D-Bus session service into `%{_datadir}/dbus-1/services/org.omega13.Recorder.service`.
- Define `gnome-shell-extension-omega13` subpackage installing `gnome-extension/omega13@b08x.github.io` into `%{_datadir}/gnome-shell/extensions/omega13@b08x.github.io`.
- Define `%files` sections cleanly separating core CLI/daemon binaries and the GNOME extension.

**Verification:**
- Run `rpm -q --specfile packaging/rpm/omega13.spec --qf "%{name}-%{version}\n"` to verify syntax parsing.
- Run `rpmlint packaging/rpm/omega13.spec` to confirm macro validity and compliance.

---

### Step 3: Implement C++ Whisper Dependency Spec (`python-transcribe-cpp.spec`)

**Files:**
- `packaging/rpm/python-transcribe-cpp.spec`

**Details:**
- Define spec for `transcribe-cpp` Python extension.
- Include build conditionals:
  - `%bcond_with cuda` (disabled by default; requires CUDA toolkit and passes `-DTRANSCRIBE_CUDA=ON`)
  - `%bcond_with vulkan` (disabled by default; requires `vulkan-headers`, `vulkan-loader-devel` and passes `-DTRANSCRIBE_VULKAN=ON`)
- Require `cmake`, `gcc-c++`, `python3-devel`, `python3-pip`, `python3-wheel`, `python3-setuptools`.
- Build wheel with CMake environment arguments and install via `%pyproject_install`.
- Add runtime check in `%check` (importing `transcribe_cpp`).

**Verification:**
- Run `rpmlint packaging/rpm/python-transcribe-cpp.spec`.
- Validate bcond handling with `rpmbuild --nobuild --with cuda packaging/rpm/python-transcribe-cpp.spec`.

---

### Step 4: Implement Additional Dependency Specs (`python-JACK-Client.spec`, `python-dbus-next.spec`)

**Files:**
- `packaging/rpm/python-JACK-Client.spec`
- `packaging/rpm/python-dbus-next.spec`

**Details:**
- Create `python-JACK-Client.spec` building `JACK-Client` using `pipewire-jack-audio-connection-kit-devel` / `jack-audio-connection-kit-devel` and `python3-cffi`.
- Create `python-dbus-next.spec` building `dbus-next` pure Python package with pyproject macros.
- Include license tags, doc files, and automatic provides/requires generation.

**Verification:**
- Run `rpmlint packaging/rpm/python-JACK-Client.spec packaging/rpm/python-dbus-next.spec`.

---

### Step 5: Implement Wayland Injection Tool Spec (`ydotool.spec`)

**Files:**
- `packaging/rpm/ydotool.spec`

**Details:**
- Define spec for `ydotool` and `ydotoold`.
- Require `cmake`, `gcc-c++`, `scdoc`.
- Install binaries `/usr/bin/ydotool` and `/usr/bin/ydotoold`.
- Install user unit `ydotoold.service` into `%{_userunitdir}`.

**Verification:**
- Run `rpmlint packaging/rpm/ydotool.spec`.

---

### Step 6: Create Packaging Automation Script (`packaging/rpm/build.sh`)

**Files:**
- `packaging/rpm/build.sh`

**Details:**
- Implement executable bash script `packaging/rpm/build.sh`.
- Options:
  - `--prep`: Generate source tarballs from repository and place in `~/rpmbuild/SOURCES` or local `build/SOURCES`.
  - `--srpm`: Build source RPMs (`.src.rpm`) for omega13 and specified dependencies.
  - `--rpm`: Build binary RPM packages.
  - `--lint`: Run `rpmlint` across all spec files.
  - `--all`: Prep, lint, and build SRPMs.
- Handle directory initialization (`mkdir -p rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}`).

**Verification:**
- Run `bash packaging/rpm/build.sh --help`.
- Run `bash packaging/rpm/build.sh --lint`.

---

### Step 7: Integrate Justfile Recipes and End-to-End Lint Validation

**Files:**
- `Justfile`

**Details:**
- Add recipe `rpm-lint` calling `packaging/rpm/build.sh --lint` (or `rpmlint packaging/rpm/*.spec`).
- Add recipe `rpm-srpm` calling `packaging/rpm/build.sh --srpm`.
- Add recipe `rpm-build` calling `packaging/rpm/build.sh --rpm`.
- Validate that all spec files adhere to Fedora and EPEL packaging rules with zero fatal errors in `rpmlint`.

**Verification:**
- Execute `just rpm-lint`.
- Execute `just rpm-srpm` to confirm source packaging works.

---

## Risks and Open Questions

1. **CUDA Build Dependencies in Clean Chroots**:
   - Building `python-transcribe-cpp` with CUDA requires the proprietary or non-free NVIDIA CUDA toolkit, which is not present in standard Fedora/EPEL repositories. The spec defaults to CPU-only (`%bcond_with cuda`), ensuring standard builds and mock environments succeed without external repositories.
2. **Pyproject Macro Availability on Older EPEL**:
   - EPEL 9 provides `pyproject-rpm-macros`, but some newer sub-macros differ slightly from Fedora Rawhide. The specs use standard conditional checks (`%if 0%{?rhel}`) to maintain dual compatibility without breaking Rawhide builds.
