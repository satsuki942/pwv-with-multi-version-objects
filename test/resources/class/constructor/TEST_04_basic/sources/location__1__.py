from point import Point

class Location:

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def print(self):
        print(f'Location v1: ({self.x}, {self.y})')
