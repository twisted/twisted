
"""Helper stuff for things"""

import gc
gc.disable()
print 'Disabled GC'

def timeit(func, iter = 1000, *args, **kwargs):
    """timeit(func, iter = 1000 *args, **kwargs) -> elapsed time
    
    calls func iter times with args and kwargs, returns time elapsed
    """

    import time
    r = range(iter)
    t = time.time()
    for i in r:
        func(*args, **kwargs)
    return time.time() - t
