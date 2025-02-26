from rework.tvenv import compile_benchmark, run_benchmark
from rework.utils import console, get_benchmarks, clean
from rich.progress import track
from pathlib import Path
from argparse import ArgumentParser


def main():
    benchmarks = list(get_benchmarks(Path.cwd() / "benchmarks"))
    for benchmark in track(
        benchmarks,
        description="Compiling benchmarks",
        console=console,
        auto_refresh=False,
        total=len(benchmarks),
    ):
        fname = f"{benchmark.parent.name}/{benchmark.name}"
        console.rule(f"Compiling {benchmark.name} @ {fname}")
        compile_benchmark(benchmark)
        run_benchmark(benchmark)
        clean()


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "--clean", action="store_true", help="Clean up compiled benchmarks"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.clean:
        clean()
    else:
        main()
