# 親と子に同じ名前のメソッドがある場合、子のメソッドが優先される。
from student import Student
def main():
    alice = Student("Alice", 67890)
    try:
        id = alice.get_id()
        print(f"Alice's ID: {id}")
    except TypeError as e:
        print(f"TypeError: {e}")

if __name__ == "__main__":
    main()
