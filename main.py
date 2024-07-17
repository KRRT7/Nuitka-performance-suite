import shutil
import sys
from datetime import datetime

from rich import print

from benchengine import (
    CURRENT_PLATFORM,
    NORMALIZED_PYTHON_VERSION,
    Benchmark,
    Stats,
    get_benchmark_setup,
    run_benchmark,
    setup_benchmark_enviroment,
    temporary_directory_change,
)

ITERATIONS = 100


def main(python_version, nuitka_version):
    benchmarks = get_benchmark_setup()
    counter, len_benchmarks = 0, len(benchmarks)
    for benchmark in benchmarks:
        orig_path = benchmark.resolve()

        results_dir = orig_path / "results" / datetime.now().strftime("%Y-%m-%d")
        # results_dir = orig_path / "results" / datetime.now().strftime("%Y-%m-%d")
        results_dir = orig_path / "results"
        results_file = (
            results_dir
            / f"{CURRENT_PLATFORM}-{NORMALIZED_PYTHON_VERSION}-{nuitka_version}.json"
        )

        if results_file.exists() and results_file.stat().st_size > 0:
            print(
                f"Skipping benchmark {benchmark.name}, because results exist for {benchmark.name} with {NORMALIZED_PYTHON_VERSION} and {nuitka_version}"
            )
            counter += 1
            continue

        if not results_dir.exists():
            results_dir.mkdir(parents=True, exist_ok=True)
        results_file.touch(exist_ok=True)

        bench_result = Benchmark(
            nuitka_version=nuitka_version, name=benchmark.name
        )

        with temporary_directory_change(benchmark):
            requirements_path = orig_path / "requirements.txt"
            if not (orig_path / "run_benchmark.py").exists():
                print(
                    f"Skipping benchmark {benchmark.name}, because {orig_path / 'run_benchmark.py'} does not exist"
                )
                continue

            python_executable = setup_benchmark_enviroment(
                requirements_path=requirements_path,
            )

            try:

                nuitka_benchmark = run_benchmark(
                    benchmark=benchmark,
                    python_executable=python_executable,
                    iterations=ITERATIONS,
                    type="Nuitka",
                    compilation_type="accelerated",
                    nuitka_version=nuitka_version,
                    count=counter,
                    number_of_benchmarks=len_benchmarks,
                )
                bench_result.nuitka_stats = Stats.from_dict(nuitka_benchmark, "nuitka")

                cpython_benchmark = run_benchmark(
                    benchmark=benchmark,
                    python_executable=python_executable,
                    iterations=ITERATIONS,
                    nuitka_version=nuitka_version,
                    type="CPython",
                    count=counter,
                    number_of_benchmarks=len_benchmarks,
                )

                bench_result.cpython_stats = Stats.from_dict(
                    cpython_benchmark, "cpython"
                )

                bench_result.to_json_file(results_file)

            except KeyboardInterrupt:
                print(
                    f"Interrupted running benchmark {benchmark.name} with {NORMALIZED_PYTHON_VERSION}, cleaning up"
                )
                raise SystemExit from None
            except Exception as e:
                print(
                    f"Failed to run benchmark {benchmark.name} with {NORMALIZED_PYTHON_VERSION}\n{e}"
                )
                break
            finally:
                dist_path = (orig_path / "run_benchmark.dist").resolve()
                if dist_path.exists():
                    shutil.rmtree(dist_path)
                counter += 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python main.py <python_version> <nuitka_version>")
        sys.exit(1)

    python_version = sys.argv[1]
    nuitka_version = sys.argv[2]

    main(python_version, nuitka_version)
