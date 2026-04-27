import ast


# 指定versionで実際にソース上に存在する名前を返す。
def entity_source_name(entity_name: str, spec: dict, version: int) -> str:
    # source_names は modules.json のversion文字列キーに依存するため、参照方法をここへ集約する。
    return spec.get("source_names", {}).get(str(version), entity_name)


# 論理entity名とversionから、対応するトップレベルASTノードを引く。
# 例: entity_name="User", source_names={"1": "OldUser", "2": "User"} の v1 なら OldUser のASTを返す。
def entity_source_node(
    top_level_by_version: dict[int, dict[str, ast.AST]],
    entity_name: str,
    spec: dict,
    version: int,
) -> ast.AST | None:
    return top_level_by_version[version].get(entity_source_name(entity_name, spec, version))


# entity_mappingsをkind単位の処理へ渡せるように絞り込む。
def entities_of_kind(entities: dict, kind: str) -> dict:
    return {
        name: spec for name, spec in entities.items()
        if spec.get("kind") == kind
    }
