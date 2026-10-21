# Topic: Capitalize each word
s = "welcome to python class"
print(s.title())
print(" ".join(w.capitalize() for w in s.split()))
