from point import Point

class Location:

    def __init__(self, p):
        self.x = p.getX()
        self.y = p.getY()

    def print(self):
        print(f'Location v2: ({self.x}, {self.y})')
