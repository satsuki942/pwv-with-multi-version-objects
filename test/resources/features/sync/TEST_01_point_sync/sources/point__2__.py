class Point:

    def __init__(self, r: float, theta: float):
        self.r = r
        self.theta = theta
        print(f'V2 Point created at (r={self.r}, theta={self.theta})')

    def get_polar(self) -> tuple:
        return (self.r, self.theta)
