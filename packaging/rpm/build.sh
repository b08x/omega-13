#!/usr/bin/env bash
#
# build.sh - RPM Packaging Automation for Omega-13 and Dependencies
#
# Manages source tarball creation, RPM workspace staging, rpmlint validation,
# SRPM generation, and binary package compilation for Fedora 40+ and EPEL 9/10.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RPMBUILD_DIR="${RPMBUILD_DIR:-${REPO_ROOT}/build/rpmbuild}"

# UI colors
if [[ -t 1 ]]; then
    COLOR_BLUE="\033[1;34m"
    COLOR_GREEN="\033[1;32m"
    COLOR_RED="\033[1;31m"
    COLOR_YELLOW="\033[1;33m"
    COLOR_RESET="\033[0m"
else
    COLOR_BLUE=""
    COLOR_GREEN=""
    COLOR_RED=""
    COLOR_YELLOW=""
    COLOR_RESET=""
fi

log_info()    { echo -e "${COLOR_BLUE}▸${COLOR_RESET} $*"; }
log_success() { echo -e "${COLOR_GREEN}✓${COLOR_RESET} $*"; }
log_warn()    { echo -e "${COLOR_YELLOW}⚠${COLOR_RESET} $*"; }
log_error()   { echo -e "${COLOR_RED}✗${COLOR_RESET} $*" >&2; }

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [PACKAGE...]

RPM packaging automation tool for Omega-13 and its dependencies.

Commands / Options:
  --prep          Initialize RPM workspace, create omega13 tarball, and stage sources
  --lint          Validate all spec files with rpmlint
  --srpm          Build Source RPM (.src.rpm) packages
  --rpm           Build binary RPM (.rpm) packages
  --all           Execute prep, lint, and srpm generation
  --clean         Clean the RPM build directory (${RPMBUILD_DIR})
  -h, --help      Display this help message

Optional [PACKAGE] filter (applies to --srpm and --rpm):
  omega13
  python-transcribe-cpp
  python-JACK-Client
  python-dbus-next
  ydotool
  (If omitted, operations run on all packages)

Environment Variables:
  RPMBUILD_DIR    Directory for RPM build tree (default: ${REPO_ROOT}/build/rpmbuild)

EOF
}

check_tool() {
    local tool="$1"
    if ! command -v "$tool" >/dev/null 2>&1; then
        log_error "Required tool '$tool' is not installed or not in PATH."
        exit 1
    fi
}

init_dirs() {
    log_info "Initializing RPM build tree at ${RPMBUILD_DIR}..."
    mkdir -p "${RPMBUILD_DIR}"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
}

get_omega13_version() {
    local spec="${SCRIPT_DIR}/omega13.spec"
    if [[ -f "$spec" ]]; then
        rpm --specfile "$spec" --qf "%{version}\n" 2>/dev/null | head -n 1
    else
        echo "2.7.5"
    fi
}

prep_sources() {
    check_tool "rpmbuild"
    init_dirs

    local version
    version="$(get_omega13_version)"
    local tarball="omega13-${version}.tar.gz"

    log_info "Staging spec files and system integration assets..."
    cp -f "${SCRIPT_DIR}"/*.spec "${RPMBUILD_DIR}/SPECS/"

    # Stage system integration assets
    if [[ -f "${SCRIPT_DIR}/omega13.service" ]]; then
        cp -f "${SCRIPT_DIR}/omega13.service" "${RPMBUILD_DIR}/SOURCES/"
    fi
    if [[ -f "${SCRIPT_DIR}/org.omega13.Recorder.service" ]]; then
        cp -f "${SCRIPT_DIR}/org.omega13.Recorder.service" "${RPMBUILD_DIR}/SOURCES/"
    fi
    if [[ -f "${SCRIPT_DIR}/ydotoold.service" ]]; then
        cp -f "${SCRIPT_DIR}/ydotoold.service" "${RPMBUILD_DIR}/SOURCES/"
    fi

    log_info "Creating Omega-13 source tarball: ${tarball}..."
    tar --exclude-vcs \
        --exclude='.venv' \
        --exclude='build' \
        --exclude='dist' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --transform="s,^\.,omega13-${version}," \
        -czf "${RPMBUILD_DIR}/SOURCES/${tarball}" \
        -C "${REPO_ROOT}" .

    log_success "Created ${tarball} in ${RPMBUILD_DIR}/SOURCES/"

    # Fetch dependency source archives if spectool is present
    if command -v spectool >/dev/null 2>&1; then
        log_info "Fetching missing dependency source archives via spectool..."
        for spec in "${RPMBUILD_DIR}/SPECS"/*.spec; do
            spectool -g -C "${RPMBUILD_DIR}/SOURCES" "$spec" >/dev/null 2>&1 || true
        done
        log_success "Dependency source archives ready."
    else
        log_warn "spectool not found; skipping automatic download of upstream dependency sources."
    fi

    log_success "RPM build staging complete."
}

run_lint() {
    check_tool "rpmlint"
    log_info "Running rpmlint on all packaging spec files..."
    local specs=("${SCRIPT_DIR}"/*.spec)
    if [[ ${#specs[@]} -eq 0 ]]; then
        log_error "No .spec files found in ${SCRIPT_DIR}"
        exit 1
    fi

    rpmlint "${specs[@]}"
    log_success "All spec files passed rpmlint validation with zero fatal errors."
}

get_target_specs() {
    local filter="${1:-}"
    local target_specs=()

    if [[ -z "$filter" ]]; then
        target_specs=("${RPMBUILD_DIR}/SPECS"/*.spec)
    else
        for pkg in "$@"; do
            case "$pkg" in
                omega13*)
                    target_specs+=("${RPMBUILD_DIR}/SPECS/omega13.spec")
                    ;;
                *transcribe*)
                    target_specs+=("${RPMBUILD_DIR}/SPECS/python-transcribe-cpp.spec")
                    ;;
                *JACK*|*jack*)
                    target_specs+=("${RPMBUILD_DIR}/SPECS/python-JACK-Client.spec")
                    ;;
                *dbus*)
                    target_specs+=("${RPMBUILD_DIR}/SPECS/python-dbus-next.spec")
                    ;;
                *ydotool*)
                    target_specs+=("${RPMBUILD_DIR}/SPECS/ydotool.spec")
                    ;;
                *)
                    if [[ -f "${RPMBUILD_DIR}/SPECS/${pkg}" ]]; then
                        target_specs+=("${RPMBUILD_DIR}/SPECS/${pkg}")
                    elif [[ -f "${RPMBUILD_DIR}/SPECS/${pkg}.spec" ]]; then
                        target_specs+=("${RPMBUILD_DIR}/SPECS/${pkg}.spec")
                    else
                        log_error "Unknown package spec: $pkg"
                        exit 1
                    fi
                    ;;
            esac
        done
    fi

    echo "${target_specs[@]}"
}

build_srpm() {
    check_tool "rpmbuild"
    prep_sources

    local extra_args=()
    local pkg_args=()
    for arg in "$@"; do
        if [[ "$arg" =~ ^- ]]; then
            extra_args+=("$arg")
        else
            pkg_args+=("$arg")
        fi
    done

    local specs
    read -r -a specs <<< "$(get_target_specs "${pkg_args[@]}")"

    log_info "Building Source RPMs (SRPMs)..."
    for spec in "${specs[@]}"; do
        if [[ -f "$spec" ]]; then
            log_info "Building SRPM for $(basename "$spec")..."
            rpmbuild -bs --define "_topdir ${RPMBUILD_DIR}" ${extra_args[@]+"${extra_args[@]}"} "$spec"
        fi
    done
    log_success "SRPM build completed. Artifacts in ${RPMBUILD_DIR}/SRPMS/"
}

build_rpm() {
    check_tool "rpmbuild"
    prep_sources

    local extra_args=()
    local pkg_args=()
    for arg in "$@"; do
        if [[ "$arg" =~ ^- ]]; then
            extra_args+=("$arg")
        else
            pkg_args+=("$arg")
        fi
    done

    local specs
    read -r -a specs <<< "$(get_target_specs "${pkg_args[@]}")"

    log_info "Building binary RPM packages..."
    for spec in "${specs[@]}"; do
        if [[ -f "$spec" ]]; then
            log_info "Compiling binary RPM for $(basename "$spec")..."
            rpmbuild -bb --define "_topdir ${RPMBUILD_DIR}" ${extra_args[@]+"${extra_args[@]}"} "$spec"
        fi
    done
    log_success "Binary RPM build completed. Artifacts in ${RPMBUILD_DIR}/RPMS/"
}

clean_build() {
    log_info "Cleaning RPM build directory ${RPMBUILD_DIR}..."
    rm -rf "${RPMBUILD_DIR}"
    log_success "Cleaned ${RPMBUILD_DIR}."
}

# Main option router
if [[ $# -eq 0 ]]; then
    show_help
    exit 0
fi

ACTION="$1"
shift || true

case "$ACTION" in
    --prep)
        prep_sources
        ;;
    --lint)
        run_lint
        ;;
    --srpm)
        build_srpm "$@"
        ;;
    --rpm)
        build_rpm "$@"
        ;;
    --all)
        prep_sources
        run_lint
        build_srpm "$@"
        ;;
    --clean)
        clean_build
        ;;
    -h|--help)
        show_help
        ;;
    *)
        log_error "Unknown argument: $ACTION"
        show_help
        exit 1
        ;;
esac
