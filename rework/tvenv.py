from pathlib import Path
from rework import utils

from rework.benchmark_prepare import prepare_benchmark_file


class Requirements:
    def __init__(self, requirements_path: Path):
        self.path = requirements_path

    def uv_sync_list(self) -> list[str]:
        requirements = []
        prereqs = [
            "wheel",
            "setuptools",
            "git+https://github.com/KRRT7/Nuitka@thin-flto",
        ]
        for prereq in prereqs:
            requirements.extend(["--with", prereq])
        if not self.path.exists():
            return requirements
        with self.path.open("r") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                requirements.extend(["--with", line])
        return requirements


def compile_benchmark(benchmark_path: Path) -> None:
    requirements = Requirements(benchmark_path / "requirements.txt").uv_sync_list()
    run_benchmark_path = benchmark_path / "run_benchmark.py"
    original_contents = run_benchmark_path.read_text()
    prepare_benchmark_file(benchmark_path)
    with utils.temporary_directory_change(benchmark_path):
        build_command = [
            "uv",
            "run",
        ]

        build_command.extend(requirements)

        build_command += [
            "--",
            "nuitka",
            "--onefile",
            # "--pgo-c", #PGO is currently broken, open issue on Nuitka
            # "--pgo-python",
            "--lto=yes",
            "--remove-output",
            "--assume-yes-for-downloads",
            # "--low-memory", # only needed in GH actions
            "--run",
            "run_benchmark.py",
        ]

        result = utils.run_command_in_subprocess(build_command)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to compile benchmark: {result.stderr}")
    with run_benchmark_path.open("w") as f:
        f.write(original_contents)