from numarray import array

def distance(x, y):
    return _distance(array(x, typecode='d'),
                     array(y, typecode='d'))

def _distance(x, y):
    return sum((x - y) ** 2) ** 0.5

def magnitude(a):
    return _magnitude(array(a, typecode='d'))

def _magnitude(a):
    return sum(a * a) ** 0.5

def normalize(a):
    return _normalize(array(a, typecode='d'))

def _normalize(a):
    return a / magnitude(a)

def visible(viewpoint, direction, cosAngle, target):
    return _visible(array(viewpoint, typecode='d'),
                    array(direction, typecode='d'),
                    cosAngle,
                    array(target, typecode='d'))

def _visible(viewpoint, direction, cosAngle, target):
    if alltrue(target == viewpoint):
        return False
    target = normalize(target - viewpoint)
    direction = normalize(direction)
    prod = dot(target, direction - viewpoint)
    return prod > cosAngle

def permute(s, n):
    if n == 0:
        yield []
    else:
        for e in s:
            for r in permute(s, n - 1):
                yield r + [e]

def linePointDistance(x0, x1, x2):
    return _linePointDistance(array(x0, typecode='d'),
                              array(x1, typecode='d'),
                              array(x2, typecode='d'))

def cross(a, b):
    x = a[1] * b[2] - a[2] * b[1]
    y = a[2] * b[0] - a[0] * b[2]
    z = a[0] * b[1] - a[1] * b[0]
    return array([x, y, z], typecode='d')

def _linePointDistance(x0, x1, x2):
    x = cross(x2 - x1, x1 - x0)
    num = magnitude(x)
    den = magnitude(x2 - x1)
    r = num / den
    return r
