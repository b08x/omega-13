Name:           ydotool
Version:        1.0.4
Release:        1%{?dist}
Summary:        Generic command-line automation tool for Wayland and X11

License:        AGPL-3.0-only
URL:            https://github.com/ReimuNotMoe/ydotool
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
Source1:        ydotoold.service

BuildRequires:  cmake
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  pkgconfig(systemd)
BuildRequires:  scdoc
BuildRequires:  systemd-rpm-macros

%description
ydotool is a generic command-line automation tool for Linux systems running
Wayland or X11. It performs keyboard, mouse, and input automation actions
without requiring an X server by communicating with the Linux kernel input
subsystem through a background daemon service.

%prep
%autosetup -p1 -n %{name}-%{version}

%build
%cmake -DBUILD_SHARED_LIBS:BOOL=OFF
%cmake_build

%install
%cmake_install
install -D -p -m 0644 %{SOURCE1} %{buildroot}%{_userunitdir}/ydotoold.service

%check
%{buildroot}%{_bindir}/ydotool --help >/dev/null || :

%post
%systemd_user_post ydotoold.service

%preun
%systemd_user_preun ydotoold.service

%postun
%systemd_user_postun_with_restart ydotoold.service

%files
%license LICENSE
%doc README.md
%{_bindir}/%{name}
%{_bindir}/%{name}d
%{_userunitdir}/ydotoold.service
%{_userunitdir}/%{name}.service
%{_mandir}/man1/%{name}.1*
%{_mandir}/man8/%{name}d.8*

%changelog
* Wed Oct 07 2026 b08x <b08x@users.noreply.github.com> - 1.0.4-1
- Initial RPM packaging for ydotool with ydotoold user service
