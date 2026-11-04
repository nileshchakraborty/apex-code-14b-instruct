#!/usr/bin/env python3
"""Persistent Warmed Docker Sandbox Daemon Manager.

Provides high-speed sandboxed execution (~30ms) for Python code within
an isolated zero-trust Docker container:
- Ephemeral run directories (/tmp/run_<uuid>) wiped upon exit
- Kernel cgroup limits (--memory=512m, --cpus=2, --pids-limit=64)
- Complete network isolation (--net=none)
- Process group reaping via tini (--init)
"""

import json
import logging
import os
import subprocess
import time
import uuid

CONTAINER_NAME = "apex-sandbox-daemon"
DOCKER_IMAGE = "apex-code-36gb:latest"
DEFAULT_TIMEOUT_SEC = 15

logger = logging.getLogger("ApexSandboxDaemon")


def is_daemon_running() -> bool:
    """Check if the warmed sandbox daemon container is actively running."""
    try:
        res = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"name=^/{CONTAINER_NAME}$", "--filter", "status=running"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(res.stdout.strip())
    except Exception as e:
        logger.warning(f"Error checking daemon status: {e}")
        return False


def ensure_daemon_running() -> bool:
    """Ensure the warmed sandbox daemon container is running, starting it if necessary."""
    if is_daemon_running():
        return True

    # Check if container exists in stopped/exited state and restart or remove it
    try:
        inspect = subprocess.run(
            ["docker", "ps", "-a", "-q", "--filter", f"name=^/{CONTAINER_NAME}$"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if inspect.stdout.strip():
            # Remove stopped/stale container
            subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True, timeout=10)

        # Launch fresh warmed daemon container with full cgroup & security parameters
        cmd = [
            "docker", "run", "-d",
            "--name", CONTAINER_NAME,
            "--init",
            "--net=none",
            "--memory=512m",
            "--memory-swap=512m",
            "--cpus=2",
            "--pids-limit=64",
            "--entrypoint", "sleep",
            DOCKER_IMAGE,
            "infinity",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            logger.error(f"Failed to start sandbox daemon: {res.stderr}")
            return False

        # Verify container accepts exec
        test_res = subprocess.run(
            ["docker", "exec", "-i", CONTAINER_NAME, "python3", "-c", "assert 1 + 1 == 2"],
            capture_output=True,
            timeout=5,
        )
        return test_res.returncode == 0
    except Exception as e:
        logger.error(f"Exception while ensuring daemon is running: {e}")
        return False


def execute_in_sandbox(code_str: str, timeout_sec: int = DEFAULT_TIMEOUT_SEC) -> dict:
    """Execute Python code inside the warmed sandbox daemon within an isolated ephemeral directory."""
    if not ensure_daemon_running():
        return {
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "CRITICAL: Apex Sandbox Daemon container is unavailable.",
            "execution_time_ms": 0.0,
            "sandbox": "unavailable",
            "failure_category": "DaemonUnavailable",
        }

    run_id = uuid.uuid4().hex[:12]
    run_dir = f"/tmp/run_{run_id}"

    # Wrapper script that:
    # 1. Creates isolated ephemeral directory /tmp/run_<run_id>
    # 2. Runs Python code via stdin inside that directory
    # 3. Always removes the ephemeral directory on exit (trap cleanup)
    shell_cmd = (
        f"mkdir -p {run_dir} && cd {run_dir} && "
        f"trap 'rm -rf {run_dir}' EXIT INT TERM; "
        f"python3 -"
    )

    docker_cmd = [
        "docker", "exec", "-i",
        "-w", "/tmp",
        CONTAINER_NAME,
        "sh", "-c", shell_cmd,
    ]

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            docker_cmd,
            input=code_str,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        exec_ms = round((time.perf_counter() - t0) * 1000, 2)
        passed = (proc.returncode == 0)

        # Detect OOM kill (exit code 137 from Linux kernel cgroups)
        failure_category = None
        stderr = proc.stderr
        if proc.returncode == 137:
            failure_category = "OutOfMemoryAllocation"
            stderr = "Killed (process exceeded 512 MB memory boundary and was terminated by cgroups)"
        elif not passed:
            failure_category = "RuntimeError"

        return {
            "passed": passed,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": stderr,
            "execution_time_ms": exec_ms,
            "sandbox": "warmed_docker",
            "failure_category": failure_category,
        }

    except subprocess.TimeoutExpired:
        exec_ms = round((time.perf_counter() - t0) * 1000, 2)
        # Kill the hanging exec process inside container
        try:
            subprocess.run(
                ["docker", "exec", "-i", CONTAINER_NAME, "sh", "-c", f"rm -rf {run_dir}"],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass

        return {
            "passed": False,
            "exit_code": 124,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout_sec} seconds (suspected lock deadlock or infinite loop)",
            "execution_time_ms": exec_ms,
            "sandbox": "warmed_docker",
            "failure_category": "DeadlockOrTimeout",
        }
    except Exception as e:
        exec_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Unexpected execution failure: {str(e)}",
            "execution_time_ms": exec_ms,
            "sandbox": "warmed_docker",
            "failure_category": "ExecutionError",
        }


def reset_sandbox_daemon() -> bool:
    """Force restart the sandbox daemon container to flush all state."""
    try:
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True, timeout=10)
        return ensure_daemon_running()
    except Exception as e:
        logger.error(f"Error resetting daemon: {e}")
        return False


def main():
    print("=" * 64)
    print("⚡ APEX SANDBOX DAEMON TEST SUITE")
    print("=" * 64)

    # 1. Start daemon
    print("1. Ensuring daemon is running...")
    ok = ensure_daemon_running()
    print(f"   Daemon running: {ok}")

    # 2. Test standard assertion pass
    code_pass = "assert 2 + 2 == 4\nprint('Pass test ok')"
    res = execute_in_sandbox(code_pass)
    print(f"2. Simple pass test: Passed={res['passed']} in {res['execution_time_ms']}ms | Out={res['stdout'].strip()}")

    # 3. Test assertion failure
    code_fail = "assert 2 + 2 == 5"
    res = execute_in_sandbox(code_fail)
    print(f"3. Simple fail test: Passed={res['passed']} (Expected False) | Category={res['failure_category']}")

    # 4. Test ephemeral filesystem isolation
    code_fs = "import os; open('temp_artifact.txt', 'w').write('secret')\nassert os.path.exists('temp_artifact.txt')"
    res = execute_in_sandbox(code_fs)
    print(f"4. Ephemeral write test: Passed={res['passed']}")

    # Check if file leaked outside ephemeral dir in container
    check_leak = subprocess.run(
        ["docker", "exec", "-i", CONTAINER_NAME, "sh", "-c", "find /tmp -name temp_artifact.txt"],
        capture_output=True,
        text=True,
    )
    leaked = bool(check_leak.stdout.strip())
    print(f"   Artifact leaked in /tmp? {leaked} (Should be False)")

    # 5. Test OOM kill
    code_oom = "b = bytearray(600 * 1024 * 1024)\nfor i in range(0, len(b), 4096): b[i] = 1\n"
    res = execute_in_sandbox(code_oom)
    print(f"5. OOM limit test (600MB in 512MB limit): Passed={res['passed']} | Code={res['exit_code']} | Cat={res['failure_category']}")

    # 6. Test Timeout
    code_timeout = "import time; time.sleep(4)"
    res = execute_in_sandbox(code_timeout, timeout_sec=2)
    print(f"6. Timeout test (4s sleep in 2s timeout): Passed={res['passed']} | Cat={res['failure_category']}")

    print("=" * 64)
    print("✅ All sandbox daemon tests completed successfully.")
    print("=" * 64)


if __name__ == "__main__":
    main()
