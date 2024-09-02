from __future__ import annotations

import os
import platform
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from json import dump, load
from pathlib import Path
from statistics import mean
from subprocess import run
from time import perf_counter
from typing import Any, Callable, Generator, Iterator, Literal

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
    "Linux": {(3, 9): ["bm_django_template"], (3, 12): ["bm_2to3"]},
    "Windows": {(3, 9): ["bm_django_template"]},
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
class BenchmarkV2:
    warmup: list[int] = field(default_factory=list)
    benchmark: list[int] = field(default_factory=list)


@dataclass
class BenchmarkFile:
    standard: BenchmarkV2 = field(default_factory=BenchmarkV2)
    factory: BenchmarkV2 = field(default_factory=BenchmarkV2)


@dataclass
class BenchmarkHolder:
    benchmark_name: str
    python_version: str
    CPython_benchmark: BenchmarkFile
    Nuitka_benchmark: BenchmarkFile

    def to_dict(self) -> dict[str, Any]:
        return {
            self.python_version: {
                "Standard": {
                    "Nuitka": {
                        "Warmup": self.Nuitka_benchmark.standard.warmup,
                        "Benchmark": self.Nuitka_benchmark.standard.benchmark,
                    },
                    "CPython": {
                        "Warmup": self.CPython_benchmark.standard.warmup,
                        "Benchmark": self.CPython_benchmark.standard.benchmark,
                    },
                },
                "Factory": {
                    "Nuitka": {
                        "Warmup": self.Nuitka_benchmark.factory.warmup,
                        "Benchmark": self.Nuitka_benchmark.factory.benchmark,
                    },
                    "CPython": {
                        "Warmup": self.CPython_benchmark.factory.warmup,
                        "Benchmark": self.CPython_benchmark.factory.benchmark,
                    },
                },
            }
        }

    @classmethod
    def from_dict(
        cls, benchmark_dict: dict[str, Any], benchmark_name: str, python_version: str
    ) -> BenchmarkHolder:
        standard = benchmark_dict["Standard"]
        factory = benchmark_dict["Factory"]

        standard_nuitka = standard["Nuitka"]
        standard_cpython = standard["CPython"]

        factory_nuitka = factory["Nuitka"]
        factory_cpython = factory["CPython"]

        return cls(
            benchmark_name,
            python_version,
            BenchmarkFile(
                BenchmarkV2(
                    standard_nuitka["Warmup"],
                    standard_nuitka["Benchmark"],
                ),
                BenchmarkV2(
                    factory_nuitka["Warmup"],
                    factory_nuitka["Benchmark"],
                ),
            ),
            BenchmarkFile(
                BenchmarkV2(
                    standard_cpython["Warmup"],
                    standard_cpython["Benchmark"],
                ),
                BenchmarkV2(
                    factory_cpython["Warmup"],
                    factory_cpython["Benchmark"],
                ),
            ),
        )


@dataclass
class Benchmarks:
    benchmarks_name: str
    benchmarks: dict[str, BenchmarkHolder] = field(default_factory=dict)

    def add_benchmark(self, benchmark: BenchmarkHolder) -> None:
        self.benchmarks[benchmark.python_version] = benchmark

    def from_json_file(self, file_path: Path) -> None:
        with open(file_path) as f:
            contents: dict[str, dict[str, dict[str, dict[str, list[int]]]]] = load(f)

        if not contents:
            return

        for python_version in contents:
            benchmark = BenchmarkHolder.from_dict(
                contents[python_version], self.benchmarks_name, python_version
            )
            self.add_benchmark(benchmark)

    def get_or_create_benchmark(self, python_version: str) -> BenchmarkHolder:
        return self.benchmarks.setdefault(
            python_version,
            BenchmarkHolder(
                self.benchmarks_name, python_version, BenchmarkFile(), BenchmarkFile()
            ),
        )

    def verify_benchmark_presence(
        self, python_version: str, nuitka_version: str
    ) -> bool:
        inf_dict = self.benchmarks.get(python_version)
        if not inf_dict:
            return False

        if nuitka_version == "standard":
            standard_warmup_cpython = bool(inf_dict.CPython_benchmark.standard.warmup)
            standard_benchmark_cpython = bool(
                inf_dict.CPython_benchmark.standard.benchmark
            )
            standard_warmup_nuitka = bool(inf_dict.Nuitka_benchmark.standard.warmup)
            standard_benchmark_nuitka = bool(
                inf_dict.Nuitka_benchmark.standard.benchmark
            )
            return all(
                [
                    standard_warmup_cpython,
                    standard_benchmark_cpython,
                    standard_warmup_nuitka,
                    standard_benchmark_nuitka,
                ]
            )
        elif nuitka_version == "factory":
            factory_warmup_cpython = inf_dict.CPython_benchmark.factory.warmup
            factory_benchmark_cpython = inf_dict.CPython_benchmark.factory.benchmark
            factory_warmup_nuitka = inf_dict.Nuitka_benchmark.factory.warmup
            factory_benchmark_nuitka = inf_dict.Nuitka_benchmark.factory.benchmark
            return all(
                [
                    bool(factory_warmup_cpython),
                    bool(factory_benchmark_cpython),
                    bool(factory_warmup_nuitka),
                    bool(factory_benchmark_nuitka),
                ]
            )
        else:
            raise ValueError(f"Invalid Nuitka version, got {nuitka_version}")

    def to_json_file(self, file_path: Path) -> None:
        contents = {}
        for _, benchmark in self.benchmarks.items():
            contents.update(benchmark.to_dict())
        with open(file_path, "w") as f:
            dump(contents, f)

    def get_visualizer_setup(
        self,
    ) -> Generator[tuple[str, BenchmarkHolder], None, None]:
        for python_version, benchmark in self.benchmarks.items():
            yield python_version, benchmark


@dataclass
class Stats:
    name: str
    warmup: list[int]
    benchmark: list[int]

    @classmethod
    def from_dict(cls, stats_dict: dict[str, list[int]], name: str) -> Stats:
        return cls(
            name,
            stats_dict["warmup"],
            stats_dict["benchmark"],
        )


@dataclass
class Benchmark:
    name: str
    nuitka_version: str | None = None
    file_json: dict[str, dict[str, list[int]]] | None = None
    nuitka_stats: Stats | None = None
    cpython_stats: Stats | None = None
    factory: Benchmark | None = None
    python_version: tuple[int, int] | None = None

    def parse_stats(self, stats: dict[str, dict[str, list[int]]]) -> None:
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
) -> tuple[list[int], list[int]]:
    warmup_results: list[int] = []
    benchmark_results: list[int] = []

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
        "CPython": [python_executable, "run_benchmark.py"],
    }

    description_dict = {
        "CPython": f"{benchmark.name} with {type} {NORMALIZED_PYTHON_VERSION}",
        "Nuitka": f"{benchmark.name} with Nuitka {nuitka_version} | CPython: {NORMALIZED_PYTHON_VERSION}",
    }

    for _ in track(
        range(iterations),
        description=f"[{count}/{number_of_benchmarks}] Warming up {description_dict[type]}",
        total=iterations,
    ):
        res = run(run_command[type], check=False)  # type: ignore
        if res.returncode != 0:
            msg = f"Failed to run benchmark {benchmark.name} due to {res.stderr!r}"
            raise RuntimeError(msg)

        with open("bench_time.txt") as f:
            time_taken = int(f.read())

        warmup_results.append(time_taken)

    for _ in track(
        range(iterations),
        description=f"[{count}/{number_of_benchmarks}] Benchmarking {description_dict[type]}",
        total=iterations,
    ):
        res = run(run_command[type], check=False)  # type: ignore
        if res.returncode != 0:
            msg = f"Failed to run benchmark {benchmark.name}"
            raise RuntimeError(msg)

        with open("bench_time.txt") as f:
            time_taken = int(f.read())

        benchmark_results.append(time_taken)

    print(f"Completed benchmarking {benchmark.name} with {type}")

    return warmup_results, benchmark_results


def is_in_venv() -> bool:
    # https://stackoverflow.com/a/1883251
    return sys.prefix != sys.base_prefix


def _get_benchmarks(test: bool = False) -> Iterator[Path]:
    bench_dir = TEST_BENCHMARK_DIRECTORY if test else BENCHMARK_DIRECTORY
    for benchmark_case in bench_dir.iterdir():
        if not benchmark_case.is_dir() or not benchmark_case.name.startswith("bm_"):
            continue
        yield benchmark_case


# def get_visualizer_setup(
#     test: bool = False,
#     # ) -> Generator[tuple[str, list[Benchmark]], None, None]:
# ) -> Generator[tuple[str, Benchmarks], None, None]:
#     for _benchmark in _get_benchmarks(test=test):
#         results_dir = _benchmark / "results"
#         if not results_dir.exists():
#             print(
#                 f"Skipping benchmark {_benchmark.name}, because {results_dir} does not exist"
#             )
#             continue

#         # return Benchmarks.from_json_file(results_dir / f"{CURRENT_PLATFORM}.json")
#         benchmarks = Benchmarks(benchmarks_name=_benchmark.name)
#         benchmarks.from_json_file(results_dir / f"{CURRENT_PLATFORM}.json")
#         yield _benchmark.name, benchmarks


def get_visualizer_setup(test: bool = False):
    benchmarks = Benchmarks(benchmarks_name="Visualizer")
    for benchmark in _get_benchmarks(test=test):
        results_dir = benchmark / "results"
        file = results_dir / f"{CURRENT_PLATFORM}.json"
        if not results_dir.exists() or file.stat().st_size == 0:
            continue
        benchmarks.from_json_file(file)
    return benchmarks


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
            cmd += " --static-libpython=yes"
        commands = [
            f"{python_executable} -m nuitka --output-dir=run_benchmark.dist {cmd} run_benchmark.py".split()
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
