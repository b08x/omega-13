%global pypi_name JACK-Client
%global srcname   jack_client

Name:           python-%{pypi_name}
Version:        0.5.7
Release:        1%{?dist}
Summary:        JACK Audio Connection Kit (JACK) Client for Python

License:        MIT
URL:            https://jackclient-python.readthedocs.io/
Source0:        %{pypi_source %{srcname}}

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-cffi
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
%if 0%{?fedora} >= 39
BuildRequires:  pipewire-jack-audio-connection-kit-devel
%else
BuildRequires:  jack-audio-connection-kit-devel
%endif

%global _description %{expand:
Python module that provides bindings for the JACK audio connection kit library.
The module is able to create audio input and output ports, and also provides
functionality to manage MIDI ports.}

%description %{_description}

%package -n     python3-%{pypi_name}
Summary:        %{summary}
Requires:       python3-cffi
Suggests:       python3-numpy
Provides:       python3-jack-client = %{version}-%{release}
Provides:       python-jack-client = %{version}-%{release}

%description -n python3-%{pypi_name} %{_description}

%prep
%autosetup -n %{srcname}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l jack _jack

%check
%pyproject_check_import

%files -n python3-%{pypi_name} -f %{pyproject_files}
%license LICENSE
%doc README.rst NEWS.rst

%changelog
* Wed Oct 07 2026 b08x <b08x@users.noreply.github.com> - 0.5.7-1
- Initial RPM packaging for python-JACK-Client
