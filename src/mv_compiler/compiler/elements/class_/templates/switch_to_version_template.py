# トランスパイラがASTとして解析・再利用するためのテンプレート。
# 直接実行されない。
def _SWITCH_TO_VERSION_PLACEHOLDER(self, version_num):
    type(self)._switch_count += 1
    current_version_num = self._CURRENT_STATE_PLACEHOLDER._version_number

    _SYNC_CALL_PLACEHOLDER_ = None

    self._CURRENT_STATE_PLACEHOLDER = self._VERSION_INSTANCES_SINGLETON_PLACEHOLDER[version_num - 1]
