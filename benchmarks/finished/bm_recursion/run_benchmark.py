"""
Benchmark for recursive fibonacci function.
"""


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
    bench_recursion(100)
