from contextlib import contextmanager
from time import perf_counter
import os
from typing import Any, Iterator, Callable
from typing_extensions import Never
from pathlib import Path
import sys
from subprocess import run, Popen, PIPE
from statistics import mean

from rich import print
from rich.progress import track

# NUITKA_VERSIONS = ["nuitka", '"https://github.com/Nuitka/Nuitka/archive/factory.zip"'] # Currently factory is equivalent to release
NUITKA_VERSIONS = ["nuitka"]


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


@contextmanager
def temporary_directory_change(path: Path) -> Iterator[None]:
    if not path.exists():
        raise FileNotFoundError(f"Directory {path} does not exist")
    current_directory = Path.cwd()
    os.chdir(path)
    yield
    os.chdir(current_directory)


def resolve_venv_path() -> Path:
    resolved_path = Path(sys.executable).resolve()
    if is_in_venv():
        return resolved_path
    else:
        venv_create = run(f"{resolved_path} -m venv venv", stdout=PIPE, stderr=PIPE)
        if venv_create.returncode != 0:
            raise RuntimeError("Failed to create venv")

        new_venv_path = Path("venv")
        if new_venv_path.exists():
            return (new_venv_path / "Scripts" / "python.exe").resolve()
        else:
            raise FileNotFoundError("Failed to create venv")


def create_venv_with_version(version: str) -> Path:
    venv_create = run(f"py -{version} -m venv {version}_venv")
    if venv_create.returncode != 0:
        raise RuntimeError("Failed to create venv")

    new_venv_path = Path(f"{version}_venv")
    if new_venv_path.exists():
        return (new_venv_path / "Scripts" / "python.exe").resolve()
    else:
        raise FileNotFoundError("Failed to create venv")


def run_benchmark(
    benchmark: Path,
    python_executable: Path,
    iterations: int,
    cpython_version: str,
    type: str,
    nuitka_name: str,
) -> dict[str, list[float]]:
    local_results: dict[str, list[float]] = {
        "warmup": [],
        "benchmark": [],
    }
    run_command = {
        "Nuitka": Path(os.getcwd()) / "run_benchmark.dist/run_benchmark.exe",
        "CPython": [python_executable, "run_benchmark.py"],
    }
    description_dict = {
        "Nuitka": f"{benchmark.name} with {type} | Nuitka Version: {nuitka_name} ({cpython_version})",
        "CPython": f"{benchmark.name} with {type} | Python Version: {cpython_version}",
    }

    for _ in track(
        range(iterations),
        description=f"warming up {description_dict[type]}",
        total=iterations,
    ):
        with Timer() as timer:
            res = run(run_command[type])  # type: ignore
            if res.returncode != 0:
                raise RuntimeError(
                    f"Failed to run benchmark {benchmark.name} due to {res.stderr}"
                )

        local_results["warmup"].append(timer.time_taken)

    for _ in track(
        range(iterations),
        description=f"benchmarking {description_dict[type]}",
        total=iterations,
    ):
        with Timer() as timer:
            res = run(run_command[type])  # type: ignore
            if res.returncode != 0:
                raise RuntimeError(f"Failed to run benchmark {benchmark.name}")

        local_results["benchmark"].append(timer.time_taken)

    print(f"Completed benchmarking {benchmark.name} with {type}")

    return local_results


def parse_py_launcher() -> list[str]:
    BLACKLIST = ["3.13", "3.13t", "3.6"]
    res = Popen(["py", "-0"], shell=True, stdout=PIPE, stderr=PIPE)
    if res.returncode != 0 and res.stdout:
        resp = [line.decode("utf-8").strip().split("Python") for line in res.stdout]

    if "Active venv" in resp[0][0]:
        resp.pop(0)

    versions = [
        version[0].strip().replace("-V:", "").replace(" *", "") for version in resp
    ]
    versions = [version for version in versions if version not in BLACKLIST]
    return versions


def is_in_venv() -> bool:
    # https://stackoverflow.com/a/1883251
    return sys.prefix != sys.base_prefix
