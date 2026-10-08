%global pypi_name omega13
%global uuid      omega13@b08x.github.io

Name:           %{pypi_name}
Version:        2.7.4
Release:        1%{?dist}
Summary:        Retroactive audio recorder and transcription daemon with GTK4 OSD

License:        MIT
URL:            https://github.com/b08x/omega-13
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
Source1:        omega13.service
Source2:        org.omega13.Recorder.service

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  systemd-rpm-macros

Requires:       python3-cairo
Requires:       python3-dbus-next
Requires:       python3-gobject
Requires:       python3-jack-client
Requires:       python3-numpy
Requires:       python3-pynput
Requires:       python3-pyperclip
Requires:       python3-requests
Requires:       python3-rich
Requires:       python3-soundfile
Requires:       python3-transcribe-cpp
Requires:       gtk4-layer-shell
Requires:       ffmpeg
Requires:       sox
Requires:       pipewire-jack-audio-connection-kit

Recommends:     gnome-shell-extension-omega13 = %{version}-%{release}
Recommends:     ydotool

%description
Omega-13 is a retroactive audio recorder and transcription daemon with a GTK4
OSD. It captures audio continuously via JACK into an in-memory ring buffer,
detects voice activity or responds to hotkey triggers, transcribes speech
locally or via cloud providers, and outputs text to clipboard, active window,
or Obsidian daily notes.

%package -n     gnome-shell-extension-omega13
Summary:        GNOME Shell extension for Omega-13 OSD integration
BuildArch:      noarch
Requires:       gnome-shell
Requires:       omega13 = %{version}-%{release}

%description -n gnome-shell-extension-omega13
GNOME Shell extension providing native on-screen display (OSD) feedback and
window activation integration for the Omega-13 audio recorder daemon.

%prep
%autosetup -n %{pypi_name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l %{pypi_name}

# Install systemd user unit
install -D -p -m 0644 %{SOURCE1} %{buildroot}%{_userunitdir}/omega13.service

# Install D-Bus session activation service
install -D -p -m 0644 %{SOURCE2} %{buildroot}%{_datadir}/dbus-1/services/org.omega13.Recorder.service

# Install GNOME Shell extension
mkdir -p %{buildroot}%{_datadir}/gnome-shell/extensions/%{uuid}
cp -a gnome-extension/%{uuid}/* %{buildroot}%{_datadir}/gnome-shell/extensions/%{uuid}/
rm -f %{buildroot}%{_datadir}/gnome-shell/extensions/%{uuid}/*.zip

%check
%pyproject_check_import

%post
%systemd_user_post omega13.service

%preun
%systemd_user_preun omega13.service

%postun
%systemd_user_postun_with_restart omega13.service

%files -f %{pyproject_files}
%license LICENSE
%doc README.md
%{_bindir}/omega13
%{_userunitdir}/omega13.service
%{_datadir}/dbus-1/services/org.omega13.Recorder.service

%files -n gnome-shell-extension-omega13
%dir %{_datadir}/gnome-shell/extensions/%{uuid}
%{_datadir}/gnome-shell/extensions/%{uuid}/*

%changelog
* Wed Oct 07 2026 b08x <b08x@users.noreply.github.com> - 2.7.4-1
- Initial RPM packaging for Fedora and EPEL
- Add gnome-shell-extension-omega13 subpackage
- Add systemd user service and D-Bus session activation
