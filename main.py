from rework.tvenv import compile_benchmark, run_benchmark
from rework.utils import console, get_benchmarks, cleanup
from rich.progress import track
from pathlib import Path

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
        cleanup(
            benchmark,
            to_keep=[file for file in benchmark.iterdir() if "uv" not in file.name],
        )


if __name__ == "__main__":
    main()
