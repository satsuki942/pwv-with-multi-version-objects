# トランスパイラがASTとして解析・再利用するためのテンプレート。
# 直接実行されない。
def __init__(self, *args, **kwargs):

    self._CURRENT_STATE_PLACEHOLDER = self._VERSION_INSTANCES_SINGLETON_PLACEHOLDER[0]

    try:
        self._CURRENT_STATE_PLACEHOLDER.__initialize__(*args, _wrapper_self=self, **kwargs)
    except (AttributeError, TypeError):
        # __initialize__ 呼び出しのディスパッチ if-else 連鎖
        pass
