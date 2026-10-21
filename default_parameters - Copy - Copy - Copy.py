# Topic: Default parameter values
def order(item, qty=1):  # qty is optional
    print(qty, "x", item)
order("Pizza")  # uses default 1
order("Burger", 3)  # overrides default
