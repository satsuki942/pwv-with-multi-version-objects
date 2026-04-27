THRESHOLD = 20
PLAIN = "new"


class Point:
    def __init__(self, x, y=0):
        self.x = x
        self.y = y

    def show(self):
        return f"v2:{self.x},{self.y}:{THRESHOLD + 1}"


def label():
    return f"v2:{THRESHOLD + 2}"
