# -*- test-case-name: imagination.test -*-

class Faceted(dict):

    __slots__ = ()
    __conform__ = dict.get

    def copy(self):
        copy = self.__class__()
        copy.update(self)
        return copy

    def __repr__(self):
        return 'Faceted('+super(Faceted, self).__repr__()+')'

class Facet(object):
    def __init__(self, original):
        self.original = original

