# 異なるバージョンのconstructorが非互換な場合のテスト
from location import Location
from point import Point
def main():
    # Some main logic here
    p = Point(3, 4)
    loc1 = Location(1, 2)
    loc2 = Location(p)
    loc1.print()
    loc2.print()


if __name__ == "__main__":
    main()
