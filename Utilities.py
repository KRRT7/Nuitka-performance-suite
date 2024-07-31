from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
import os
from typing import Any, Iterator, Callable, Literal, Generator, Iterable
from pathlib import Path
import sys
from subprocess import run, Popen, PIPE
from statistics import mean
from json import load, dump
from dataclasses import dataclass
from rich import print
from rich.align import Align
from rich.text import Text
from rich.progress import track
import platform

# NUITKA_VERSIONS = ["nuitka", '"https://github.com/Nuitka/Nuitka/archive/factory.zip"'] # Currently factory is equivalent to release
NUITKA_VERSIONS = ["nuitka"]

BENCHMARK_DIRECTORY = Path(__file__).parent / "benchmarks"
TEST_BENCHMARK_DIRECTORY = Path(__file__).parent / "benchmarks_test"


def centered_text(text: str) -> Align:
    return Align.center(Text(text))


@dataclass
class Stats:
    name: str
    warmup: list[float]
    benchmark: list[float]

    @classmethod
    def from_dict(cls, stats_dict: dict[str, list[float]], name: str) -> "Stats":
        return cls(
            name,
            stats_dict["warmup"],
            stats_dict["benchmark"],
        )


@dataclass
class Benchmark:
    python_version: tuple[int, int]
    benchmark_name: str
    target: str | None = None
    nuitka_version: str | None = None
    file_json: dict[str, dict[str, list[float]]] | None = None
    nuitka_stats: Stats | None = None
    cpython_stats: Stats | None = None
    factory: Benchmark | None = None

    @staticmethod
    def parse_file_name(file_name: str) -> tuple[str, str, tuple[int, int]]:
        target, nuitka_version, python_version = file_name.split("-")
        py_ver_split = python_version.split(".")
        python_version_tuple = (int(py_ver_split[0]), int(py_ver_split[1]))
        return target, nuitka_version, python_version_tuple

    def parse_stats(self, stats: dict[str, dict[str, list[float]]]) -> None:
        self.nuitka_stats = Stats.from_dict(stats["nuitka"], "nuitka")
        self.cpython_stats = Stats.from_dict(stats["cpython"], "cpython")

    @property
    def py_version(self) -> str:
        major, _min = self.python_version
        return "{}.{}".format(major, _min)

    @classmethod
    def from_path(cls, file_path: Path, benchmark_name: str) -> "Benchmark":

        if not file_path.stat().st_size > 0:
            raise FileNotFoundError(f"File {file_path} does not exist or is empty")

        with open(file_path, "r") as f:
            file_json = load(f)

        file_info = cls.parse_file_name(file_path.stem)
        return cls(
            target=file_info[0],
            nuitka_version=file_info[1],
            python_version=file_info[2],
            file_json=file_json,
            nuitka_stats=Stats.from_dict(file_json["nuitka"], "nuitka"),
            cpython_stats=Stats.from_dict(file_json["cpython"], "cpython"),
            benchmark_name=benchmark_name.removeprefix("bm_"),
        )

    @classmethod
    def from_dict(
        cls, file_dict: dict[str, dict[str, list[float]]], benchmark_name: str
    ) -> "Benchmark":
        file_info = cls.parse_file_name(benchmark_name)
        return cls(
            target=file_info[0],
            nuitka_version=file_info[1],
            python_version=file_info[2],
            file_json=file_dict,
            nuitka_stats=Stats(
                "nuitka",
                file_dict["nuitka"]["warmup"],
                file_dict["nuitka"]["benchmark"],
            ),
            cpython_stats=Stats(
                "cpython",
                file_dict["cpython"]["warmup"],
                file_dict["cpython"]["benchmark"],
            ),
            benchmark_name=benchmark_name.removeprefix("bm_"),
        )

    def to_json_file(self, file_path: Path) -> None:

        if not self.nuitka_stats or not self.cpython_stats:
            raise ValueError("Stats not found")

        contents = {
            "nuitka": {
                "warmup": self.nuitka_stats.warmup,
                "benchmark": self.nuitka_stats.benchmark,
            },
            "cpython": {
                "warmup": self.cpython_stats.warmup,
                "benchmark": self.cpython_stats.benchmark,
            },
        }
        with open(file_path, "w") as f:
            dump(contents, f)

    def calculate_stats(self, which: Literal["nuitka", "cpython"]) -> float:
        if which.lower() not in ["nuitka", "cpython"]:
            raise ValueError("Invalid value for 'which' parameter")

        if not self.nuitka_stats or not self.cpython_stats:
            raise ValueError("Stats not found")

        stats = self.nuitka_stats if which.lower() == "nuitka" else self.cpython_stats

        is_warmup_skewed: bool = min(stats.warmup) == stats.warmup[0]
        is_benchmark_skewed: bool = min(stats.benchmark) == stats.benchmark[0]

        warmup = mean(stats.warmup[is_warmup_skewed:])
        benchmark = mean(stats.benchmark[is_benchmark_skewed:])

        return min(warmup, benchmark)

    def format_stats(self) -> Align:
        nuitka_stats = self.calculate_stats("nuitka")
        cpython_stats = self.calculate_stats("cpython")

        if nuitka_stats < cpython_stats:
            difference = (cpython_stats - nuitka_stats) / cpython_stats * 100
            return Align.center(Text(f"+{difference:.2f}%", style="green"))
        elif nuitka_stats > cpython_stats:
            difference = (nuitka_stats - cpython_stats) / cpython_stats * 100
            return Align.center(Text(f"-{difference:.2f}%", style="red"))
        else:
            difference = (nuitka_stats - cpython_stats) / cpython_stats * 100
            return Align.center(Text(f"{difference:.2f}%", style="yellow"))

    def __repr__(self) -> str:
        return f"{self.benchmark_name} reprd"


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
    if platform.system() == "Windows":
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
    else:
        raise NotImplementedError("Only Windows is supported")


def is_in_venv() -> bool:
    # https://stackoverflow.com/a/1883251
    return sys.prefix != sys.base_prefix


def _get_benchmarks(test: bool = False) -> Iterator[Path]:
    bench_dir = TEST_BENCHMARK_DIRECTORY if test else BENCHMARK_DIRECTORY
    for benchmark_case in bench_dir.iterdir():
        if not benchmark_case.is_dir() or not benchmark_case.name.startswith("bm_"):
            continue
        yield benchmark_case


def get_visualizer_setup(
    test: bool = False,
    # ) -> Generator[tuple[str, str, list[Benchmark], list[Benchmark]], None, None]:
    # ) -> Generator[tuple[str, str, list[Benchmark]]]:
) -> Generator[tuple[str, str, list[Benchmark]], None, None]:
    for benchmark in _get_benchmarks(test=test):
        results_dir = benchmark / "results"
        if not results_dir.exists():
            print(
                f"Skipping benchmark {benchmark.name}, because {results_dir} does not exist"
            )
            continue

        for dates in results_dir.iterdir():
            date = dates.name
            date_benchmarks = []
            for result_file in dates.iterdir():
                if not result_file.suffix == ".json" or "factory" in result_file.name:
                    continue
                try:
                    bench = Benchmark.from_path(result_file, benchmark.name)
                    date_benchmarks.append(bench)
                    factory = result_file.parent / result_file.name.replace(
                        "stable", "factory"
                    )
                    if factory.exists():
                        bench.factory = Benchmark.from_path(factory, benchmark.name)
                    else:
                        print(f"Factory file {factory} does not exist vs {result_file}")
                except FileNotFoundError:
                    continue
            yield benchmark.name, date, sorted(date_benchmarks, key=lambda x: x.python_version[1])


def get_benchmark_setup() -> list[Path]:
    return list(_get_benchmarks())


def setup_benchmark_enviroment(
    nuitka_version: str,
    requirements_exists: bool,
    python_executable: str,
    silent: bool = False,
) -> None:
    try:
        commands = [
            f"{python_executable} --version",
            f"{python_executable} -m pip install --upgrade pip setuptools wheel",
            f"{python_executable} -m pip install {nuitka_version}",
            f"{python_executable} -m pip install ordered-set",
            f"{python_executable} -m pip install appdirs",
            # f"{python_executable} -m nuitka --standalone --remove-output run_benchmark.py",
            f"{python_executable} -m nuitka --remove-output --lto=yes run_benchmark.py",
        ]
        if requirements_exists:
            commands.insert(
                2, f"{python_executable} -m pip install -r requirements.txt"
            )
        for command in commands:
            if silent:
                res = run(command, stdout=PIPE, stderr=PIPE)
            else:
                res = run(command)
            if res.returncode != 0:
                print(f"Failed to run command {command}")
                break
    except Exception as e:
        raise RuntimeError(f"Failed to setup benchmark enviroment\n{e}")
