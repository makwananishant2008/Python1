# Topic: Built-in functions together
data = [-5, 12, -8, 20]
print("Count:", len(data))
print("Biggest:", max(data), "Smallest:", min(data))
print("Sum of absolute values:", sum(abs(x) for x in data))
