import pytest

from mv_compiler.api import compile, execute


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

    assert execute("main.py", output_dir).strip().splitlines() == ["v2", "new"]


def test_mapping_rejects_name_changes(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("class Point:\n    pass\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("class RenamedPoint:\n    pass\n", encoding="utf-8")
    (mapping_dir / "modules.json").write_text(
        '{"modules": {"sample": {"exports": {"Point": {"kind": "class", "versions": {"1": "Point", "2": "RenamedPoint"}}}}}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Only same-name export mappings"):
        compile(input_dir, output_dir)


def test_mapping_rejects_kind_mismatches(tmp_path):
    input_dir = tmp_path / "sources"
    output_dir = tmp_path / "out"
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True)

    (input_dir / "sample__1__.py").write_text("class Point:\n    pass\n", encoding="utf-8")
    (input_dir / "sample__2__.py").write_text("def Point():\n    return None\n", encoding="utf-8")
    (mapping_dir / "modules.json").write_text(
        '{"modules": {"sample": {"exports": {"Point": {"kind": "class"}}}}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing or mismatched"):
        compile(input_dir, output_dir)
