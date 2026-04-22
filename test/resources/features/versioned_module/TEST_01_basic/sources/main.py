from sample import PLAIN, THRESHOLD, Point, label


def main():
    print(PLAIN)
    print(label())
    print(THRESHOLD.switch_to(2) + 5)
    p = Point(3)
    print(p.show())


if __name__ == "__main__":
    main()
