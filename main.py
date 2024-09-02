import shutil
import sys

from rich import print

from benchengine import (
    CURRENT_PLATFORM,
    NORMALIZED_PYTHON_VERSION,
    Benchmarks,
    get_benchmark_setup,
    run_benchmark,
    setup_benchmark_enviroment,
    temporary_directory_change,
    check_if_excluded,
)

ITERATIONS = 100


def main(python_version: str, nuitka_version: str) -> None:
    benchmarks = get_benchmark_setup()
    counter, len_benchmarks = 0, len(benchmarks)
    for benchmark in benchmarks:
        if check_if_excluded(benchmark):
            print(f"Skipping benchmark {benchmark.name}, because it is excluded")
            counter += 1
            continue

        orig_path = benchmark.resolve()

        results_dir = orig_path / "results"
        results_file = results_dir / f"{CURRENT_PLATFORM}.json"

        benchmarks_obj: Benchmarks = Benchmarks(benchmarks_name=benchmark.name)

        if results_file.exists() and results_file.stat().st_size > 0:
            benchmarks_obj.from_json_file(results_file)

        if benchmarks_obj.verify_benchmark_presence(
            NORMALIZED_PYTHON_VERSION, nuitka_version
        ):
            print(
                f"Skipping benchmark {benchmark.name}, because it has already been run with {NORMALIZED_PYTHON_VERSION} and {nuitka_version}"
            )
            counter += 1
            continue

        elif not results_dir.exists():
            results_dir.mkdir(parents=True, exist_ok=True)
        results_file.touch(exist_ok=True)

        current_benchmark = benchmarks_obj.get_or_create_benchmark(
            NORMALIZED_PYTHON_VERSION
        )
        with temporary_directory_change(benchmark):
            requirements_path = orig_path / "requirements.txt"
            if not (orig_path / "run_benchmark.py").exists():
                print(
                    f"Skipping benchmark {benchmark.name}, because {orig_path / 'run_benchmark.py'} does not exist"
                )
                counter += 1
                continue

            python_executable = setup_benchmark_enviroment(
                requirements_path=requirements_path,
            )

            try:

                nuitka_result_warmup, nuitka_result_benchmark = run_benchmark(
                    benchmark=benchmark,
                    python_executable=python_executable,
                    iterations=ITERATIONS,
                    type="Nuitka",
                    compilation_type="accelerated",
                    nuitka_version=nuitka_version,
                    count=counter,
                    number_of_benchmarks=len_benchmarks,
                )

                cpython_result_warmup, cpython_result_benchmark = run_benchmark(
                    benchmark=benchmark,
                    python_executable=python_executable,
                    iterations=ITERATIONS,
                    nuitka_version=nuitka_version,
                    type="CPython",
                    count=counter,
                    number_of_benchmarks=len_benchmarks,
                )

                if nuitka_version.lower() == "standard":
                    current_benchmark.Nuitka_benchmark.standard.warmup.extend(
                        nuitka_result_warmup
                    )
                    current_benchmark.Nuitka_benchmark.standard.benchmark.extend(
                        nuitka_result_benchmark
                    )

                    current_benchmark.CPython_benchmark.standard.warmup.extend(
                        cpython_result_warmup
                    )
                    current_benchmark.CPython_benchmark.standard.benchmark.extend(
                        cpython_result_benchmark
                    )
                elif nuitka_version.lower() == "factory":
                    current_benchmark.Nuitka_benchmark.factory.warmup.extend(
                        nuitka_result_warmup
                    )
                    current_benchmark.Nuitka_benchmark.factory.benchmark.extend(
                        nuitka_result_benchmark
                    )

                    current_benchmark.CPython_benchmark.factory.warmup.extend(
                        cpython_result_warmup
                    )
                    current_benchmark.CPython_benchmark.factory.benchmark.extend(
                        cpython_result_benchmark
                    )
                else:
                    raise ValueError("Invalid Nuitka version")

                benchmarks_obj.add_benchmark(current_benchmark)
                benchmarks_obj.to_json_file(results_file)

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
        raise ValueError("Usage: python main.py <python_version> <nuitka_version>")

    python_version = sys.argv[1]
    nuitka_version = sys.argv[2]

    main(python_version, nuitka_version)
