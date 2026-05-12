import ast


def copy_declared_imports(module_mapping: dict | None, versions: list[int]) -> list[ast.AST]:
    """modules.jsonのimports宣言をASTノードへ変換する。"""
    imports_by_version = (module_mapping or {}).get("imports", {})
    if imports_by_version is None:
        imports_by_version = {}
    if not isinstance(imports_by_version, dict):
        raise ValueError("Module imports must be an object")

    imports: list[ast.AST] = []
    for version in versions:
        raw_imports = imports_by_version.get(str(version), [])
        if not isinstance(raw_imports, list) or not all(isinstance(item, str) for item in raw_imports):
            raise ValueError(f"Module imports for v{version} must be a list of strings")
        for import_source in raw_imports:
            imports.append(parse_import_spec(import_source, version))
    return imports


def parse_import_spec(import_source: str, version: int) -> ast.AST:
    """1行のimport宣言文字列をImport/ImportFrom ASTへ変換する。"""
    try:
        tree = ast.parse(import_source)
    except SyntaxError as e:
        raise ValueError(f"Invalid import spec for v{version}: {import_source}") from e

    if len(tree.body) != 1 or not isinstance(tree.body[0], (ast.Import, ast.ImportFrom)):
        raise ValueError(f"Import spec for v{version} must contain exactly one import statement: {import_source}")
    return tree.body[0]


def dedupe_imports(import_nodes: list[ast.AST]) -> list[ast.AST]:
    """同じimport文が複数経路から来ても、生成結果には1つだけ残す。"""
    imports: dict[str, ast.AST] = {}
    for import_node in import_nodes:
        imports.setdefault(ast.unparse(import_node), import_node)
    return list(imports.values())
