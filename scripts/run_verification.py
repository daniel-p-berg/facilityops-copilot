import importlib.metadata
import shlex
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMPORT_TIMEOUT_SECONDS = 30
TEST_TIMEOUT_SECONDS = 300
PACKAGE_NAMES = (
    "fastapi",
    "starlette",
    "pydantic",
    "uvicorn",
    "anyio",
)


def print_environment():
    print(f"python={sys.version.split()[0]}")
    print("unittest=standard-library")
    for package_name in PACKAGE_NAMES:
        try:
            version = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            version = "not-installed"
        print(f"{package_name}={version}")


def run_bounded(label, command, timeout_seconds):
    print(
        f"{label}: {shlex.join(command)} "
        f"(timeout={timeout_seconds}s)",
        flush=True,
    )
    started_at = time.monotonic()

    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        elapsed_seconds = time.monotonic() - started_at
        print(
            f"{label}: timed out after {elapsed_seconds:.3f}s",
            file=sys.stderr,
        )
        return 124

    elapsed_seconds = time.monotonic() - started_at
    print(
        f"{label}: exit={completed.returncode} "
        f"elapsed={elapsed_seconds:.3f}s",
        flush=True,
    )
    return completed.returncode


def main():
    print_environment()

    import_result = run_bounded(
        "application import",
        [sys.executable, "-c", "import backend.main"],
        IMPORT_TIMEOUT_SECONDS,
    )
    if import_result != 0:
        return import_result

    return run_bounded(
        "complete unittest suite",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        TEST_TIMEOUT_SECONDS,
    )


if __name__ == "__main__":
    raise SystemExit(main())
