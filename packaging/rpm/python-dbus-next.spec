%global pypi_name dbus-next
%global srcname   dbus_next

Name:           python-%{pypi_name}
Version:        0.2.3
Release:        1%{?dist}
Summary:        Zero-dependency DBus library for Python with asyncio support

License:        MIT
URL:            https://github.com/altdesktop/python-dbus-next
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros

%global _description %{expand:
python-dbus-next is a Python library for DBus that aims to be a fully
featured high-level library primarily geared towards integration of
applications into Linux desktop and mobile environments. It supports
asyncio, GLib, and non-blocking IO.}

%description %{_description}

%package -n     python3-%{pypi_name}
Summary:        %{summary}

%description -n python3-%{pypi_name} %{_description}

%prep
%autosetup -p1 -n %{name}-%{version}
# Remove execute bit from examples if present
find examples/ -type f -exec chmod -x {} + 2>/dev/null || :

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l %{srcname}

%check
%pyproject_check_import

%files -n python3-%{pypi_name} -f %{pyproject_files}
%license LICENSE
%doc README.md CHANGELOG.md

%changelog
* Wed Oct 07 2026 b08x <b08x@users.noreply.github.com> - 0.2.3-1
- Initial RPM packaging for python-dbus-next
