import t_appl, pickle, traceback

def dump():
    b = t_appl.Blah()
    pickle.dump(b, file("main.tap", "wb"))

def load():
    b = pickle.load(file("module.tap", "rb"))

if __name__ == "__main__":
    dump()
    t_appl.dump()
    try:
        load()
    except:
        print "foobar 1"
        traceback.print_exc()
    try:
        t_appl.load()
    except:
        print "foobar 2"
        traceback.print_exc()
