

def callsPer(quota, timers, f, *a, **b):
    """
    Returns a list of length len(timers).  The first timer is considered
    authoritative.  Quota is the amount of measurement in the authoritative
    timer.  Each element in the return value is the number of times f can be
    called as f(*a, **b) in one unit of each timer.
    """
    t = timers[0]
    then = t()
    now = then
    count = 0.
    lthen = range(len(timers))
    pos = 0
    for timer in timers:
        lthen[pos] = timer()
        pos += 1
    while now - then < quota:
        f(*a,**b)
        count += 1.
        now = t()
    pos = 0
    valr = range(len(timers))
    for timer in timers:
        elapsed = timer() - lthen[pos]
        valr[pos] = count / elapsed
        pos += 1
    return valr

def nop(*a,**b):
    pass

def test():
    import time
    print callsPer(1, [time.time, time.clock], nop)

if __name__ == '__main__':
    test()

