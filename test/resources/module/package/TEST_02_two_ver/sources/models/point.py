class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def get_coords_str(self):
        return f"({self.x}, {self.y})"
    