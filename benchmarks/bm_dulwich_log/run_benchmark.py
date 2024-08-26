"""
Iterate on commits of the asyncio Git repository using the Dulwich module.
"""

import os

# import pyperf

import dulwich.repo
from time import perf_counter_ns


def iter_all_commits(repo):
    # iterate on all changes on the Git repository
    for entry in repo.get_walker(head):
        pass


if __name__ == "__main__":
    # runner = pyperf.Runner()
    # runner.metadata['description'] = ("Dulwich benchmark: "
    #                                   "iterate on all Git commits")
    start = perf_counter_ns()
    repo_path = os.path.join(os.path.dirname(__file__), 'data', 'asyncio.git')

    repo = dulwich.repo.Repo(repo_path)
    head = repo.head()
    # runner.bench_func('dulwich_log', iter_all_commits, repo)
    for i in range(12):
        iter_all_commits(repo)
    repo.close()
    end = perf_counter_ns()
    with open("bench_time.txt", "w") as f:
        f.write(str(end - start))
