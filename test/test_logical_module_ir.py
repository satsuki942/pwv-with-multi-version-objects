import ast
import json
from pathlib import Path

from mv_compiler.api import compile


def test_schema_v2_generates_skeleton_in_base_version_order(tmp_path: Path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "compiled"
    _write_schema_v2_case(
        input_dir,
        module_path="sample",
        versions=[1, 2],
        sources={
            1: """
import math
VALUE = 1

def alpha(x, y=1):
    return x + y

class Box:
    def value(self):
        return 1

print("not part of the skeleton")
""",
            2: """
import decimal
VALUE = 2

def alpha(x, y=2):
    return x * y

class Box:
    def value(self):
        return 2
""",
        },
    )

    compile(input_dir, output_dir)

    generated = ast.parse((output_dir / "sample.py").read_text(encoding="utf-8"))
    assert [_node_summary(node) for node in generated.body] == [
        "import",
        "assign:VALUE",
        "function:alpha",
        "class:Box",
    ]

    function_node = generated.body[2]
    assert isinstance(function_node, ast.FunctionDef)
    assert [arg.arg for arg in function_node.args.args] == ["x", "y"]
    assert isinstance(function_node.body[0], ast.Raise)

    class_node = generated.body[3]
    assert isinstance(class_node, ast.ClassDef)
    assert len(class_node.body) == 1
    assert isinstance(class_node.body[0], ast.Pass)


def test_schema_v2_uses_minimum_version_as_base_when_v1_is_absent(tmp_path: Path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "compiled"
    _write_schema_v2_case(
        input_dir,
        module_path="sample",
        versions=[2, 3],
        sources={
            2: """
def beta():
    return "v2"
""",
            3: """
def gamma():
    return "v3"
""",
        },
    )

    compile(input_dir, output_dir)

    generated = ast.parse((output_dir / "sample.py").read_text(encoding="utf-8"))
    assert [_node_summary(node) for node in generated.body] == ["function:beta"]


def _write_schema_v2_case(
    input_dir: Path,
    *,
    module_path: str,
    versions: list[int],
    sources: dict[int, str],
) -> None:
    """schema_version 2 の最小プロジェクト構造を tmp_path 配下に作る。"""
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)
    modules_json = {
        "schema_version": 2,
        "modules": {
            module_path: {
                "module_path": module_path,
                "versions": versions,
                "compatibility": {
                    "operations": []
                },
            }
        },
    }
    (mapping_dir / "modules.json").write_text(
        json.dumps(modules_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for version, source in sources.items():
        (input_dir / f"{module_path}__{version}__.py").write_text(
            source.strip() + "\n",
            encoding="utf-8",
        )


def _node_summary(node: ast.AST) -> str:
    """生成ASTのトップレベル要素を、順序検証しやすい文字列にする。"""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return "import"
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        return f"assign:{node.targets[0].id}"
    if isinstance(node, ast.FunctionDef):
        return f"function:{node.name}"
    if isinstance(node, ast.ClassDef):
        return f"class:{node.name}"
    return type(node).__name__
