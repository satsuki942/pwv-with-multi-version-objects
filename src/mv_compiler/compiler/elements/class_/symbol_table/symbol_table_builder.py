import ast

from .symbol_table import SymbolTable
from .class_info import ClassInfo
from .method_info import MethodInfo, ParameterInfo
from ..ast_util import get_class_version_info, get_class_version_info_from_name, UNVERSIONED_CLASS_TAG
from ....common.util.constants import INITIALIZE_METHOD_NAME

class SymbolTableBuilder(ast.NodeVisitor):
    """
    ソースASTを走査してシンボルテーブルを構築する。
    """
    def __init__(self, symbol_table: SymbolTable):
        self.symbol_table = symbol_table

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name, version = get_class_version_info(node)

        if not class_name:
            # 非バージョンクラス
            class_name = node.name
            is_versioned = False
            version = UNVERSIONED_CLASS_TAG
        else:
            is_versioned = True

        existing_class_info = self.symbol_table.lookup_class(class_name)
        methods_map = existing_class_info.methods if existing_class_info else {}
        versioned_bases_map = existing_class_info.versioned_bases if existing_class_info else {}
        versions_set = set(existing_class_info.versions) if existing_class_info else set()

        # versionedクラスの場合のみ継承関係を収集
        if is_versioned:
            versions_set.add(version)
            bases_for_this_version = []
            for base_node in node.bases:
                parent_base_name = None
                parent_version = None

                if isinstance(base_node, ast.Name):
                    parent_base_name, parent_version = get_class_version_info_from_name(base_node.id)
                    if not parent_base_name:
                        parent_base_name = base_node.id
                        parent_version = UNVERSIONED_CLASS_TAG
                elif isinstance(base_node, ast.Attribute):
                    parent_base_name, parent_version = get_class_version_info_from_name(base_node.attr)
                    if not parent_base_name:
                        parent_base_name = ast.unparse(base_node)
                        parent_version = UNVERSIONED_CLASS_TAG
                else:
                    parent_base_name = ast.unparse(base_node)
                    parent_version = UNVERSIONED_CLASS_TAG

                bases_for_this_version.append((parent_base_name, parent_version))
            
            if bases_for_this_version:
                versioned_bases_map[version] = bases_for_this_version
        
        for member in node.body:
            # メソッド定義の収集
            if isinstance(member, ast.FunctionDef):
                method_info = self._create_method_info(member, version)
                if member.name == '__init__' and is_versioned:
                    method_info.name = INITIALIZE_METHOD_NAME
                    method_info.ast_node.name = INITIALIZE_METHOD_NAME
                methods_map.setdefault(method_info.name, []).append(method_info)

        class_info = ClassInfo(
            class_name=class_name,
            is_versioned=is_versioned,
            versioned_bases=versioned_bases_map,
            methods=methods_map,
            versions=versions_set,
        )
        self.symbol_table.add_class(class_info)

    # --- HELPER METHODS ---
    def _create_method_info(self, method_node: ast.FunctionDef, version: str) -> MethodInfo:
        parameters = []
        args = method_node.args
        
        # デフォルト値の開始位置を計算
        pos_and_kw_args = args.posonlyargs + args.args
        defaults_start_index = len(pos_and_kw_args) - len(args.defaults)

        # --- 1. 位置専用引数 (/) の収集 ---
        for i, arg in enumerate(args.posonlyargs):
            parameters.append(ParameterInfo(
                name=arg.arg,
                type=ast.unparse(arg.annotation) if arg.annotation else "any",
                has_default_value=(i >= defaults_start_index),
                kind='POSITIONAL_ONLY'
            ))

        # --- 2. 通常引数の収集 ---
        for i, arg in enumerate(args.args):
            # 'self' は無視
            if i == 0:
                continue
            
            combined_index = len(args.posonlyargs) + i
            parameters.append(ParameterInfo(
                name=arg.arg,
                type=ast.unparse(arg.annotation) if arg.annotation else "any",
                has_default_value=(combined_index >= defaults_start_index),
                kind='POSITIONAL_OR_KEYWORD'
            ))
            
        # --- 3. 可変長位置引数 (*args) の収集 ---
        if args.vararg:
            arg = args.vararg
            parameters.append(ParameterInfo(
                name=arg.arg,
                type=ast.unparse(arg.annotation) if arg.annotation else "any",
                has_default_value=False,
                kind='VAR_POSITIONAL'
            ))

        # --- 4. キーワード専用引数 (*) の収集 ---
        for i, arg in enumerate(args.kwonlyargs):
            has_default = args.kw_defaults[i] is not None
            parameters.append(ParameterInfo(
                name=arg.arg,
                type=ast.unparse(arg.annotation) if arg.annotation else "any",
                has_default_value=has_default,
                kind='KEYWORD_ONLY'
            ))

        # --- 5. 可変長キーワード引数 (**kwargs) の収集 ---
        if args.kwarg:
            arg = args.kwarg
            parameters.append(ParameterInfo(
                name=arg.arg,
                type=ast.unparse(arg.annotation) if arg.annotation else "any",
                has_default_value=False,
                kind='VAR_KEYWORD'
            ))
        
        return MethodInfo(
            name=method_node.name,
            version=version,
            parameters=parameters,
            ast_node=method_node
        )

