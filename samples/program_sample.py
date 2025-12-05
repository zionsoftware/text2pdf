def factorial(n):
    """Calculates the factorial of n."""
    if n == 0:
        return 1
    else:
        return n * factorial(n - 1)

def main():
    print("Factorial Table:")
    print("----------------")
    for i in range(10):
        print(f"{i:2d}! = {factorial(i):8d}")

if __name__ == "__main__":
    main()
