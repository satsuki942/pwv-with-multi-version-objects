@[ATTR].setter
def [ATTR](self, value):
    try:
        self._[ATTR]
    except AttributeError:
        self._SWITCH_TO_VERSION_PLACEHOLDER([VERSION])
    self._[ATTR] = value
