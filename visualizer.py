from __future__ import annotations

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.theme import 
from benchengine import CURRENT_PLATFORM, PLATFORM_EMOJI, Benchmark, centered_text, get_visualizer_setup

console = Console(record=True)


def build_table() -> Table:
    table = Table()
    table.add_column("Version")
    table.add_column("CPython")
    table.add_column("Nuitka")
    table.add_column(centered_text("Nuitka-Diff"))
    table.add_column(centered_text("Factory Diff"))

    return table

def build_group_table(benchmarks: list[Benchmark]) -> Table:
    table = build_table()

    for version in benchmarks:
        nuitka_stats = version.calculate_stats("nuitka")
        cpython_stats = version.calculate_stats("cpython")
        factory_stats = (
            version.factory.format_stats()
            if version.factory
            else centered_text("N/A")
        )
        table.add_row(
            centered_text(version.normalized_python_version),
            centered_text(f"{cpython_stats:.2f}"),
            centered_text(f"{nuitka_stats:.2f}"),
            version.format_stats(),
            factory_stats,
        )
    return table

to_visualize = []
to_visualize.append(Panel(centered_text(f"{PLATFORM_EMOJI} {CURRENT_PLATFORM} {PLATFORM_EMOJI}")))

for name, benchmarks in get_visualizer_setup():
    table = build_group_table(benchmarks)
    to_visualize.append(Panel(table, title=name))

console.print(Align.center(Panel(Group(*to_visualize))))
console.save_svg(f"results/{CURRENT_PLATFORM}_benchmarks.svg")
