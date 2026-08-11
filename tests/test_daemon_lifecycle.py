"""
Integration test for Omega-13 daemon lifecycle.

Verifies:
1. Daemon starts and writes a PID file.
2. A second launch fails due to PID file conflict.
3. Daemon shuts down cleanly on SIGTERM.
4. PID file is removed after shutdown.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VENV_PYTHON = "/home/b08x/WorkspaceV3/omega-13/.venv/bin/python"
PROJECT_SRC = "/home/b08x/WorkspaceV3/omega-13/src"
PID_FILE = Path("/tmp/omega13_test.pid")

HELPER_SCRIPT = '''
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, "{project_src}")

from omega13.pidfile import PidFile, PidFileError

pid_file = Path("{pid_file}")

try:
    pf = PidFile(pid_file)
    pid = pf.acquire()
    print(f"ACQUIRED PID {{pid}}", flush=True)
except PidFileError as e:
    print(f"FAILED: {{e}}", file=sys.stderr, flush=True)
    sys.exit(1)

def handle_term(signum, frame):
    pf.release()
    print("RELEASED", flush=True)
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_term)
signal.signal(signal.SIGINT, handle_term)

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
'''.format(project_src=PROJECT_SRC, pid_file=str(PID_FILE))


def run_helper(env=None):
    """Start the helper daemon script and return the Popen object."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(HELPER_SCRIPT)
        helper_path = f.name

    run_env = os.environ.copy()
    run_env["PYTHONPATH"] = PROJECT_SRC
    if env:
        run_env.update(env)

    proc = subprocess.Popen(
        [VENV_PYTHON, helper_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=run_env,
    )
    return proc, helper_path


def wait_for_pid_file(timeout=5.0):
    """Wait for PID_FILE to appear and contain a valid PID."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                return pid
            except ValueError:
                pass
        time.sleep(0.1)
    raise TimeoutError(f"PID file {PID_FILE} did not appear within {timeout}s")


def cleanup():
    """Remove PID file and kill any leftover helper process."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
        except Exception:
            pass
        try:
            PID_FILE.unlink()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clean_pid_file():
    cleanup()
    yield
    cleanup()


class TestDaemonLifecycle:
    """Integration tests for daemon PID file and signal lifecycle."""

    def test_daemon_starts_and_writes_pid_file(self):
        """(1) Daemon starts and writes a PID file."""
        proc, helper_path = run_helper()
        try:
            pid = wait_for_pid_file(timeout=5.0)
            assert pid == proc.pid, (
                f"PID file PID ({pid}) should match process PID ({proc.pid})"
            )
        finally:
            proc.terminate()
            try:
                os.unlink(helper_path)
            except OSError:
                pass

    def test_second_launch_fails_due_to_pid_conflict(self):
        """(2) Second launch fails due to PID file conflict."""
        # Start first daemon
        proc1, helper1 = run_helper()
        try:
            pid1 = wait_for_pid_file(timeout=5.0)
            assert pid1 == proc1.pid

            # Start second daemon (should fail immediately)
            proc2, helper2 = run_helper()
            try:
                stdout, stderr = proc2.communicate(timeout=5.0)
                assert proc2.returncode == 1, (
                    f"Second daemon should exit with code 1, got {proc2.returncode}"
                )
                assert b"FAILED" in stdout or b"FAILED" in stderr, (
                    f"Expected failure output, got stdout={stdout!r}, stderr={stderr!r}"
                )
            finally:
                try:
                    os.unlink(helper2)
                except OSError:
                    pass
        finally:
            proc1.terminate()
            try:
                os.unlink(helper1)
            except OSError:
                pass

    def test_daemon_shuts_down_cleanly_on_sigterm(self):
        """(3) Daemon shuts down cleanly on SIGTERM."""
        proc, helper_path = run_helper()
        try:
            pid = wait_for_pid_file(timeout=5.0)
            # Send SIGTERM
            proc.send_signal(signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=5.0)
            assert proc.returncode == 0, (
                f"Daemon should exit 0 on SIGTERM, got {proc.returncode}"
            )
            assert b"RELEASED" in stdout, f"Expected RELEASED output, got stdout={stdout!r}"
        finally:
            try:
                os.unlink(helper_path)
            except OSError:
                pass

    def test_pid_file_removed_after_shutdown(self):
        """(4) PID file is removed after shutdown."""
        proc, helper_path = run_helper()
        try:
            pid = wait_for_pid_file(timeout=5.0)
            # Send SIGTERM and wait
            proc.send_signal(signal.SIGTERM)
            proc.communicate(timeout=5.0)
            assert not PID_FILE.exists(), (
                f"PID file {PID_FILE} should be removed after SIGTERM shutdown"
            )
        finally:
            try:
                os.unlink(helper_path)
            except OSError:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
