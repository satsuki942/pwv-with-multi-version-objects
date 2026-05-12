import ast
import json
from pathlib import Path

import pytest

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
        "assign:VALUE",
        "function:alpha",
        "class:Box",
    ]

    function_node = generated.body[1]
    assert isinstance(function_node, ast.FunctionDef)
    assert [arg.arg for arg in function_node.args.args] == ["x", "y"]
    assert isinstance(function_node.body[0], ast.Raise)

    class_node = generated.body[2]
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


def test_schema_v2_uses_declared_imports_only(tmp_path: Path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "compiled"
    _write_schema_v2_case(
        input_dir,
        module_path="sample",
        versions=[1, 2],
        imports={
            "1": ["import math", "import math"],
            "2": ["from decimal import Decimal"],
        },
        sources={
            1: """
import os

def alpha():
    return os.name
""",
            2: """
import sys

def alpha():
    return sys.platform
""",
        },
    )

    compile(input_dir, output_dir)

    generated = ast.parse((output_dir / "sample.py").read_text(encoding="utf-8"))
    assert [_node_summary(node) for node in generated.body] == [
        "import:import math",
        "import:from decimal import Decimal",
        "function:alpha",
    ]


def test_schema_v2_function_fixed_realization_calls_hidden_impl(tmp_path: Path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "compiled"
    _write_schema_v2_case(
        input_dir,
        module_path="sample",
        versions=[1, 2],
        compatibility=_function_compatibility(
            entity="alpha",
            source_name="alpha",
            fixed_meaning="alpha@v2",
            implementation_version=2,
        ),
        sources={
            1: """
def alpha(value):
    return value + 1
""",
            2: """
def alpha(value):
    return value * 2
""",
        },
    )

    compile(input_dir, output_dir)

    generated_source = (output_dir / "sample.py").read_text(encoding="utf-8")
    generated = ast.parse(generated_source)
    assert [_node_summary(node) for node in generated.body] == [
        "function:_v1_alpha",
        "function:_v2_alpha",
        "function:alpha",
    ]

    wrapper = generated.body[2]
    assert isinstance(wrapper, ast.FunctionDef)
    assert wrapper.args.vararg and wrapper.args.vararg.arg == "args"
    assert wrapper.args.kwarg and wrapper.args.kwarg.arg == "kwargs"
    docstring = ast.get_docstring(wrapper)
    assert docstring is not None
    assert "内部識別子" not in docstring
    assert "呼び出し解釈:" in docstring
    assert "- fixed: alpha@v2" in docstring
    assert "実行候補:" in docstring
    assert "- alpha@v2: call v2.alpha -> _v2_alpha" in docstring
    assert "前提条件: なし" in docstring
    assert "事前調整: なし" in docstring

    namespace: dict[str, object] = {}
    exec(generated_source, namespace)
    assert namespace["alpha"](3) == 6
    assert namespace["_v1_alpha"](3) == 4
    assert namespace["_v2_alpha"](3) == 6


def test_schema_v2_function_rejects_different_source_names(tmp_path: Path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "compiled"
    compatibility = _function_compatibility(
        entity="alpha",
        source_name="alpha",
        fixed_meaning="alpha@v1",
        implementation_version=1,
    )
    compatibility["functions"][0]["sources"]["2"]["name"] = "beta"
    _write_schema_v2_case(
        input_dir,
        module_path="sample",
        versions=[1, 2],
        compatibility=compatibility,
        sources={
            1: """
def alpha():
    return "v1"
""",
            2: """
def beta():
    return "v2"
""",
        },
    )

    with pytest.raises(ValueError, match="same source name"):
        compile(input_dir, output_dir)


@pytest.mark.parametrize(
    ("realization_patch", "match"),
    [
        ({"preconditions": [{"kind": "field_exists", "field": "state"}]}, "preconditions is not supported"),
        ({"pre_adjustments": [{"kind": "sync_state"}]}, "pre_adjustments is not supported"),
        ({"implementation": {"kind": "call_sequence", "version": 1, "name": "alpha"}}, "call_sequence"),
    ],
)
def test_schema_v2_function_rejects_unsupported_realization_features(
    tmp_path: Path,
    realization_patch: dict,
    match: str,
):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "compiled"
    compatibility = _function_compatibility(
        entity="alpha",
        source_name="alpha",
        fixed_meaning="alpha@v1",
        implementation_version=1,
    )
    compatibility["functions"][0]["realizations"][0].update(realization_patch)
    _write_schema_v2_case(
        input_dir,
        module_path="sample",
        versions=[1, 2],
        compatibility=compatibility,
        sources={
            1: """
def alpha():
    return "v1"
""",
            2: """
def alpha():
    return "v2"
""",
        },
    )

    with pytest.raises(ValueError, match=match):
        compile(input_dir, output_dir)


def _write_schema_v2_case(
    input_dir: Path,
    *,
    module_path: str,
    versions: list[int],
    sources: dict[int, str],
    compatibility: dict | None = None,
    imports: dict[str, list[str]] | None = None,
) -> None:
    """schema_version 2 の最小プロジェクト構造を tmp_path 配下に作る。"""
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)
    module_spec = {
        "module_path": module_path,
        "versions": versions,
        "compatibility": compatibility if compatibility is not None else {
            "operations": []
        },
    }
    if imports is not None:
        module_spec["imports"] = imports

    modules_json = {
        "schema_version": 2,
        "modules": {
            module_path: module_spec
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


def _function_compatibility(
    *,
    entity: str,
    source_name: str,
    fixed_meaning: str,
    implementation_version: int,
) -> dict:
    """初期対応の論理関数仕様を作る。"""
    return {
        "functions": [
            {
                "entity": entity,
                "sources": {
                    "1": {"name": source_name},
                    "2": {"name": source_name},
                },
                "meanings": [
                    {"id": f"{entity}@v1"},
                    {"id": f"{entity}@v2"},
                ],
                "meaning_resolution": {
                    "mode": "fixed",
                    "meaning": fixed_meaning,
                },
                "realizations": [
                    {
                        "meaning": fixed_meaning,
                        "implementation": {
                            "kind": "call",
                            "version": implementation_version,
                            "name": source_name,
                        },
                        "preconditions": [],
                        "pre_adjustments": [],
                    }
                ],
            }
        ]
    }


def _node_summary(node: ast.AST) -> str:
    """生成ASTのトップレベル要素を、順序検証しやすい文字列にする。"""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return f"import:{ast.unparse(node)}"
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        return f"assign:{node.targets[0].id}"
    if isinstance(node, ast.FunctionDef):
        return f"function:{node.name}"
    if isinstance(node, ast.ClassDef):
        return f"class:{node.name}"
    return type(node).__name__
