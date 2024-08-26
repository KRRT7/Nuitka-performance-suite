"""
Calculate `factorial` using the decimal module.

- 2024-06-14: Michael Droettboom copied this from
  Modules/_decimal/tests/bench.py in the CPython source and adapted to use
  pyperf.
"""

# Original copyright notice in CPython source:

#
# Copyright (C) 2001-2012 Python Software Foundation. All Rights Reserved.
# Modified and extended by Stefan Krah.
#


import decimal
from time import perf_counter_ns


# import pyperf


def factorial(n, m):
    if n > m:
        return factorial(m, n)
    elif m == 0:
        return 1
    elif n == m:
        return n
    else:
        return factorial(n, (n + m) // 2) * factorial((n + m) // 2 + 1, m)


def bench_decimal_factorial():
    c = decimal.getcontext()
    c.prec = decimal.MAX_PREC
    c.Emax = decimal.MAX_EMAX
    c.Emin = decimal.MIN_EMIN

    for n in [10000, 100000, 20000, 200000, 10000, 100000]:
        # C version of decimal
        _ = factorial(decimal.Decimal(n), 0)


if __name__ == "__main__":
    # runner = pyperf.Runner()
    # runner.metadata["description"] = "decimal_factorial benchmark"

    # args = runner.parse_args()
    # runner.bench_func("decimal_factorial", bench_decimal_factorial)
    start = perf_counter_ns()
    bench_decimal_factorial()
    end = perf_counter_ns()
    with open("bench_time.txt", "w") as f:
        f.write(str(end - start))