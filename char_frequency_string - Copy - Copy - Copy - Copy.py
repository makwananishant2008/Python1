# Topic: Character frequency
s = "hello"
for ch in sorted(set(s)):
    print(ch, "->", s.count(ch))
