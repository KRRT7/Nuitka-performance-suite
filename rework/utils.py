import contextlib
import errno
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterator
import subprocess
import sys
from rich.console import Console


console = Console()


@contextlib.contextmanager
def temporary_file():
    tmp_filename = tempfile.mktemp()
    try:
        yield tmp_filename
    finally:
        try:
            os.unlink(tmp_filename)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise


class Timer:
    def __init__(self) -> None:
        self.start: float = 0
        self.end: float = 0

        self.time_taken: float = 0

    def __enter__(self) -> "Timer":
        self.start = perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        self.end = perf_counter()

        self.time_taken = self.end - self.start

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with self:
                return func(*args, **kwargs)

        return wrapper


def safe_rmtree(path):
    if not Path(path).exists():
        return False
    shutil.rmtree(path)
    return True


MS_WINDOWS = sys.platform == "win32"

NECESSARY_ENV_VARS = {
    "nt": [
        "ALLUSERSPROFILE",
        "APPDATA",
        "COMPUTERNAME",
        "ComSpec",
        "CommonProgramFiles",
        "CommonProgramFiles(x86)",
        "CommonProgramW6432",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "NUMBER_OF_PROCESSORS",
        "OS",
        "PATHEXT",
        "PROCESSOR_ARCHITECTURE",
        "PROCESSOR_IDENTIFIER",
        "PROCESSOR_LEVEL",
        "PROCESSOR_REVISION",
        "Path",
        "ProgramData",
        "ProgramFiles",
        "ProgramFiles(x86)",
        "ProgramW6432",
        "SystemDrive",
        "SystemRoot",
        "TEMP",
        "TMP",
        "USERDNSDOMAIN",
        "USERDOMAIN",
        "USERDOMAIN_ROAMINGPROFILE",
        "USERNAME",
        "USERPROFILE",
        "windir",
    ],
}
NECESSARY_ENV_VARS_DEFAULT = [
    "HOME",
    "PATH",
]


def _get_envvars():
    try:
        necessary = NECESSARY_ENV_VARS[os.name]
    except KeyError:
        necessary = NECESSARY_ENV_VARS_DEFAULT
    copy_env = list(necessary)
    env = {}
    for name in copy_env:
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def run_command_in_subprocess(
    command: list[str],
) -> subprocess.CompletedProcess:
    process = subprocess.Popen(
        command,
        env=_get_envvars(),
        text=True,
    )

    process.wait()

    return subprocess.CompletedProcess(
        args=command,
        returncode=process.returncode,
    )


@contextmanager
def temporary_directory_change(path: Path) -> Iterator[None]:
    if not path.exists():
        raise FileNotFoundError(f"Directory {path} does not exist")
    current_directory = Path.cwd()
    os.chdir(path)
    yield
    os.chdir(current_directory)


def cleanup(parent: Path, to_keep: list[Path]) -> None:
    for path in parent.iterdir():
        if path not in to_keep:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def get_benchmarks(bechmark_dir: Path) -> Iterator[Path]:
    for benchmark_case in bechmark_dir.iterdir():
        if not benchmark_case.is_dir() or not benchmark_case.name.startswith("bm_"):
            continue
        yield benchmark_case
