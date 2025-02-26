from engine.tvenv import compile_benchmark, run_benchmark
from engine.utils import console, get_benchmarks, clean, parse_args
from rich.progress import track
from pathlib import Path


def main(benchmarks=None):
    _benchmarks = list(get_benchmarks(Path.cwd() / "benchmarks"))
    if benchmarks:
        _benchmarks = [
            b
            for b in _benchmarks
            if any(benchmark in b.name for benchmark in benchmarks)
        ]

    benchmarks = _benchmarks

    console.print(f"Running benchmarks: {benchmarks}")
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


if __name__ == "__main__":
    args = parse_args()
    if args.clean:
        clean()
    else:
        main(args.benchmarks if args.benchmarks else None)
