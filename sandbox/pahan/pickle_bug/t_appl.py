import pickle

class Blah:
    pass

def dump():
    b = Blah()
    pickle.dump(b, file("module.tap", "w"))

def load():
    b = pickle.load(file("module.tap", "rb"))
