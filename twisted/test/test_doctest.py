#!/usr/bin/python2.3

# XXX This whole module is confusing.  It doesn't seem to test
# the doc test functionality, but merely assumes it will work.
# It also seems unlikely that these tests will run as a result
# of "trial twisted.test".

"""
this is a module doctest

>>> foobar(5)
25
"""


def foobar(n):
    # XXX Note that two parts of the Twisted coding standard are relevant
    # here: quotes within a triple quoted string should be escaped and
    # code samples within a doc string should be left aligned against a
    # column of |s.  If doctest does not support this, it may be necessary
    # to extend it, rather than encourage violation of the coding standard
    # by adding features contrary to it.  Also, the indentation here seems
    # weird.  Why is it not at the same level of indentation as the rest
    # of the function? Is it a doctest limitation?
    """
>>> foobar(12)
32
>>> foobar(39)
Traceback (most recent call last):
    File "<stdin>", line 1, in ?
    File "test_doctest.py", line 15, in foobar
    raise RuntimeError, "must supply an integer <= 20!"
RuntimeError: must supply an integer <= 20!
>>> foobar(11)
1292
    """
    if n > 20:
        raise RuntimeError, "must supply an integer <= 20!"
    return n + 20



def _test():
    import doctest
    from twisted.test import test_doctest
    return doctest.testmod(test_doctest)


if __name__ == '__main__':
    _test()
