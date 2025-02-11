from rework.tvenv import compile_benchmark
from rework.utils import console, get_benchmarks, cleanup
from rich.progress import track
from pathlib import Path
from rich import print
from functools import partial


class Benchmark:
    def __init__(self, benchmark: Path):
        self.benchmark = benchmark
        self.name = benchmark.name
        self.iterations = 5

    def run(self): ...

    def run_benchmark(self):
        partialed_commands = {
            # "Nuitka": partial(
            #     self.venv.run_command_in_terminal,
            #     Path(os.getcwd()) / "run_benchmark.cmd",
            # ),
            "CPython": partial(
                self.venv.run_command_with_venv_python, "run_benchmark.py"
            ),
        }

        for type, command in partialed_commands.items():
            print(f"Running benchmark with {type}")
            for _ in track(
                range(self.iterations),
                description=f"Running {type} benchmark",
                total=self.iterations,
            ):
                command()


def main():
    benchmarks = list(get_benchmarks(Path.cwd() / "benchmarks"))
    for benchmark in track(
        benchmarks,
        description="Compiling benchmarks",
        console=console,
        auto_refresh=False,
        total=len(benchmarks),
    ):
        console.rule(f"Compiling {benchmark.name} @ {benchmark}")
        compile_benchmark(benchmark)
        cleanup(
            benchmark,
            to_keep=[file for file in benchmark.iterdir() if "uv" not in file.name],
        )
        # benchmark = Benchmark(benchmark=benchmark)
        # benchmark.run_benchmark()


if __name__ == "__main__":
    main()
