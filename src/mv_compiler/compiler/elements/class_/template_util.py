from pathlib import Path
from ...common.util import logger
from ...common.util.constants import (
    TEMPLATE_CURRENT_STATE_ATTR,
    TEMPLATE_VERSION_SINGLETON_ATTR,
    TEMPLATE_SWITCH_TO_VERSION_FUNC,
    TEMPLATE_SYNC_CALL_PLACEHOLDER,
)
import ast

_TEMPLATE_DIR = Path(__file__).parent / "templates"

def get_template_string(template_filename: str) -> str | None:
    """
    templatesディレクトリ内のテンプレートファイルを読み込む。

    Args:
        template_filename: 読み込むテンプレートファイル名 (例: "stub_method_template.py")

    戻り値:
        ファイル内容を文字列で返す。見つからない場合は None。
    """
    template_path = _TEMPLATE_DIR / template_filename
    try:
        with open(template_path, 'r', encoding='utf-8-sig') as f:
            return f.read()
    except FileNotFoundError:
        logger.error_log(f"Template file not found at: {template_path}")
        return None
    
def load_template_ast(template_filename: str) -> ast.Module | None:
    """
    指定テンプレートからASTを読み込んで返す。

    Args:
        template_filename: 読み込むテンプレートファイル名 (例: "stub_method_template.py")

    戻り値:
        解析済みのAST(Module)。読み込みやパースに失敗した場合は None。
    """
    template_string = get_template_string(template_filename)
    if not template_string:
        logger.error_log(f"Failed to load template: {template_filename}")
        return None

    try:
        template_ast = ast.parse(template_string)
        return template_ast
    except SyntaxError as e:
        logger.error_log(f"Syntax error parsing template {template_filename}: {e}")
        return None
    
class TemplateRenamer(ast.NodeTransformer):
    def __init__(self, class_name: str, sync_dispatch_chain: ast.If | None = None):
        self.class_name = class_name
        self.sync_dispatch_chain = sync_dispatch_chain

    def visit_Attribute(self, node):
        node = self.generic_visit(node)
        if node.attr == TEMPLATE_CURRENT_STATE_ATTR:
            node.attr = f'_{self.class_name.lower()}_current_state'
        elif node.attr == TEMPLATE_VERSION_SINGLETON_ATTR:
            node.attr = f'_{self.class_name.upper()}_VERSION_INSTANCES_SINGLETON'
        return node
    
    def visit_FunctionDef(self, node):
        node = self.generic_visit(node)
        if node.name == TEMPLATE_SWITCH_TO_VERSION_FUNC:
            node.name = f'_{self.class_name.lower()}_switch_to_version'
        return node

    def visit_Assign(self, node):
        node = self.generic_visit(node)
        if isinstance(node.targets[0], ast.Name) and node.targets[0].id == TEMPLATE_SYNC_CALL_PLACEHOLDER:
            if self.sync_dispatch_chain:
                node = self.sync_dispatch_chain
            else:
                # If there are no sync functions, remove the placeholder
                node = None
        return node
