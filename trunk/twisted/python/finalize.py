
"""
A module for externalized finalizers.
"""

import weakref

garbageKey = 0

def callbackFactory(num, fins):
    def _cb(w):
        del refs[num]
        for fx in fins:
            fx()
    return _cb

refs = {}

def register(inst):
    global garbageKey
    garbageKey += 1
    r = weakref.ref(inst, callbackFactory(garbageKey, inst.__finalizers__()))
    refs[garbageKey] = r

if __name__ == '__main__':
    def fin():
        print 'I am _so_ dead.'

    class Finalizeable:
        """
        An un-sucky __del__
        """

        def __finalizers__(self):
            """
            I'm going away.
            """
            return [fin]

    f = Finalizeable()
    f.f2 = f
    register(f)
    del f
    import gc
    gc.collect()
    print 'deled'
