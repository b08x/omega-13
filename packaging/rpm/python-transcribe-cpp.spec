%global pypi_name transcribe-cpp
%global srcname   transcribe_cpp

%bcond_with cuda
%bcond_with vulkan

Name:           python-%{pypi_name}
Version:        0.3.1
Release:        1%{?dist}
Summary:        Python bindings for transcribe.cpp speech recognition library

License:        MIT
URL:            https://github.com/handy-computer/transcribe.cpp
Source0:        %{url}/archive/v%{version}/transcribe.cpp-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-pip
BuildRequires:  python3-wheel
BuildRequires:  python3-setuptools

%if %{with cuda}
BuildRequires:  cuda-toolkit
%endif

%if %{with vulkan}
BuildRequires:  vulkan-headers
BuildRequires:  vulkan-loader-devel
%endif

%global _description %{expand:
Python bindings for transcribe.cpp, providing high-performance local speech
recognition and voice activity detection using GGML models. Supports optional
hardware acceleration via CUDA and Vulkan backends.}

%description %{_description}

%package -n     python3-%{pypi_name}
Summary:        %{summary}

%description -n python3-%{pypi_name} %{_description}

%prep
%autosetup -n transcribe.cpp-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
CMAKE_ARGS="-DTRANSCRIBE_BUILD_SHARED=ON"
%if %{with cuda}
CMAKE_ARGS="${CMAKE_ARGS} -DTRANSCRIBE_CUDA=ON"
%endif
%if %{with vulkan}
CMAKE_ARGS="${CMAKE_ARGS} -DTRANSCRIBE_VULKAN=ON"
%endif
export CMAKE_ARGS

%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l %{srcname}

%check
%pyproject_check_import

%files -n python3-%{pypi_name} -f %{pyproject_files}
%license LICENSE
%doc README.md

%changelog
* Wed Oct 07 2026 b08x <b08x@users.noreply.github.com> - 0.3.1-1
- Initial RPM packaging for transcribe-cpp
- Add bcond flags for optional CUDA and Vulkan hardware acceleration
