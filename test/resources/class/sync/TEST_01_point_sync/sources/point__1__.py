class Point:

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        print(f'V1 Point created at (x={self.x}, y={self.y})')

    def get_cartesian(self) -> tuple:
        return (self.x, self.y)
