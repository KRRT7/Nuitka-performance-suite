"""
Convert Docutils' documentation from reStructuredText to <format>.
"""

import contextlib
from pathlib import Path

import docutils
from docutils import core

# import pyperf
from time import perf_counter_ns

try:
    from docutils.utils.math.math2html import Trace
except ImportError:
    pass
else:
    Trace.show = lambda message, channel: ...  # don't print to console

DOC_ROOT = (Path(__file__).parent / "data" / "docs").resolve()

def build_html(doc_root):
    for file in doc_root.rglob("*.txt"):
        file_contents = file.read_text(encoding="utf-8")
        # t0 = pyperf.perf_counter()
        with contextlib.suppress(docutils.ApplicationError):
            core.publish_string(
                source=file_contents,
                reader_name="standalone",
                parser_name="restructuredtext",
                writer_name="html5",
                settings_overrides={
                    "input_encoding": "unicode",
                    "output_encoding": "unicode",
                    "report_level": 5,
                },
            )
        # elapsed += pyperf.perf_counter() - t0


def bench_docutils(loops, doc_root):
    for _ in range(loops):
        build_html(doc_root)


if __name__ == "__main__":
    # runner = pyperf.Runner()

    # runner.metadata["description"] = "Render documentation with Docutils"
    # args = runner.parse_args()

    # runner.bench_time_func("docutils", bench_docutils, DOC_ROOT)
    start = perf_counter_ns()
    bench_docutils(1, DOC_ROOT)
    end = perf_counter_ns()
    with open("bench_time.txt", "w") as f:
        f.write(str(end - start))