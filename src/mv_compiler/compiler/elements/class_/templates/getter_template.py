@property
def [ATTR](self):
    try:
        return self._[ATTR]
    except AttributeError:
        self._SWITCH_TO_VERSION_PLACEHOLDER([VERSION])
        return self._[ATTR]
