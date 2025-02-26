from pathlib import Path
from engine.utils import (
    temporary_directory_change,
    run_command_in_subprocess,
)

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
                if self.requirements_exist
                else "./run_benchmark.bin"
            )
            command = [
                "hyperfine",
                "--show-output",
                "--warmup",
                iters,
                "--min-runs",
                iters,
                ".venv/bin/python run_benchmark.py",
                executable,
            ]
            result = run_command_in_subprocess(command)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to run benchmark: {result.stderr}")

    def execute(self, iters: str = "100") -> None:
        self.compile()
        self.run(iters)
