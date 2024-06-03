from Utilities import (
    temporary_directory_change,
    run_benchmark,
    parse_py_launcher,
    create_venv_with_version,
    NUITKA_VERSIONS,
    calculate_stats,
)
from pathlib import Path
import shutil
from subprocess import run, PIPE
from rich import print
from rich.table import Table
from itertools import product
import json
from datetime import datetime

BENCHMARK_DIRECTORY = Path("benchmarks")
ITERATIONS = 100


versions = parse_py_launcher()

# for python_version, nuitka_version in product(versions, NUITKA_VERSIONS):
for python_version in versions:
    nuitka_version = "Nuitka"
    if "github" in nuitka_version:
        nuitka_name = "Nuitka-factory"
    else:
        nuitka_name = "Nuitka-release"

    for benchmark in BENCHMARK_DIRECTORY.iterdir():
        if benchmark.is_dir() and not benchmark.name.startswith("bm_"):
            continue

        if benchmark.is_dir():
            orig_path = benchmark.resolve()
            bench_results: dict[str, dict[str, list[float]]] = {
                "nuitka": {"benchmark": [], "warmup": []},
                "cpython": {"benchmark": [], "warmup": []},
            }
            results_dir = orig_path / "results" / datetime.now().strftime("%Y-%m-%d")
            if not results_dir.exists():
                results_dir.mkdir(parents=True, exist_ok=True)

            results_file = results_dir / f"{nuitka_name}-{python_version}.json"
            if results_file.exists() and results_file.stat().st_size > 0:
                print(f"Skipping benchmark {benchmark.name}, because results exist")
                continue

            results_file.touch()

            with temporary_directory_change(benchmark):
                requirements_exists = (orig_path / "requirements.txt").exists()
                if not (orig_path / "run_benchmark.py").exists():
                    print(
                        f"Skipping benchmark {benchmark.name}, because {orig_path / 'run_benchmark.py'} does not exist"
                    )
                    continue
                python_executable = create_venv_with_version(python_version)
                try:
                    commands = [
                        f"{python_executable} --version",
                        f"{python_executable} -m pip install --upgrade pip",
                        f"{python_executable} -m pip install {nuitka_version}",
                        f"{python_executable} -m pip install ordered-set",
                        f"{python_executable} -m pip install appdirs",
                        f"{python_executable} -m nuitka --standalone --remove-output run_benchmark.py",
                    ]
                    if requirements_exists:
                        commands.insert(
                            2, f"{python_executable} -m pip install -r requirements.txt"
                        )
                    for command in commands:
                        res = run(command, stdout=PIPE, stderr=PIPE)
                        if res.returncode != 0:
                            print(f"Failed to run command {command}")
                            break

                    bench_results["nuitka"] = run_benchmark(
                        benchmark,
                        python_executable,
                        ITERATIONS,
                        python_version,
                        "Nuitka",
                        nuitka_name,
                    )

                    bench_results["cpython"] = run_benchmark(
                        benchmark,
                        python_executable,
                        ITERATIONS,
                        python_version,
                        "CPython",
                        nuitka_name,
                    )

                    with open(results_file, "w") as f:
                        json.dump(bench_results, f)
                    results = Table(
                        title=f"Benchmarks for {benchmark.name}, {python_version}"
                    )
                    results.add_column("Benchmark", justify="left", style="cyan")
                    results.add_column("Nuitka", justify="right", style="magenta")
                    results.add_column("CPython", justify="right", style="green")

                    print(calculate_stats(bench_results["nuitka"]))
                    # min_nuitka = min(
                    #     sum(bench_results["nuitka"]["benchmark"])
                    #     / len(bench_results["nuitka"]["benchmark"]),
                    #     sum(bench_results["nuitka"]["warmup"])
                    #     / len(bench_results["nuitka"]["warmup"]),
                    # )
                    # min_nuitka = min(
                    #     calculate_average(bench_results["nuitka"]["benchmark"]),
                    #     calculate_average(bench_results["nuitka"]["warmup"]),
                    # )

                    # min_cpython = min(
                    #     sum(bench_results["cpython"]["benchmark"])
                    #     / len(bench_results["cpython"]["benchmark"]),
                    #     sum(bench_results["cpython"]["warmup"])
                    #     / len(bench_results["cpython"]["warmup"]),
                    # )

                    # if min_nuitka < min_cpython:
                    #     print(
                    #         f"{nuitka_version} is faster for benchmark {benchmark.name} by {((min_cpython - min_nuitka) / min_cpython) * 100:.2f}%"
                    #     )
                    # else:
                    #     print(
                    #         f"{python_version} is faster for benchmark {benchmark.name} by {((min_nuitka - min_cpython) / min_nuitka) * 100:.2f}%"
                    #     )
                    # results.add_section()
                    # for key in ["warmup", "benchmark"]:
                    #     results.add_row(
                    #         key,
                    #         f"{sum(bench_results['nuitka'][key]) / ITERATIONS:.2f}",
                    #         f"{sum(bench_results['cpython'][key]) / ITERATIONS:.2f}",
                    #     )

                    # print(results)
                    # cleanup the benchmark directory venv
                except KeyboardInterrupt:
                    print(
                        f"Interrupted running benchmark {benchmark.name} with {python_version}, cleaning up"
                    )
                    break
                except Exception as e:
                    print(
                        f"Failed to run benchmark {benchmark.name} with {python_version}"
                    )
                    print(e)
                    break
                finally:
                    # cleanup the benchmark directory venv and dist
                    venv_path = python_executable.parent.parent
                    dist_path = benchmark / "run_benchmark.dist"
                    # print(f"Removing venv {venv_path}")
                    shutil.rmtree(venv_path)
                    if dist_path.exists():
                        shutil.rmtree(dist_path)
