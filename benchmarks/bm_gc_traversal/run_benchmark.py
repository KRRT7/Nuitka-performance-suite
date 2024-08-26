# import pyperf
import gc
from time import perf_counter_ns

N_LEVELS = 4500


def create_recursive_containers(n_levels):

    current_list = []
    for n in range(n_levels):
        new_list = [None] * n
        for index in range(n):
            new_list[index] = current_list
        current_list = new_list

    return current_list


def benchamark_collection(loops, n_levels):
    all_cycles = create_recursive_containers(n_levels)
    for _ in range(loops):
        gc.collect()
        # Main loop to measure
        # t0 = pyperf.perf_counter()
        collected = gc.collect()
        # total_time += pyperf.perf_counter() - t0

        assert collected is None or collected == 0



if __name__ == "__main__":
    # runner = pyperf.Runner()
    # runner.metadata["description"] = "GC traversal benchmark"
    # runner.bench_time_func("gc_traversal", benchamark_collection, N_LEVELS)
    start = perf_counter_ns()
    gc_traversal = benchamark_collection(10, N_LEVELS)
    end = perf_counter_ns()
    with open("bench_time.txt", "w") as f:
        f.write(str(end - start))
