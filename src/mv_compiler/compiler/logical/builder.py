import ast
from pathlib import Path
from typing import Any

from ..common.imports import copy_declared_imports, dedupe_imports
from .ir import (
    FunctionImplementationIR,
    FunctionMeaningIR,
    FunctionMeaningResolutionIR,
    FunctionRealizationIR,
    FunctionSourceIR,
    LogicalFunctionIR,
    LogicalModuleIR,
    LogicalObjectIR,
    LogicalObjectKind,
)


def build_logical_module_ir(
    logical_rel_path: Path,
    versioned_trees: dict[int, ast.AST],
    module_mapping: dict[str, Any],
) -> LogicalModuleIR:
    """
    schema_version 2 の入力から LogicalModuleIR を構築する。

    import は modules.json の宣言だけを信用する。公開要素については base version の
    トップレベル順序を論理モジュールの公開順序として採用し、各要素に対応する他版の
    ASTノードと互換仕様を紐付ける。
    """
    # 利用可能な版を確定し、論理モジュールの基準にする版を選ぶ。
    versions = sorted(versioned_trees)
    if not versions:
        raise ValueError(f"Logical module has no versions: {logical_rel_path.as_posix()}")

    base_version = 1 if 1 in versions else versions[0]
    base_tree = versioned_trees[base_version]

    # 各版のトップレベル定義を名前で引けるようにして、base側の要素へ束ねる。
    top_level_by_version = {
        version: _collect_top_level_defs(tree)
        for version, tree in versioned_trees.items()
    }
    compatibility = _get_compatibility(module_mapping)
    compatibility_by_name = _index_compatibility_operations(compatibility)
    function_irs_by_name = _build_logical_function_irs(compatibility, top_level_by_version, versions)
    import_nodes = dedupe_imports(copy_declared_imports(module_mapping, versions))

    # base version のトップレベル順序を維持して LogicalObjectIR を作る。
    objects: list[LogicalObjectIR] = []
    for order_index, node in enumerate(base_tree.body):
        kind = _logical_object_kind(node)
        if kind == LogicalObjectKind.IMPORT:
            continue
        public_name = _top_level_name(node)
        version_nodes = _collect_version_nodes(public_name, top_level_by_version, versions)
        function_ir = function_irs_by_name.get(public_name) if public_name else None
        objects.append(LogicalObjectIR(
            kind=kind,
            order_index=order_index,
            public_name=public_name,
            base_version_node=node,
            version_nodes=version_nodes,
            compatibility_spec=compatibility_by_name.get(public_name) if public_name else None,
            function_ir=function_ir,
        ))

    module_path = module_mapping["module_path"]
    return LogicalModuleIR(
        module_key=module_mapping.get("module_key", module_path),
        module_path=module_path,
        logical_rel_path=logical_rel_path,
        versions=versions,
        base_version=base_version,
        import_nodes=import_nodes,
        objects=objects,
    )


def _get_compatibility(module_mapping: dict[str, Any]) -> dict[str, Any]:
    """module mappingからcompatibilityオブジェクトを取り出して検証する。"""
    # schema v2 の compatibility はまだ拡張中なので、最小限の形だけ検証する。
    compatibility = module_mapping.get("compatibility", {})
    if compatibility is None:
        compatibility = {}
    if not isinstance(compatibility, dict):
        raise ValueError("Module compatibility must be an object")
    return compatibility


def _index_compatibility_operations(compatibility: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """互換仕様の operation を、論理操作名から引ける辞書に変換する。"""
    operations = compatibility.get("operations", [])
    if operations is None:
        operations = []
    if not isinstance(operations, list):
        raise ValueError("Module compatibility.operations must be an array")

    indexed: dict[str, dict[str, Any]] = {}
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("Module compatibility.operations items must be objects")
        # 名前フィールドの候補は、仕様の揺れを吸収するため当面は複数受ける。
        name = operation.get("name") or operation.get("public_name") or operation.get("logical_operation")
        if isinstance(name, str) and name:
            indexed[name] = operation
    return indexed


def _build_logical_function_irs(
    compatibility: dict[str, Any],
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
) -> dict[str, LogicalFunctionIR]:
    """compatibility.functionsを検証し、公開名からLogicalFunctionIRを引ける形にする。"""
    raw_functions = compatibility.get("functions", [])
    if raw_functions is None:
        raw_functions = []
    if not isinstance(raw_functions, list):
        raise ValueError("Module compatibility.functions must be an array")

    by_public_name: dict[str, LogicalFunctionIR] = {}
    used_entities: set[str] = set()
    for raw_function in raw_functions:
        if not isinstance(raw_function, dict):
            raise ValueError("Module compatibility.functions items must be objects")

        entity = _required_str(raw_function, "entity", "logical function")
        if entity in used_entities:
            raise ValueError(f"Duplicate logical function entity: {entity}")
        used_entities.add(entity)

        sources = _parse_function_sources(raw_function, top_level_by_version, versions, entity)
        public_name = _public_name_from_sources(sources, entity)
        if public_name in by_public_name:
            raise ValueError(f"Duplicate logical function public name: {public_name}")

        meanings = _parse_function_meanings(raw_function, entity)
        meaning_resolution = _parse_function_meaning_resolution(raw_function, meanings, entity)
        realizations = _parse_function_realizations(raw_function, meanings, sources, versions, entity)
        if not any(realization.meaning == meaning_resolution.meaning for realization in realizations):
            raise ValueError(
                f"Logical function {entity} has no realization for fixed meaning: {meaning_resolution.meaning}"
            )

        by_public_name[public_name] = LogicalFunctionIR(
            entity=entity,
            public_name=public_name,
            sources=sources,
            meanings=meanings,
            meaning_resolution=meaning_resolution,
            realizations=realizations,
        )
    return by_public_name


def _parse_function_sources(
    raw_function: dict[str, Any],
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
    entity: str,
) -> dict[int, FunctionSourceIR]:
    """論理関数仕様のsourcesを、版ごとの元関数ASTへ解決する。"""
    raw_sources = raw_function.get("sources")
    if not isinstance(raw_sources, dict):
        raise ValueError(f"Logical function {entity} sources must be an object")

    sources: dict[int, FunctionSourceIR] = {}
    for version in versions:
        raw_source = raw_sources.get(str(version))
        if not isinstance(raw_source, dict):
            raise ValueError(f"Logical function {entity} source for v{version} must be an object")
        source_name = _required_str(raw_source, "name", f"logical function {entity} source v{version}")
        node = top_level_by_version[version].get(source_name)
        if not isinstance(node, ast.FunctionDef):
            raise ValueError(f"Logical function {entity} source v{version}.{source_name} is missing or not a function")
        sources[version] = FunctionSourceIR(version=version, name=source_name, node=node)
    return sources


def _public_name_from_sources(sources: dict[int, FunctionSourceIR], entity: str) -> str:
    """初期実装で公開名にできるsource名を決定する。"""
    source_names = {source.name for source in sources.values()}
    if len(source_names) != 1:
        raise ValueError(
            f"Logical function {entity} must use the same source name across versions in the initial implementation"
        )
    return next(iter(source_names))


def _parse_function_meanings(raw_function: dict[str, Any], entity: str) -> dict[str, FunctionMeaningIR]:
    """明示されたmeaning一覧を検証して辞書化する。"""
    raw_meanings = raw_function.get("meanings")
    if not isinstance(raw_meanings, list) or not raw_meanings:
        raise ValueError(f"Logical function {entity} meanings must be a non-empty array")

    meanings: dict[str, FunctionMeaningIR] = {}
    for raw_meaning in raw_meanings:
        if not isinstance(raw_meaning, dict):
            raise ValueError(f"Logical function {entity} meanings items must be objects")
        meaning_id = _required_str(raw_meaning, "id", f"logical function {entity} meaning")
        if meaning_id in meanings:
            raise ValueError(f"Duplicate logical function meaning: {meaning_id}")
        meanings[meaning_id] = FunctionMeaningIR(id=meaning_id)
    return meanings


def _parse_function_meaning_resolution(
    raw_function: dict[str, Any],
    meanings: dict[str, FunctionMeaningIR],
    entity: str,
) -> FunctionMeaningResolutionIR:
    """初期対応のfixed meaning resolutionを検証する。"""
    raw_resolution = raw_function.get("meaning_resolution")
    if not isinstance(raw_resolution, dict):
        raise ValueError(f"Logical function {entity} meaning_resolution must be an object")
    mode = _required_str(raw_resolution, "mode", f"logical function {entity} meaning_resolution")
    if mode != "fixed":
        raise ValueError(f"Logical function {entity} meaning_resolution mode is not supported: {mode}")
    meaning = _required_str(raw_resolution, "meaning", f"logical function {entity} meaning_resolution")
    if meaning not in meanings:
        raise ValueError(f"Logical function {entity} fixed meaning is not declared: {meaning}")
    return FunctionMeaningResolutionIR(mode=mode, meaning=meaning)


def _parse_function_realizations(
    raw_function: dict[str, Any],
    meanings: dict[str, FunctionMeaningIR],
    sources: dict[int, FunctionSourceIR],
    versions: list[int],
    entity: str,
) -> list[FunctionRealizationIR]:
    """初期対応のcall realizationを検証する。"""
    raw_realizations = raw_function.get("realizations")
    if not isinstance(raw_realizations, list) or not raw_realizations:
        raise ValueError(f"Logical function {entity} realizations must be a non-empty array")

    realizations: list[FunctionRealizationIR] = []
    for raw_realization in raw_realizations:
        if not isinstance(raw_realization, dict):
            raise ValueError(f"Logical function {entity} realizations items must be objects")
        meaning = _required_str(raw_realization, "meaning", f"logical function {entity} realization")
        if meaning not in meanings:
            raise ValueError(f"Logical function {entity} realization references undeclared meaning: {meaning}")

        preconditions = _empty_list(raw_realization, "preconditions", f"logical function {entity} realization")
        pre_adjustments = _empty_list(raw_realization, "pre_adjustments", f"logical function {entity} realization")
        implementation = _parse_function_implementation(raw_realization, sources, versions, entity)
        realizations.append(FunctionRealizationIR(
            meaning=meaning,
            implementation=implementation,
            preconditions=preconditions,
            pre_adjustments=pre_adjustments,
        ))
    return realizations


def _parse_function_implementation(
    raw_realization: dict[str, Any],
    sources: dict[int, FunctionSourceIR],
    versions: list[int],
    entity: str,
) -> FunctionImplementationIR:
    """realizationのimplementationが初期対応のcall形式か検証する。"""
    raw_implementation = raw_realization.get("implementation")
    if not isinstance(raw_implementation, dict):
        raise ValueError(f"Logical function {entity} realization implementation must be an object")
    kind = _required_str(raw_implementation, "kind", f"logical function {entity} implementation")
    if kind != "call":
        raise ValueError(f"Logical function {entity} implementation kind is not supported: {kind}")

    version = raw_implementation.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version not in versions:
        raise ValueError(f"Logical function {entity} implementation version is not declared: {version}")
    name = _required_str(raw_implementation, "name", f"logical function {entity} implementation")
    if sources[version].name != name:
        raise ValueError(
            f"Logical function {entity} implementation v{version}.{name} must reference its declared source"
        )
    return FunctionImplementationIR(kind=kind, version=version, name=name)


def _required_str(data: dict[str, Any], field: str, context: str) -> str:
    """外部仕様の必須文字列フィールドを取り出す。"""
    value = data.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} {field} must be a non-empty string")
    return value


def _empty_list(data: dict[str, Any], field: str, context: str) -> list[Any]:
    """初期実装では空だけを許す配列フィールドを検証する。"""
    value = data.get(field, [])
    if not isinstance(value, list):
        raise ValueError(f"{context} {field} must be an array")
    if value:
        raise ValueError(f"{context} {field} is not supported yet")
    return value


def _collect_top_level_defs(tree: ast.AST) -> dict[str, ast.AST]:
    """ASTモジュールから名前を持つトップレベル要素だけを集める。"""
    defs: dict[str, ast.AST] = {}
    for node in tree.body:
        name = _top_level_name(node)
        if name is not None:
            defs[name] = node
    return defs


def _collect_version_nodes(
    public_name: str | None,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
) -> dict[int, ast.AST | None]:
    """論理要素名に対応する各版のASTノードを集める。"""
    if public_name is None:
        return {version: None for version in versions}
    return {
        version: top_level_by_version[version].get(public_name)
        for version in versions
    }


def _logical_object_kind(node: ast.AST) -> LogicalObjectKind:
    """トップレベルASTノードを LogicalObjectKind に分類する。"""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return LogicalObjectKind.IMPORT
    if isinstance(node, ast.ClassDef):
        return LogicalObjectKind.CLASS
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return LogicalObjectKind.FUNCTION
    if _is_variable_node(node):
        return LogicalObjectKind.VARIABLE
    return LogicalObjectKind.OTHER


def _is_variable_node(node: ast.AST) -> bool:
    """トップレベル変数として扱える代入ノードか判定する。"""
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return True
    if isinstance(node, ast.Assign):
        return any(isinstance(target, ast.Name) for target in node.targets)
    return False


def _top_level_name(node: ast.AST) -> str | None:
    """トップレベルASTノードから公開名を取り出す。"""
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                return target.id
    return None
