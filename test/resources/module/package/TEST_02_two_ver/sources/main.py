# package 配下で複数 version module と通常 module を組み合わせて import できることを検証する。
from models.location import Location
from models.point import Point

def main():
    p = Point(3, 4)
    loc1 = Location(p)
    loc1.describe()
    loc2 = Location(Point(0, 0))
    distance = loc1.distance_to(loc2)
    print(int(distance))

if __name__ == "__main__":
    main()
