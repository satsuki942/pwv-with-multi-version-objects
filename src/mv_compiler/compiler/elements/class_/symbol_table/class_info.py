from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple

from .method_info import MethodInfo

@dataclass
class ClassInfo:
    """単一クラスの情報（メンバ情報を含む）を保持する。"""
    class_name: str
    is_versioned: bool
    versioned_bases: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)
    methods: Dict[str, List[MethodInfo]] = field(default_factory=dict)
    versions: Set[str] = field(default_factory=set)

    def get_all_versions(self) -> Set[str]:
        """
        このクラスに存在するバージョン集合を返す。
        """
        versions = set(self.versions)
        for overloads in self.methods.values():
            for method_info in overloads:
                versions.add(method_info.version)
        
        return versions
    
    def get_methods_for_version(self, version_str: str) -> List[MethodInfo]:
        """
        指定バージョンに属するMethodInfoをすべて返す。
        """
        version_methods = []
        for overloads in self.methods.values():
            for method_info in overloads:
                if method_info.version == version_str:
                    version_methods.append(method_info)
        return version_methods

    def has_consistent_signature(self, method_name: str) -> bool:
        """
        指定メソッドの全バージョンが同一シグネチャかを判定する。
        """
        overloads = self.methods.get(method_name)
        if not overloads or len(overloads) <= 1:
            return True

        first_signature = overloads[0].parameters
        for other_info in overloads[1:]:
            if other_info.parameters != first_signature:
                return False
        
        return True
        
