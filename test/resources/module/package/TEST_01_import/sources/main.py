# package 配下の versioned module を通常 import して利用できることを検証する。
from models.point import Point

def main():
    p = Point(10, 20)
    coords = p.get_coords()
    print(f"Coordinates: {coords}")

if __name__ == "__main__":
    main()
