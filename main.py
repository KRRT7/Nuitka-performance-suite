from engine.tvenv import Benchmark
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

    benchmarks = sorted(_benchmarks)

    for benchmark_path in track(
        benchmarks,
        description="Compiling benchmarks",
        console=console,
        auto_refresh=False,
        total=len(benchmarks),
    ):
        fname = f"{benchmark_path.parent.name}/{benchmark_path.name}"
        console.rule(f"Compiling {benchmark_path.name} @ {fname}")

        benchmark = Benchmark(benchmark_path)
        benchmark.execute()

    clean()


if __name__ == "__main__":
    args = parse_args()
    if args.clean:
        clean()
    else:
        main(args.benchmarks if args.benchmarks else None)
