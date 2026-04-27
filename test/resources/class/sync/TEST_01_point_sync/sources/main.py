# sync mapping により座標表現の異なる version 間で状態同期されることを検証する。
from point import Point

def main():
    p = Point(3.0, 4.0)
    polar_coords = p.get_polar()
    print(f'Polar coords: r={polar_coords[0]:.2f}, theta={polar_coords[1]:.2f}')
    p.r = 0
    cartesian_coords = p.get_cartesian()
    print(f'Cartesian coords: x={cartesian_coords[0]:.2f}, y={cartesian_coords[1]:.2f}')
if __name__ == '__main__':
    main()
