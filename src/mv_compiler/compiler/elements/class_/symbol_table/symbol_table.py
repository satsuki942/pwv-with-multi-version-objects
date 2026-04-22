from typing import Dict, Optional

from .class_info import ClassInfo

class SymbolTable:
    """
    プロジェクト内の全クラス情報を保持する。
    """

    def __init__(self):
        self._class_table: Dict[str, ClassInfo] = {}

    def add_class(self, class_info: ClassInfo):
        """
        クラス情報を追加または更新する。
        """
        self._class_table[class_info.class_name] = class_info

    def lookup_class(self, class_name: str) -> Optional[ClassInfo]:
        """
        クラス名で情報を検索する。
        """
        return self._class_table.get(class_name)

    def get_representation(self) -> str:
        """
        シンボルテーブルの文字列表現を返す。
        """
        lines = ["","--- Symbol Table ---"]
        if not self._class_table:
            lines.append("(No classes found)")
            lines.append("--------------------")
            return "\n".join(lines)
        
        for name, info in self._class_table.items():
            lines.append(f"Class: {name} (Versioned: {info.is_versioned})")
            lines.append(f"  - Base Classes: {info.versioned_bases}")

            # Output method information
            if not info.methods:
                lines.append("  - (No methods found)")
            else:
                for method_name, overloads in info.methods.items():
                    for method_info in overloads:
                        param_types = [p.type for p in method_info.parameters]
                        lines.append(f"  - Method: {method_info.name}, Version: {method_info.version}, Params: {param_types}")
        
        lines.append("--------------------")
        lines.append("")
        return "\n".join(lines)
