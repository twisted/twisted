# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Helper stuff for benchmarks.
"""

import gc
gc.disable()
print 'Disabled GC'

def timeit(func, iter = 1000, *args, **kwargs):
    """
    timeit(func, iter = 1000 *args, **kwargs) -> elapsed time
    
    calls func iter times with args and kwargs, returns time elapsed
    """

    from time import time as currentTime
    r = range(iter)
    t = currentTime()
    for i in r:
        func(*args, **kwargs)
    return currentTime() - t
