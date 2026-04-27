THRESHOLD = 10
PLAIN = "old"


class Point:
    def __init__(self, x):
        self.x = x

    def show(self):
        return f"v1:{self.x}:{THRESHOLD + 1}"


def label():
    return f"v1:{THRESHOLD + 2}"
