from __future__ import generators

# Make the module name of things defined in this file 'correct'.
__name__ = 'UserDict'

# In Python 2.3.0
class DictMixin:
    # Mixin defining all dictionary methods for classes that already have
    # a minimum dictionary interface including getitem, setitem, delitem,
    # and keys. Without knowledge of the subclass constructor, the mixin
    # does not define __init__() or copy().  In addition to the four base
    # methods, progressively more efficiency comes with defining
    # __contains__(), __iter__(), and iteritems().

    # second level definitions support higher levels
    def __iter__(self):
        for k in self.keys():
            yield k
    def has_key(self, key):
        try:
            value = self[key]
        except KeyError:
            return False
        return True
    def __contains__(self, key):
        return self.has_key(key)

    # third level takes advantage of second level definitions
    def iteritems(self):
        for k in self:
            yield (k, self[k])
    def iterkeys(self):
        return self.__iter__()

    # fourth level uses definitions from lower levels
    def itervalues(self):
        for _, v in self.iteritems():
            yield v
    def values(self):
        return [v for _, v in self.iteritems()]
    def items(self):
        return list(self.iteritems())
    def clear(self):
        for key in self.keys():
            del self[key]
    def setdefault(self, key, default):
        try:
            return self[key]
        except KeyError:
            self[key] = default
        return default
    def pop(self, key, *args):
        if len(args) > 1:
            raise TypeError, "pop expected at most 2 arguments, got "\
                              + repr(1 + len(args))
        try:
            value = self[key]
        except KeyError:
            if args:
                return args[0]
            raise
        del self[key]
        return value
    def popitem(self):
        try:
            k, v = self.iteritems().next()
        except StopIteration:
            raise KeyError, 'container is empty'
        del self[k]
        return (k, v)
    def update(self, other):
        # Make progressively weaker assumptions about "other"
        if hasattr(other, 'iteritems'):  # iteritems saves memory and lookups
            for k, v in other.iteritems():
                self[k] = v
        elif hasattr(other, '__iter__'): # iter saves memory
            for k in other:
                self[k] = other[k]
        else:
            for k in other.keys():
                self[k] = other[k]
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
    def __repr__(self):
        return repr(dict(self.iteritems()))
    def __cmp__(self, other):
        if isinstance(other, DictMixin):
            other = dict(other.iteritems())
        return cmp(dict(self.iteritems()), other)
    def __len__(self):
        return len(self.keys())

