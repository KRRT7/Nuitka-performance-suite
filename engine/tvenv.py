from pathlib import Path
import json

from engine.utils import (
    temporary_directory_change,
    run_command_in_subprocess,
    console,
)
from rich.table import Table
from rich.panel import Panel
from rich import box
from typing import Any
from engine.benchmark_prepare import prepare_benchmark_file


class Benchmark:
    def __init__(self, benchmark_path: Path):
        self.benchmark_path = benchmark_path
        self.run_benchmark_path = benchmark_path / "run_benchmark.py"
        self.requirements_path = benchmark_path / "requirements.txt"
        self.requirements_exist = self.requirements_path.exists()
        self.original_contents = None

    def prepare(self):
        self.original_contents = self.run_benchmark_path.read_text()
        prepare_benchmark_file(self.benchmark_path)

    def restore(self):
        if self.original_contents:
            with self.run_benchmark_path.open("w") as f:
                f.write(self.original_contents)

    def compile(self) -> None:
        self.prepare()

        try:
            with temporary_directory_change(self.benchmark_path):
                run_command_in_subprocess(["uv", "venv"])

                run_command_in_subprocess(
                    [
                        "uv",
                        "pip",
                        "install",
                        "wheel",
                        "setuptools",
                        "git+https://github.com/KRRT7/Nuitka@thin-flto",
                    ]
                )
                if self.requirements_exist:
                    run_command_in_subprocess(
                        ["uv", "pip", "install", "-r", "requirements.txt"]
                    )

                command = ["uvx", "--with", "setuptools", "--with", "wheel"]
                if self.requirements_exist:
                    command += [
                        "--with-requirements",
                        self.requirements_path.as_posix(),
                    ]

                command += [
                    "nuitka",
                    "--lto=yes",
                    "--remove-output",
                    "--assume-yes-for-downloads",
                    "--clang",
                    "--disable-cache=all",
                    "--pgo-python",
                    # "--run",
                    "run_benchmark.py",
                ]
                result = run_command_in_subprocess(command)
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to compile benchmark: {result.stderr}")
        finally:
            self.restore()

    def run(self, iters: str = "100") -> None:
        with temporary_directory_change(self.benchmark_path):
            executable = (
                "./run_benchmark.sh"
                if (self.benchmark_path / "run_benchmark.sh").exists()
                else "./run_benchmark.bin"
            )
            command = [
                "hyperfine",
                "--show-output",
                "--warmup",
                iters,
                "--runs",
                iters,
                "--export-json",
                "benchmark_results.json",
                ".venv/bin/python run_benchmark.py",
                executable,
            ]
            result = run_command_in_subprocess(command)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to run benchmark: {result.stderr}")

    def execute(self, iters: str = "100") -> None:
        self.compile()
        self.run(iters)

    def report(self) -> dict[str, Any]:
        results_path = self.benchmark_path / "benchmark_results.json"

        if not results_path.exists():
            console.print(
                f"[bold red]Error:[/bold red] Benchmark results file not found at {results_path}"
            )
            raise FileNotFoundError(f"Benchmark results file not found at {results_path}")

        try:
            with open(results_path, "r") as f:
                data = json.load(f)

            if "results" not in data or len(data["results"]) != 2:
                raise ValueError("Invalid benchmark results format")

            python_data = next(
                (r for r in data["results"] if ".venv/bin/python" in r["command"]), None
            )
            nuitka_data = next(
                (r for r in data["results"] if "./run_benchmark" in r["command"]), None
            )

            if not python_data or not nuitka_data:
                raise ValueError("Invalid benchmark results format")

            python_mean = python_data["mean"]
            nuitka_mean = nuitka_data["mean"]
            speedup_ratio = (
                python_mean / nuitka_mean if nuitka_mean > 0 else float("inf")
            )
            percent_change = (
                (1 - nuitka_mean / python_mean) * 100
                if python_mean > 0
                else float("inf")
            )

            summary = {
                "benchmark_name": self.benchmark_path.name,
                "python": {
                    "mean": python_mean,
                    "median": python_data["median"],
                    "stddev": python_data["stddev"],
                    "min": python_data["min"],
                    "max": python_data["max"],
                },
                "nuitka": {
                    "mean": nuitka_mean,
                    "median": nuitka_data["median"],
                    "stddev": nuitka_data["stddev"],
                    "min": nuitka_data["min"],
                    "max": nuitka_data["max"],
                },
                "comparison": {
                    "speedup_ratio": speedup_ratio,
                    "percent_change": percent_change,
                    "is_nuitka_faster": speedup_ratio > 1,
                },
            }

            self._display_report(summary)
            return summary

        except Exception as e:
            console.print(
                f"[bold red]Error:[/bold red] Failed to process benchmark results: {str(e)}"
            )
            return {"error": f"Failed to process benchmark results: {str(e)}"}

    def _display_report(self, summary: dict[str, Any]) -> None:
        table = Table(
            title=f"[bold blue]Benchmark Results: {summary['benchmark_name']}[/bold blue]",
            box=box.ROUNDED,
            header_style="bold magenta",
        )

        table.add_column("Metric", style="cyan")
        table.add_column("CPython", style="green")
        table.add_column("Nuitka", style="yellow")
        table.add_column("Difference", style="blue")

        def format_time(seconds: float) -> str:
            return f"{seconds * 1000:.2f} ms"

        python_data = summary["python"]
        nuitka_data = summary["nuitka"]
        comparison = summary["comparison"]

        speedup = f"{comparison['speedup_ratio']:.2f}x"
        speedup_style = (
            "[bold green]" if comparison["is_nuitka_faster"] else "[bold red]"
        )

        table.add_row(
            "Mean Execution Time",
            format_time(python_data["mean"]),
            format_time(nuitka_data["mean"]),
            f"{speedup_style}{speedup}[/]",
        )

        table.add_row(
            "Median Execution Time",
            format_time(python_data["median"]),
            format_time(nuitka_data["median"]),
            "",
        )

        table.add_row(
            "Min/Max Time",
            f"{format_time(python_data['min'])} / {format_time(python_data['max'])}",
            f"{format_time(nuitka_data['min'])} / {format_time(nuitka_data['max'])}",
            "",
        )

        table.add_row(
            "Standard Deviation",
            format_time(python_data["stddev"]),
            format_time(nuitka_data["stddev"]),
            "",
        )

        percent_change = comparison["percent_change"]
        percent_str = f"{percent_change:.2f}%"
        percent_style = "[bold green]" if percent_change > 0 else "[bold red]"
        table.add_row(
            "Performance Improvement", "", "", f"{percent_style}{percent_str}[/]"
        )

        console.print(table)

        status = (
            "[bold green]FASTER[/bold green]"
            if comparison["is_nuitka_faster"]
            else "[bold red]SLOWER[/bold red]"
        )
        summary_text = (
            f"Nuitka compilation is {status} than CPython by {abs(percent_change):.2f}%"
        )
        console.print(
            Panel(
                summary_text,
                title="[bold]Summary[/bold]",
                border_style="blue",
                expand=False,
            )
        )
