
import gc, inspect
from types import ClassType

from twisted.python.util import dsu

def topTypes(N=25):
    d = {}
    for o in gc.get_objects():
        s = str(getattr(o, '__class__', type(o)))
        d[s] = d.get(s, 0) + 1
    counts = [(v, k) for (k, v) in d.iteritems()]
    counts.sort()
    counts = counts[-N:]
    counts.reverse()
    return counts

def topClasses(N=25):
    d = {}
    for o in gc.get_objects():
        try:
            isTypeOrClass = issubclass(o, type) or isinstance(o, ClassType)
        except TypeError:
            pass
        else:
            if isTypeOrClass:
                s = getattr(o, '__name__', str(o))
                for i in gc.get_referrers(o):
                    if isinstance(i, o):
                        d[s] = d.get(s, 0) + 1
    counts = [(v, k) for (k, v) in d.iteritems()]
    counts.sort()
    counts = counts[-N:]
    counts.reverse()
    return counts

def decorateWithReferrers(objs, exclude=()):
    f = inspect.currentframe()
    exclude = list(exclude) + [f, f.f_locals]
    return [([r for r in gc.get_referrers(o) if r not in exclude], o) for o in objs]

from twisted.python.reflect import objgrep, isSame

class ReferrerTracker:
    def instancesOf(self, type):
        return [o for o in gc.get_referrers(type) if isinstance(o, type)]

    def findInFrames(self, o):
        f = inspect.currentframe()
        frames = []
        while f.f_back:
            frames.append(f.f_back)
            f = f.f_back
        for f in frames:
            r = objgrep(f.f_locals, o, isSame)
            print 'Looked for', o, 'in', f, 'and found', r
            if r:
                yield f, r

    def findInstanceMongerFrame(self, type, min):
        instances = self.instancesOf(type)
        if len(instances) < min:
            return None
        results = {}
        for i in instances:
            for (f, stuff) in self.findInFrames(i):
                results[f] = results.get(f, 0) + 1
        if results:
            f = dsu(results, lambda v: results[v])[-1]
            if results[f] > min:
                return f
        return None

    def topReferrers(self, N=100, type=None):
        f = inspect.currentframe()
        referrers = {}
        objects = gc.get_objects()
        for o in objects:
            if type is not None and not isinstance(o, type):
                continue
            refs = gc.get_referrers(o)
            for r in refs:
                if r is f or r is f.f_locals or r is objects or r is __builtins__:
                    continue
                i = id(r)
                if i in referrers:
                    referrers[i][1].append(o)
                else:
                    referrers[i] = (r, [o])
            del refs

        refs = dsu(referrers.values(), lambda v: len(v[1]))
        for i in range(len(refs)):
            if len(refs[i][1]) >= N:
                result = refs[i:]
                return decorateWithReferrers(result, exclude=[f, f.f_locals, objects])
        return []

rt = ReferrerTracker()
topReferrers = rt.topReferrers
findInstanceMongerFrame = rt.findInstanceMongerFrame
