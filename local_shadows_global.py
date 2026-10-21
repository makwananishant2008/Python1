# Topic: Local variable hides global with same name
x = "global"
def test():
    x = "local"  # new local variable
    print(x)
test()
print(x)  # global is not changed
