import ast
from pathlib import Path

mapping = {
    "bm_pyflate": {str: "data/interpreter.tar.bz2"},
    "bm_bpe_tokeniser": {},
    "bm_html5lib": {},
    "bm_dulwich_log": {},
    "bm_tomli_loads": {},
    "bm_telco": {},
}


class BaseReplacementVisitor(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self.parent_stack = []

    def visit(self, node):
        self.parent_stack.append(node)
        super().visit(node)
        self.parent_stack.pop()

    def replace_child(self, parent, old_node, new_node):
        for field, value in ast.iter_fields(parent):
            if isinstance(value, list):
                try:
                    idx = value.index(old_node)
                    value[idx] = new_node
                    return
                except ValueError:
                    pass
            elif value == old_node:
                setattr(parent, field, new_node)
                return

    def generic_visit(self, node):
        for child in ast.iter_child_nodes(node):
            self.visit(child)


class FileParentReplacementVisitor(BaseReplacementVisitor):
    def visit_Attribute(self, node):
        if (
            node.attr == "parent"
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "Path"
            and len(node.value.args) == 1
            and isinstance(node.value.args[0], ast.Name)
            and node.value.args[0].id == "__file__"
        ):
            replacement_node = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="Path", ctx=ast.Load()),
                    attr="cwd",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
            )
            self.replace_child(self.parent_stack[-2], node, replacement_node)

        self.generic_visit(node)

    def visit_Call(self, node):
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Attribute)
            and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "os"
            and node.func.value.attr == "path"
            and node.func.attr == "dirname"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "__file__"
        ):
            replacement_node = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="os", ctx=ast.Load()),
                    attr="getcwd",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
            )
            self.replace_child(self.parent_stack[-2], node, replacement_node)

        self.generic_visit(node)


class ReplacementVisitor(BaseReplacementVisitor):
    def __init__(self, benchmark_path: Path, replacements):
        super().__init__()
        self.benchmark_path = benchmark_path
        self.replacements = replacements
        self.resolved_replacements = {
            k: str((self.benchmark_path / v).resolve()) for k, v in replacements.items()
        }

    def visit_Constant(self, node):
        for replacement_type, replacement_value in self.resolved_replacements.items():
            if (
                isinstance(node.value, replacement_type)
                and node.value == self.replacements[replacement_type]
            ):
                new_node = ast.Constant(value=replacement_value)
                parent = self.parent_stack[-2]
                self.replace_child(parent, node, new_node)
        self.generic_visit(node)

def prepare_benchmark_file(benchmark_path: Path):
    run_benchmark_path = benchmark_path / "run_benchmark.py"
    replacement = mapping.get(benchmark_path.name, None)

    if replacement is None:
        return

    with run_benchmark_path.open("r") as f:
        tree = ast.parse(f.read())

    visitors = [
        ReplacementVisitor(benchmark_path, replacement),
        FileParentReplacementVisitor(),
    ]
    for visitor in visitors:
        visitor.visit(tree)

    with run_benchmark_path.open("w") as f:
        ast.fix_missing_locations(tree)
        f.write(ast.unparse(tree))
