import ast
import copy
from pathlib import Path

from ..common.imports import copy_declared_imports, dedupe_imports
from ..common.util import logger
from ..common.util.constants import DEFAULT_VERSION_SELECTION_STRATEGY
from ..elements.class_.compiler import build_unified_classes_for_module
from ..elements.entity import entities_of_kind, entity_source_name, entity_source_node
from ..elements.function.compiler import build_function_entity
from ..elements.signature import build_signature_runtime_support
from ..elements.variable.compiler import (
    build_module_runtime,
    build_variable_entity,
)


def transform_versioned_module(
    logical_rel_path: Path,
    versioned_trees: dict[int, ast.AST],
    module_mapping: dict | None,
    sync_functions_dict: dict,
    incompatibilities: dict | None,
    version_selection_strategy: str = DEFAULT_VERSION_SELECTION_STRATEGY,
) -> tuple[Path, ast.AST | None]:
    """版付きモジュールASTを単一のPythonモジュールASTへ統合する。

    Args:
        logical_rel_path: 出力先でも使う論理モジュールの相対パス。
        versioned_trees: version番号をkeyにした、各版の入力AST。
        module_mapping: modules.jsonで宣言された当該モジュールの設定。
        sync_functions_dict: class entity_keyごとの状態同期関数定義。
        incompatibilities: class entity_keyごとの非互換メソッド設定。
        version_selection_strategy: 実行時にversionを選ぶ戦略名。

    Returns:
        論理モジュールの相対パスと、統合後のAST。入力versionが空ならASTはNone。
    """
    versions = sorted(versioned_trees)
    if not versions:
        logger.error_log(f"Versioned module has no versions: {logical_rel_path}")
        return logical_rel_path, None

    entity_mappings = (module_mapping or {}).get("entity_mappings", [])
    latest_version = versions[-1]
    latest_tree = versioned_trees[latest_version]
    top_level_by_version = {
        version: _collect_top_level_defs(tree)
        for version, tree in versioned_trees.items()
    }
    entities = _normalize_entity_mappings(entity_mappings, top_level_by_version, versions)

    new_body: list[ast.AST] = []
    import_nodes = copy_declared_imports(module_mapping, versions)
    import_nodes.extend(_copy_sync_imports(entities, sync_functions_dict))
    new_body.extend(dedupe_imports(import_nodes))

    class_entities = entities_of_kind(entities, "class")
    function_entities = entities_of_kind(entities, "function")
    variable_entities = entities_of_kind(entities, "variable")
    if class_entities or function_entities:
        new_body.extend(build_signature_runtime_support())
    has_generated_variable = any(
        spec.get("versioned_by") == "generated"
        for spec in variable_entities.values()
    )
    if has_generated_variable:
        new_body.extend(build_module_runtime(version_selection_strategy, latest_version))

    if class_entities:
        new_body.extend(build_unified_classes_for_module(
            class_entities,
            top_level_by_version,
            versions,
            sync_functions_dict,
            incompatibilities,
            version_selection_strategy,
        ))

    for entity_name, spec in entities.items():
        kind = spec.get("kind")
        if kind == "function":
            new_body.extend(build_function_entity(
                entity_name,
                spec,
                top_level_by_version,
                versions,
                version_selection_strategy,
            ))
        elif kind == "variable":
            variable_node = build_variable_entity(
                entity_name,
                spec,
                top_level_by_version,
                versions,
                latest_version,
                version_selection_strategy,
            )
            if variable_node:
                new_body.append(variable_node)

    new_body.extend(_build_alias_assignments(entities))
    new_body.extend(_copy_unmapped_latest_defs(latest_tree, _mapped_output_names(entities, latest_version)))

    new_module = ast.Module(body=new_body, type_ignores=[])
    ast.fix_missing_locations(new_module)
    return logical_rel_path, new_module


def _collect_top_level_defs(tree: ast.AST) -> dict[str, ast.AST]:
    """クラス、関数、変数代入をトップレベル名で引ける索引にする。"""
    defs: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            defs[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defs[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defs[node.target.id] = node
    return defs


def _copy_sync_imports(entities: dict, sync_functions_dict: dict) -> list[ast.AST]:
    """クラス同期関数が必要とするimportを、生成モジュール側へコピーする。"""
    imports: list[ast.AST] = []
    for entity_name, spec in entities.items():
        if spec.get("kind") != "class":
            continue
        sync_key = spec.get("sync_key", entity_name)
        sync_imports, _ = sync_functions_dict.get(sync_key, ([], []))
        for import_node in sync_imports:
            imports.append(copy.deepcopy(import_node))
    return imports


def _normalize_entity_mappings(
    entity_mappings: list,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
) -> dict:
    """entity_mappingsを検証し、生成処理向けの内部specへ正規化する。

    Args:
        entity_mappings: modules.jsonのentity_mappings配列。
        top_level_by_version: versionごとのトップレベル定義索引。
        versions: 当該モジュールで宣言されているversion一覧。

    Returns:
        生成時のentity名をkeyにした正規化済みspec。

    Raises:
        ValueError: kind、source_names、alias衝突など、宣言と入力ASTが矛盾する場合。
    """
    if not isinstance(entity_mappings, list):
        raise ValueError("Module entity_mappings must be an array")

    out: dict = {}
    used_public_names: set[str] = set()
    used_entity_keys: set[str] = set()
    used_sources_by_version: dict[int, set[str]] = {version: set() for version in versions}
    for raw_spec in entity_mappings:
        if not isinstance(raw_spec, dict):
            raise ValueError("Module entity_mappings array items must be objects")
        spec = copy.deepcopy(raw_spec)
        kind = spec.get("kind")
        if kind not in {"class", "function", "variable"}:
            raise ValueError(f"Invalid entity kind: {kind}")
        if kind == "variable":
            versioned_by = spec.get("versioned_by")
            if versioned_by not in {"generated", "referenced"}:
                raise ValueError("Variable entity versioned_by must be 'generated' or 'referenced'")
        elif "versioned_by" in spec:
            raise ValueError("versioned_by is only valid for variable entities")

        # entity_mappings は外部仕様なので、生成処理が使いやすい内部specへ正規化する。
        source_names = _normalize_source_names(spec, versions)
        entity_key = spec.get("entity_key")
        if entity_key is None:
            entity_key = _default_entity_key(source_names, versions)
        if not isinstance(entity_key, str) or not entity_key:
            raise ValueError("Entity entity_key must be a non-empty string")
        if entity_key in used_entity_keys:
            raise ValueError(f"Duplicate entity_key: {entity_key}")
        used_entity_keys.add(entity_key)
        spec["source_names"] = source_names
        spec["sync_key"] = entity_key

        # 異名 mapping は実体と公開aliasを分ける。referenced変数だけはkey名にlatest右辺を束縛する。
        aliases = _build_alias_names(source_names)
        if _uses_entity_alias(entity_key, aliases):
            spec["entity_key"] = entity_key
            spec["entity_name"] = entity_key if spec.get("versioned_by") == "referenced" else f"_{entity_key}_Entity"
            spec["aliases"] = aliases
        else:
            spec["entity_key"] = entity_key
            spec["entity_name"] = entity_key
            spec["aliases"] = []

        # 同じ公開名を複数 entity から出すと、版選択では解決できない曖昧さになるため拒否する。
        public_names = spec["aliases"] or [spec["entity_name"]]
        for public_name in public_names:
            if public_name in used_public_names:
                raise ValueError(f"Alias name collision: {public_name}")
            used_public_names.add(public_name)

        for version in versions:
            source_name = entity_source_name(spec["entity_name"], spec, version)
            if source_name in used_sources_by_version[version]:
                raise ValueError(f"Duplicate entity source in v{version}: {source_name}")
            used_sources_by_version[version].add(source_name)
            node = entity_source_node(top_level_by_version, spec["entity_name"], spec, version)
            if not _matches_kind(node, kind):
                raise ValueError(f"Entity {entity_key} ({kind}) source {source_name} is missing or mismatched in v{version}")
        out[spec["entity_name"]] = spec
    return out


def _default_entity_key(source_names: dict[str, str], versions: list[int]) -> str:
    """entity_key未指定時に、各versionのsource名から暫定keyを作る。"""
    parts: list[str] = []
    for version in versions:
        source_name = source_names[str(version)]
        parts.append(source_name[:1].upper() + source_name[1:].lower())
    return "".join(parts)


def _normalize_source_names(spec: dict, versions: list[int]) -> dict[str, str]:
    """source_namesが全version分そろっていることを検証して正規化する。"""
    raw_source_names = spec.get("source_names")
    if not isinstance(raw_source_names, dict):
        raise ValueError("Entity source_names must be an object")

    source_names: dict[str, str] = {}
    for version in versions:
        source_name = raw_source_names.get(str(version))
        if not isinstance(source_name, str) or not source_name:
            raise ValueError(f"Entity source name for v{version} must be a non-empty string")
        source_names[str(version)] = source_name
    return source_names


def _build_alias_names(source_names: dict[str, str]) -> list[str]:
    """各versionのsource名を、重複を除いた公開alias候補にする。"""
    aliases: list[str] = []
    for name in source_names.values():
        if name not in aliases:
            aliases.append(name)
    return aliases


def _uses_entity_alias(entity_key: str, aliases: list[str]) -> bool:
    """source名とentity_keyが一致せず、alias生成が必要か判定する。"""
    return len(aliases) > 1 or aliases != [entity_key]


def _build_alias_assignments(entities: dict) -> list[ast.Assign]:
    """生成したentity本体へ、旧名や異名から到達するための代入を作る。"""
    assignments: list[ast.Assign] = []
    for entity_name, spec in entities.items():
        # 生成した実体を、各版で実際に使われていた名前から参照できるようにする。
        for alias in spec.get("aliases", []):
            if alias == entity_name:
                continue
            assignments.append(ast.Assign(
                targets=[ast.Name(id=alias, ctx=ast.Store())],
                value=ast.Name(id=entity_name, ctx=ast.Load()),
            ))
    return assignments


def _mapped_output_names(entities: dict, latest_version: int) -> set[str]:
    """通常定義として再コピーしてはいけないトップレベル名を集める。"""
    names: set[str] = set(entities)
    for entity_name, spec in entities.items():
        names.add(entity_name)
        names.update(spec.get("aliases", []))
        # latest 側の source 定義を通常定義として再コピーすると alias と重複するため除外する。
        names.add(entity_source_name(entity_name, spec, latest_version))
    return names


def _matches_kind(node: ast.AST | None, kind: str) -> bool:
    """entity_mappingsのkindと、実際のASTノード種別が一致するか判定する。"""
    if kind == "class":
        return isinstance(node, ast.ClassDef)
    if kind == "function":
        return isinstance(node, ast.FunctionDef)
    if kind == "variable":
        return isinstance(node, (ast.Assign, ast.AnnAssign))
    return False


def _copy_unmapped_latest_defs(latest_tree: ast.AST, mapped_names: set[str]) -> list[ast.AST]:
    """entity_mappings対象外のlatest定義を、そのまま生成モジュールへ残す。"""
    out: list[ast.AST] = []
    for node in latest_tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if _top_level_name(node) in mapped_names:
            continue
        out.append(copy.deepcopy(node))
    return out


def _top_level_name(node: ast.AST) -> str | None:
    """トップレベル定義ノードから、その公開名を取り出す。"""
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None
