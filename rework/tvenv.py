from pathlib import Path
from rework.utils import (
    temporary_directory_change,
    run_command_in_subprocess,
    MS_WINDOWS,
)

from rework.benchmark_prepare import prepare_benchmark_file


def compile_benchmark(benchmark_path: Path) -> None:
    requirements = Path(benchmark_path / "requirements.txt")
    reqs_exist = requirements.exists()
    run_benchmark_path = benchmark_path / "run_benchmark.py"
    original_contents = run_benchmark_path.read_text()
    prepare_benchmark_file(benchmark_path)
    with temporary_directory_change(benchmark_path):
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
        if reqs_exist:
            run_command_in_subprocess(
                ["uv", "pip", "install", "-r", "requirements.txt"]
            )

        command = ["uvx", "--with", "setuptools", "--with", "wheel"]
        if reqs_exist:
            command += ["--with-requirements", requirements.as_posix()]

        command += [
            "nuitka",
            "--onefile",
            "--lto=yes",
            "--remove-output",
            "--assume-yes-for-downloads",
            "--clang",
            # "--disable-cache=all",
            "--run",
            "run_benchmark.py",
        ]
        result = run_command_in_subprocess(command)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to compile benchmark: {result.stderr}")
    with run_benchmark_path.open("w") as f:
        f.write(original_contents)


def run_benchmark(benchmark_path: Path, iterations: int = 50) -> None:
    with temporary_directory_change(benchmark_path):
        command = [
            "hyperfine",
            "--show-output",
            "--warmup",
            "50",
            "--min-runs",
            str(iterations),
            "./run_benchmark.bin",
            ".venv/bin/python run_benchmark.py",
        ]
        # command.append("run_benchmark.exe" if MS_WINDOWS else "./run_benchmark.bin") # for windows in the future
        result = run_command_in_subprocess(command)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to run benchmark: {result.stderr}")
