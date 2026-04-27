from .point import Point

class Location:

    def __init__(self, p: Point):
        self.point = p

    def describe(self):
        print(f'V1 Description: Position is {self.point.get_coords_str()}')
