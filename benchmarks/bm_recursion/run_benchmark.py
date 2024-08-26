"""
Benchmark for recursive fibonacci function.
"""
from time import perf_counter_ns

def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def bench_recursion(loops: int) -> float:
    range_it = range(loops)
    for _ in range_it:
        fibonacci(25)
    return loops


if __name__ == "__main__":
    start = perf_counter_ns()
    bench_recursion(100)
    end = perf_counter_ns()
    with open("bench_time.txt", "w") as f:
        f.write(str(end - start))
