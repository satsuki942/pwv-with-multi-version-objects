import json

import pytest

from mv_compiler.api import compile, execute


def write_evolution(mapping_dir, entities, imports=None, versions=None):
    mapping_dir.mkdir(parents=True, exist_ok=True)
    spec = {
        "modules": {
            "sample": {
                "versions": versions or [1, 2],
                "imports": imports or {},
                "entities": entities,
            }
        }
    }
    (mapping_dir / "evolution.json").write_text(json.dumps(spec), encoding="utf-8")


def test_unmapped_versioned_module_exports_latest_definitions(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    (input_dir / "sample__1__.py").write_text(
        "class Point:\n"
        "    def label(self):\n"
        "        return 'v1'\n"
        "\n"
        "def helper():\n"
        "    return 'old'\n",
        encoding="utf-8",
    )
    (input_dir / "sample__2__.py").write_text(
        "class Point:\n"
        "    def label(self):\n"
        "        return 'v2'\n"
        "\n"
        "def helper():\n"
        "    return 'new'\n",
        encoding="utf-8",
    )
    (input_dir / "main.py").write_text(
        "from sample import Point, helper\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(Point().label())\n"
        "    print(helper())\n",
        encoding="utf-8",
    )

    compile(input_dir, output_dir)

    assert execute("main.py", output_dir).strip().splitlines() == ["v1", "old"]


def test_evolution_accepts_name_changes(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("class Point:\n    pass\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("class RenamedPoint:\n    pass\n", encoding="utf-8")
    write_evolution(mapping_dir, {
        "point": {
            "state": {"sync": "none"},
            "versions": {
                "1": {"kind": "class", "name": "Point"},
                "2": {"kind": "class", "name": "RenamedPoint"},
            },
        }
    })

    compile(input_dir, output_dir)
    generated = (output_dir / "sample.py").read_text(encoding="utf-8")
    assert "class Point" in generated
    assert "class RenamedPoint" in generated


def test_mapping_rejects_kind_mismatches(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("class Point:\n    pass\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("def Point():\n    return None\n", encoding="utf-8")
    write_evolution(mapping_dir, {
        "point": {
            "versions": {
                "1": {"kind": "class", "name": "Point"},
                "2": {"kind": "class", "name": "Point"},
            }
        }
    })

    with pytest.raises(ValueError, match="missing or mismatched"):
        compile(input_dir, output_dir)


def test_declared_imports_are_unioned_by_version(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("class Point:\n    pass\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("class Point:\n    pass\n", encoding="utf-8")
    write_evolution(
        mapping_dir,
        {"point": {"versions": {"1": {"kind": "class", "name": "Point"}, "2": {"kind": "class", "name": "Point"}}}},
        imports={"1": ["import os", "from math import sqrt"], "2": ["import os", "from decimal import Decimal as D"]},
    )

    compile(input_dir, output_dir)

    generated = (output_dir / "sample.py").read_text(encoding="utf-8")
    assert generated.index("import os") < generated.index("from math import sqrt")
    assert generated.index("from math import sqrt") < generated.index("from decimal import Decimal as D")
    assert generated.count("import os") == 1


def test_source_imports_are_ignored_when_not_declared(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("import os\n\nclass Point:\n    pass\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("import sys\n\nclass Point:\n    pass\n", encoding="utf-8")
    write_evolution(
        mapping_dir,
        {"point": {"versions": {"1": {"kind": "class", "name": "Point"}, "2": {"kind": "class", "name": "Point"}}}},
        imports={"1": ["from math import sqrt"], "2": []},
    )

    compile(input_dir, output_dir)

    generated = (output_dir / "sample.py").read_text(encoding="utf-8")
    assert "from math import sqrt" in generated
    assert "import os" not in generated
    assert "import sys" not in generated


def test_missing_imports_are_treated_as_empty(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("import os\n\nclass Point:\n    pass\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("import sys\n\nclass Point:\n    pass\n", encoding="utf-8")
    write_evolution(
        mapping_dir,
        {"point": {"versions": {"1": {"kind": "class", "name": "Point"}, "2": {"kind": "class", "name": "Point"}}}},
    )

    compile(input_dir, output_dir)

    generated = (output_dir / "sample.py").read_text(encoding="utf-8")
    assert "import os" not in generated
    assert "import sys" not in generated


@pytest.mark.parametrize("import_spec", ["x = 1", "import os\nimport sys"])
def test_mapping_rejects_invalid_import_specs(tmp_path, import_spec):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("class Point:\n    pass\n", encoding="utf-8")
    write_evolution(
        mapping_dir,
        {"point": {"versions": {"1": {"kind": "class", "name": "Point"}}}},
        imports={"1": [import_spec]},
        versions=[1],
    )

    with pytest.raises(ValueError, match="Import spec"):
        compile(input_dir, output_dir)


def test_function_dispatch_uses_callable_version_for_three_versions(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("def choose(x):\n    return f'v1:{x}'\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("def choose(x, y):\n    return f'v2:{x},{y}'\n", encoding="utf-8")
    (input_dir / "sample__3__.py").write_text("def choose(x, y, z=0):\n    return f'v3:{x},{y},{z}'\n", encoding="utf-8")
    (input_dir / "main.py").write_text(
        "from sample import choose\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(choose(1))\n"
        "    print(choose(1, 2))\n"
        "    print(choose(1, 2, 3))\n"
        "    print(choose(4, 5))\n",
        encoding="utf-8",
    )
    write_evolution(
        mapping_dir,
        {"choose": {"versions": {
            "1": {"kind": "function", "name": "choose"},
            "2": {"kind": "function", "name": "choose"},
            "3": {"kind": "function", "name": "choose"},
        }}},
        versions=[1, 2, 3],
    )

    compile(input_dir, output_dir)

    assert execute("main.py", output_dir).strip().splitlines() == [
        "v1:1",
        "v3:1,2,0",
        "v3:1,2,3",
        "v3:4,5,0",
    ]


def test_function_current_version_is_stored_per_export(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text(
        "def left(x):\n"
        "    return f'left-v1:{x}'\n"
        "\n"
        "def right(x):\n"
        "    return f'right-v1:{x}'\n",
        encoding="utf-8",
    )
    (input_dir / "sample__2__.py").write_text(
        "def left(x, y):\n"
        "    return f'left-v2:{x},{y}'\n"
        "\n"
        "def right(x, y):\n"
        "    return f'right-v2:{x},{y}'\n",
        encoding="utf-8",
    )
    (input_dir / "main.py").write_text(
        "from sample import left, right\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(left._mvo_current_version, right._mvo_current_version)\n"
        "    print(left(1, 2))\n"
        "    print(left._mvo_current_version, right._mvo_current_version)\n"
        "    print(right(3))\n"
        "    print(left._mvo_current_version, right._mvo_current_version)\n",
        encoding="utf-8",
    )
    write_evolution(mapping_dir, {
        "left": {"versions": {"1": {"kind": "function", "name": "left"}, "2": {"kind": "function", "name": "left"}}},
        "right": {"versions": {"1": {"kind": "function", "name": "right"}, "2": {"kind": "function", "name": "right"}}},
    })

    compile(input_dir, output_dir)

    assert execute("main.py", output_dir).strip().splitlines() == [
        "1 1",
        "left-v2:1,2",
        "2 1",
        "right-v1:3",
        "2 1",
    ]


def test_public_name_can_refer_to_different_entities_by_version(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("x = 'position-v1'\nz = 'count-v1'\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("x = 'count-v2'\ny = 'position-v2'\n", encoding="utf-8")
    (input_dir / "main.py").write_text(
        "from sample import x, y, z\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(x.get())\n"
        "    print(y.get())\n"
        "    print(z.get())\n",
        encoding="utf-8",
    )
    write_evolution(mapping_dir, {
        "position": {
            "state": {"sync": "required"},
            "versions": {
                "1": {"kind": "variable", "name": "x"},
                "2": {"kind": "variable", "name": "y"},
            },
        },
        "count": {
            "state": {"sync": "required"},
            "versions": {
                "1": {"kind": "variable", "name": "z"},
                "2": {"kind": "variable", "name": "x"},
            },
        },
    })

    compile(input_dir, output_dir)

    assert execute("main.py", output_dir).strip().splitlines() == [
        "position-v1",
        "position-v1",
        "count-v1",
    ]


def test_kind_change_entity_uses_access_facade(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("x = 10\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("def y(n):\n    return n * 2\n", encoding="utf-8")
    (input_dir / "main.py").write_text(
        "from sample import x, y\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(x.get())\n"
        "    print(y(5))\n",
        encoding="utf-8",
    )
    write_evolution(mapping_dir, {
        "position": {
            "state": {"sync": "required"},
            "versions": {
                "1": {"kind": "variable", "name": "x"},
                "2": {"kind": "function", "name": "y"},
            },
        },
    })

    compile(input_dir, output_dir)

    assert execute("main.py", output_dir).strip().splitlines() == ["10", "10"]


def test_function_dispatch_uses_python_signature_binding(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("def choose(x, /):\n    return f'pos:{x}'\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("def choose(*items):\n    return f'var:{len(items)}'\n", encoding="utf-8")
    (input_dir / "sample__3__.py").write_text("def choose(x, *, mode):\n    return f'kwonly:{x}:{mode}'\n", encoding="utf-8")
    (input_dir / "sample__4__.py").write_text("def choose(**kwargs):\n    return f'kwargs:{sorted(kwargs)}'\n", encoding="utf-8")
    (input_dir / "main.py").write_text(
        "from sample import choose\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(choose(1))\n"
        "    print(choose(x=2, mode='m'))\n"
        "    print(choose())\n"
        "    print(choose(1, 2, 3))\n"
        "    print(choose(extra=5))\n"
        "    try:\n"
        "        choose(1, x=2)\n"
        "    except TypeError as e:\n"
        "        print(type(e).__name__, str(e))\n",
        encoding="utf-8",
    )
    write_evolution(
        mapping_dir,
        {"choose": {"versions": {
            "1": {"kind": "function", "name": "choose"},
            "2": {"kind": "function", "name": "choose"},
            "3": {"kind": "function", "name": "choose"},
            "4": {"kind": "function", "name": "choose"},
        }}},
        versions=[1, 2, 3, 4],
    )

    compile(input_dir, output_dir)

    assert execute("main.py", output_dir).strip().splitlines() == [
        "pos:1",
        "kwargs:['mode', 'x']",
        "kwargs:[]",
        "var:3",
        "kwargs:['extra']",
        "TypeError No version of 'choose' matches the provided arguments.",
    ]


def test_method_dispatch_uses_python_signature_binding(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text(
        "class Runner:\n"
        "    def call(self, x, /):\n"
        "        return f'pos:{x}'\n",
        encoding="utf-8",
    )
    (input_dir / "sample__2__.py").write_text(
        "class Runner:\n"
        "    def call(self, *items):\n"
        "        return f'var:{len(items)}'\n",
        encoding="utf-8",
    )
    (input_dir / "sample__3__.py").write_text(
        "class Runner:\n"
        "    def call(self, x, *, mode):\n"
        "        return f'kwonly:{x}:{mode}'\n",
        encoding="utf-8",
    )
    (input_dir / "sample__4__.py").write_text(
        "class Runner:\n"
        "    def call(self, **kwargs):\n"
        "        return f'kwargs:{sorted(kwargs)}'\n",
        encoding="utf-8",
    )
    (input_dir / "main.py").write_text(
        "from sample import Runner\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    runner = Runner()\n"
        "    print(runner.call(1))\n"
        "    print(runner.call(x=2, mode='m'))\n"
        "    print(runner.call())\n"
        "    print(runner.call(1, 2, 3))\n"
        "    print(runner.call(extra=5))\n"
        "    try:\n"
        "        runner.call(1, x=2)\n"
        "    except TypeError as e:\n"
        "        print(type(e).__name__, str(e))\n",
        encoding="utf-8",
    )
    write_evolution(
        mapping_dir,
        {"runner": {"versions": {
            "1": {"kind": "class", "name": "Runner"},
            "2": {"kind": "class", "name": "Runner"},
            "3": {"kind": "class", "name": "Runner"},
            "4": {"kind": "class", "name": "Runner"},
        }}},
        versions=[1, 2, 3, 4],
    )

    compile(input_dir, output_dir)

    assert execute("main.py", output_dir).strip().splitlines() == [
        "pos:1",
        "kwargs:['mode', 'x']",
        "kwargs:[]",
        "var:3",
        "kwargs:['extra']",
        "TypeError No version of 'call' matches the provided arguments.",
    ]


def test_consistent_positional_only_method_signature_compiles(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text(
        "class Runner:\n"
        "    def call(self, x, /):\n"
        "        return f'v1:{x}'\n",
        encoding="utf-8",
    )
    (input_dir / "sample__2__.py").write_text(
        "class Runner:\n"
        "    def call(self, x, /):\n"
        "        return f'v2:{x}'\n",
        encoding="utf-8",
    )
    (input_dir / "main.py").write_text(
        "from sample import Runner\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    runner = Runner()\n"
        "    print(runner.call(1))\n"
        "    try:\n"
        "        runner.call(x=1)\n"
        "    except TypeError as e:\n"
        "        print(type(e).__name__)\n",
        encoding="utf-8",
    )
    write_evolution(mapping_dir, {"runner": {"versions": {"1": {"kind": "class", "name": "Runner"}, "2": {"kind": "class", "name": "Runner"}}}})

    compile(input_dir, output_dir)

    assert execute("main.py", output_dir).strip().splitlines() == [
        "v1:1",
        "TypeError",
    ]


def test_versioned_values_resolve_from_their_own_strategy(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("LEFT = 10\nRIGHT = 100\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("LEFT = 20\nRIGHT = 200\n", encoding="utf-8")
    (input_dir / "main.py").write_text(
        "from sample import LEFT, RIGHT\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(LEFT.get(), RIGHT.get())\n"
        "    LEFT.set(15)\n"
        "    print(LEFT.get(), RIGHT.get())\n",
        encoding="utf-8",
    )
    write_evolution(mapping_dir, {
        "left": {"versions": {"1": {"kind": "variable", "name": "LEFT"}, "2": {"kind": "variable", "name": "LEFT"}}},
        "right": {"versions": {"1": {"kind": "variable", "name": "RIGHT"}, "2": {"kind": "variable", "name": "RIGHT"}}},
    })

    compile(input_dir, output_dir)

    generated = (output_dir / "sample.py").read_text(encoding="utf-8")
    assert "_MVO_CURRENT_VERSION" not in generated
    assert execute("main.py", output_dir).strip().splitlines() == [
        "10 100",
        "15 100",
    ]


def test_versioned_value_latest_strategy_initializes_to_latest_value(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("VALUE = 10\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("VALUE = 20\n", encoding="utf-8")
    (input_dir / "main.py").write_text(
        "from sample import VALUE\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(VALUE.get())\n",
        encoding="utf-8",
    )
    write_evolution(mapping_dir, {"value": {"versions": {"1": {"kind": "variable", "name": "VALUE"}, "2": {"kind": "variable", "name": "VALUE"}}}})

    compile(input_dir, output_dir, version_selection_strategy="latest")

    assert execute("main.py", output_dir).strip().splitlines() == ["20"]
