from .point import Point

class Location:

    def __init__(self, p: Point):
        self.point = p

    def describe(self):
        print(f'V2 Description: Position is {self.point.get_coords_str()}')

    def distance_to(self, other):
        dx = self.point.x - other.point.x
        dy = self.point.y - other.point.y
        return (dx ** 2 + dy ** 2) ** 0.5
