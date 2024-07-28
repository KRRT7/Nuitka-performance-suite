from __future__ import annotations

import os
import platform
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from json import dump, load
from pathlib import Path
from statistics import mean
from subprocess import run
from time import perf_counter
if sys.version_info[:2] >= (3, 8):
    from typing import Any, Callable, Generator, Iterator, Literal
else:
    from typing import Any, Callable, Generator, Iterator
    from typing_extensions import Literal

from rich import print
from rich.align import Align
from rich.progress import track
from rich.text import Text

EMOJIS = {
    "Linux": "🐧",
    "Windows": "🪟",
    "macos": "🍎",
}

CURRENT_PLATFORM = platform.system()
PLATFORM_EMOJI = EMOJIS[CURRENT_PLATFORM]
PYTHON_VERSION: tuple[int, int] = sys.version_info[:2]
NORMALIZED_PYTHON_VERSION = f"{PYTHON_VERSION[0]}.{PYTHON_VERSION[1]}"
BENCHMARK_DIRECTORY = Path(__file__).parent / "benchmarks"
TEST_BENCHMARK_DIRECTORY = Path(__file__).parent / "benchmarks_test"


EXCLUSIONS: dict[str, dict[tuple[int, int], list[str]]] = {
    "Linux": {(3, 9): ["bm_django_template"]},
    "Windows": {(3, 9): ["bm_django_template"], (3, 7): ["bm_django_template"]},
}


def check_if_excluded(benchmark: Path) -> bool:
    name = benchmark.name
    cases = EXCLUSIONS.get(CURRENT_PLATFORM)
    if cases:
        for key, value in cases.items():
            if PYTHON_VERSION <= key and name in value:
                return True
    return False


def centered_text(text: str) -> Align:
    return Align.center(Text(text))


@dataclass
class Stats:
    name: str
    warmup: list[float]
    benchmark: list[float]

    @classmethod
    def from_dict(cls, stats_dict: dict[str, list[float]], name: str) -> Stats:
        return cls(
            name,
            stats_dict["warmup"],
            stats_dict["benchmark"],
        )


@dataclass
class Benchmark:
    name: str
    nuitka_version: str | None = None
    file_json: dict[str, dict[str, list[float]]] | None = None
    nuitka_stats: Stats | None = None
    cpython_stats: Stats | None = None
    factory: Benchmark | None = None
    python_version: tuple[int, int] | None = None

    def parse_stats(self, stats: dict[str, dict[str, list[float]]]) -> None:
        self.nuitka_stats = Stats.from_dict(stats["nuitka"], "nuitka")
        self.cpython_stats = Stats.from_dict(stats["cpython"], "cpython")

    @staticmethod
    def parse_file_name(file_name: str) -> tuple[str, str, tuple[int, int]]:
        platform, version, nuitka_version = file_name.split("-")
        _pyver_split = version.split(".")
        return platform, version, (int(_pyver_split[0]), int(_pyver_split[1]))

    @property
    def normalized_python_version(self) -> str:
        if not self.python_version:
            msg = "Python version not found"
            raise ValueError(msg)
        return f"{self.python_version[0]}.{self.python_version[1]}"

    @classmethod
    def from_path(cls, file_path: Path, benchmark_name: str) -> Benchmark:

        if not file_path.stat().st_size > 0:
            msg = f"File {file_path} does not exist or is empty"
            raise FileNotFoundError(msg)

        with open(file_path) as f:
            file_json = load(f)

        file_info = cls.parse_file_name(file_path.stem)

        benchmark = cls(
            name=benchmark_name,
            nuitka_version=file_info[1],
            python_version=file_info[2],
        )
        benchmark.parse_stats(file_json)

        return benchmark

    def to_json_file(self, file_path: Path) -> None:

        if not self.nuitka_stats or not self.cpython_stats:
            msg = "Stats not found"
            raise ValueError(msg)

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
            msg = "Invalid value for 'which' parameter"
            raise ValueError(msg)

        if not self.nuitka_stats or not self.cpython_stats:
            msg = "Stats not found"
            raise ValueError(msg)

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


class Timer:
    def __init__(self) -> None:
        self.start: float = 0
        self.end: float = 0

        self.time_taken: float = 0

    def __enter__(self) -> Timer:
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
        msg = f"Directory {path} does not exist"
        raise FileNotFoundError(msg)
    current_directory = Path.cwd()
    os.chdir(path)
    yield
    os.chdir(current_directory)


def run_benchmark(
    benchmark: Path,
    python_executable: Path,
    iterations: int,
    type: str,
    nuitka_version: str,
    count: int,
    number_of_benchmarks: int,
    compilation_type: Literal["onefile", "standalone", "accelerated"] = "accelerated",
) -> dict[str, list[float]]:
    local_results: dict[str, list[float]] = {
        "warmup": [],
        "benchmark": [],
    }

    comp_types = {
        "accelerated": {
            "Linux": "run_benchmark.dist/run_benchmark.bin",
            "Windows": "run_benchmark.dist\\run_benchmark.cmd",
        },
        "standalone": {
            "Linux": "run_benchmark.dist/run_benchmark",
            "Windows": "run_benchmark.dist\\run_benchmark.cmd",
        },
        "onefile": {
            "Linux": "run_benchmark.dist/run_benchmark",
            "Windows": "run_benchmark.dist\\run_benchmark.cmd",
        },
    }
    run_command = {
        "Nuitka": [
            comp_types[compilation_type][CURRENT_PLATFORM],
        ],
        "CPython": [str(python_executable), "run_benchmark.py"],
    }

    description_dict = {
        "CPython": f"{benchmark.name} with {type} {NORMALIZED_PYTHON_VERSION}",
        "Nuitka": f"{benchmark.name} with Nuitka {nuitka_version} | CPython: {NORMALIZED_PYTHON_VERSION}",
    }

    # for _ in track(
    #     range(iterations),
    #     description=f"[{count}/{number_of_benchmarks}] Warming up {description_dict[type]}",
    #     total=iterations,
    # ):
    for i in range(iterations):
        with Timer() as timer:
            res = run(run_command[type], check=False)  # type: ignore
            if res.returncode != 0:
                msg = f"Failed to run benchmark {benchmark.name} due to {res.stderr!r}"
                raise RuntimeError(msg)

        local_results["warmup"].append(timer.time_taken)
    print(
        f"Completed warming up {benchmark.name} with {type}, min: {min(local_results['warmup'])}"
    )

    # for _ in track(
    #     range(iterations),
    #     description=f"[{count}/{number_of_benchmarks}] Benchmarking {description_dict[type]}",
    #     total=iterations,
    # ):
    for i in range(iterations):
        with Timer() as timer:
            res = run(run_command[type], check=False)  # type: ignore
            if res.returncode != 0:
                msg = f"Failed to run benchmark {benchmark.name}"
                raise RuntimeError(msg)

        local_results["benchmark"].append(timer.time_taken)

    # print(
    #     f"Completed benchmarking {benchmark.name} with {type}, min: {min(local_results['benchmark'])}"
    # )
    print(
        f"[{count}/{number_of_benchmarks}] Completed benchmarking {description_dict[type]} with min: {min(local_results['benchmark'])}"
    )

    return local_results


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
) -> Generator[tuple[str, list[Benchmark]], None, None]:
    for _benchmark in _get_benchmarks(test=test):
        results_dir = _benchmark / "results"
        if not results_dir.exists():
            print(
                f"Skipping benchmark {_benchmark.name}, because {results_dir} does not exist"
            )
            continue

        benchmark_case_group: list[Benchmark] = []

        for result in results_dir.iterdir():
            if result.is_file():
                try:
                    benchmark = Benchmark.from_path(result, _benchmark.name)
                except FileNotFoundError as e:
                    print(e)
                    continue
                benchmark_case_group.append(benchmark)
        benchmark_case_group.sort(key=lambda x: x.python_version, reverse=True)

        yield benchmark.name, benchmark_case_group


def get_benchmark_setup() -> list[Path]:
    return list(_get_benchmarks())


def setup_benchmark_enviroment(
    requirements_path: Path,
    silent: bool = False,
) -> Path:
    python_executable = Path(sys.executable)

    try:

        cmd = "--lto=yes"  # let's not use PGO for now
        if CURRENT_PLATFORM == "Linux":
            # cmd += " --static-libpython=yes --pgo-c --pgo-python"
            cmd += " --static-libpython=yes --pgo-c"
        commands = [
            f"{python_executable} -m nuitka --disable-ccache --mingw64 --output-dir=run_benchmark.dist {cmd} run_benchmark.py".split()
        ]
        if requirements_path.exists():
            commands.insert(
                0,
                f"{python_executable} -m pip install -r {requirements_path.absolute()}".split(),
            )
        for command in commands:
            res = run(command, check=False)
            if res.returncode != 0:
                print(f"Failed to run command {command}")

    except Exception as e:
        msg = f"Failed to setup benchmark enviroment\n{e}"
        raise RuntimeError(msg) from e

    return python_executable
