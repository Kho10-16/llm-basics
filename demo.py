def greet(name, food):
    print(f"{name} likes {food}")

order = {"food":"pizza", "name":"Kho"}

greet(**order)
greet(name="kho", food="pizza")

order2 = {"name":"kho", "food":"pizza", "drink":"tea"}
greet(**order2)