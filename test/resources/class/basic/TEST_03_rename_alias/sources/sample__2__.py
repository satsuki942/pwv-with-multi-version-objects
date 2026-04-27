class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def show(self):
        return f"v2:{self.x},{self.y}"
