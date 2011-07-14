# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.http_headers}.
"""

import sys

from twisted.python.compat import set
from twisted.trial.unittest import TestCase
from twisted.web.http_headers import _DictHeaders, Headers


class HeadersTests(TestCase):
    """
    Tests for L{Headers}.
    """
    def test_initializer(self):
        """
        The header values passed to L{Headers.__init__} can be retrieved via
        L{Headers.getRawHeaders}.
        """
        h = Headers({'Foo': ['bar']})
        self.assertEqual(h.getRawHeaders('foo'), ['bar'])


    def test_setRawHeaders(self):
        """
        L{Headers.setRawHeaders} sets the header values for the given
        header name to the sequence of string values.
        """
        rawValue = ["value1", "value2"]
        h = Headers()
        h.setRawHeaders("test", rawValue)
        self.assertTrue(h.hasHeader("test"))
        self.assertTrue(h.hasHeader("Test"))
        self.assertEqual(h.getRawHeaders("test"), rawValue)


    def test_rawHeadersTypeChecking(self):
        """
        L{Headers.setRawHeaders} requires values to be of type list.
        """
        h = Headers()
        self.assertRaises(TypeError, h.setRawHeaders, {'Foo': 'bar'})


    def test_addRawHeader(self):
        """
        L{Headers.addRawHeader} adds a new value for a given header.
        """
        h = Headers()
        h.addRawHeader("test", "lemur")
        self.assertEqual(h.getRawHeaders("test"), ["lemur"])
        h.addRawHeader("test", "panda")
        self.assertEqual(h.getRawHeaders("test"), ["lemur", "panda"])


    def test_getRawHeadersNoDefault(self):
        """
        L{Headers.getRawHeaders} returns C{None} if the header is not found and
        no default is specified.
        """
        self.assertIdentical(Headers().getRawHeaders("test"), None)


    def test_getRawHeadersDefaultValue(self):
        """
        L{Headers.getRawHeaders} returns the specified default value when no
        header is found.
        """
        h = Headers()
        default = object()
        self.assertIdentical(h.getRawHeaders("test", default), default)


    def test_getRawHeaders(self):
        """
        L{Headers.getRawHeaders} returns the values which have been set for a
        given header.
        """
        h = Headers()
        h.setRawHeaders("test", ["lemur"])
        self.assertEqual(h.getRawHeaders("test"), ["lemur"])
        self.assertEqual(h.getRawHeaders("Test"), ["lemur"])


    def test_hasHeaderTrue(self):
        """
        Check that L{Headers.hasHeader} returns C{True} when the given header
        is found.
        """
        h = Headers()
        h.setRawHeaders("test", ["lemur"])
        self.assertTrue(h.hasHeader("test"))
        self.assertTrue(h.hasHeader("Test"))


    def test_hasHeaderFalse(self):
        """
        L{Headers.hasHeader} returns C{False} when the given header is not
        found.
        """
        self.assertFalse(Headers().hasHeader("test"))


    def test_removeHeader(self):
        """
        Check that L{Headers.removeHeader} removes the given header.
        """
        h = Headers()

        h.setRawHeaders("foo", ["lemur"])
        self.assertTrue(h.hasHeader("foo"))
        h.removeHeader("foo")
        self.assertFalse(h.hasHeader("foo"))

        h.setRawHeaders("bar", ["panda"])
        self.assertTrue(h.hasHeader("bar"))
        h.removeHeader("Bar")
        self.assertFalse(h.hasHeader("bar"))


    def test_removeHeaderDoesntExist(self):
        """
        L{Headers.removeHeader} is a no-operation when the specified header is
        not found.
        """
        h = Headers()
        h.removeHeader("test")
        self.assertEqual(list(h.getAllRawHeaders()), [])


    def test_canonicalNameCaps(self):
        """
        L{Headers._canonicalNameCaps} returns the canonical capitalization for
        the given header.
        """
        h = Headers()
        self.assertEqual(h._canonicalNameCaps("test"), "Test")
        self.assertEqual(h._canonicalNameCaps("test-stuff"), "Test-Stuff")
        self.assertEqual(h._canonicalNameCaps("content-md5"), "Content-MD5")
        self.assertEqual(h._canonicalNameCaps("dnt"), "DNT")
        self.assertEqual(h._canonicalNameCaps("etag"), "ETag")
        self.assertEqual(h._canonicalNameCaps("p3p"), "P3P")
        self.assertEqual(h._canonicalNameCaps("te"), "TE")
        self.assertEqual(h._canonicalNameCaps("www-authenticate"),
                          "WWW-Authenticate")
        self.assertEqual(h._canonicalNameCaps("x-xss-protection"),
                          "X-XSS-Protection")


    def test_getAllRawHeaders(self):
        """
        L{Headers.getAllRawHeaders} returns an iterable of (k, v) pairs, where
        C{k} is the canonicalized representation of the header name, and C{v}
        is a sequence of values.
        """
        h = Headers()
        h.setRawHeaders("test", ["lemurs"])
        h.setRawHeaders("www-authenticate", ["basic aksljdlk="])

        allHeaders = set([(k, tuple(v)) for k, v in h.getAllRawHeaders()])

        self.assertEqual(allHeaders,
                          set([("WWW-Authenticate", ("basic aksljdlk=",)),
                               ("Test", ("lemurs",))]))


    def test_headersComparison(self):
        """
        A L{Headers} instance compares equal to itself and to another
        L{Headers} instance with the same values.
        """
        first = Headers()
        first.setRawHeaders("foo", ["panda"])
        second = Headers()
        second.setRawHeaders("foo", ["panda"])
        third = Headers()
        third.setRawHeaders("foo", ["lemur", "panda"])
        self.assertEqual(first, first)
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)


    def test_otherComparison(self):
        """
        An instance of L{Headers} does not compare equal to other unrelated
        objects.
        """
        h = Headers()
        self.assertNotEqual(h, ())
        self.assertNotEqual(h, object())
        self.assertNotEqual(h, "foo")


    def test_repr(self):
        """
        The L{repr} of a L{Headers} instance shows the names and values of all
        the headers it contains.
        """
        self.assertEqual(
            repr(Headers({"foo": ["bar", "baz"]})),
            "Headers({'foo': ['bar', 'baz']})")


    def test_subclassRepr(self):
        """
        The L{repr} of an instance of a subclass of L{Headers} uses the name
        of the subclass instead of the string C{"Headers"}.
        """
        class FunnyHeaders(Headers):
            pass
        self.assertEqual(
            repr(FunnyHeaders({"foo": ["bar", "baz"]})),
            "FunnyHeaders({'foo': ['bar', 'baz']})")


    def test_copy(self):
        """
        L{Headers.copy} creates a new independant copy of an existing
        L{Headers} instance, allowing future modifications without impacts
        between the copies.
        """
        h = Headers()
        h.setRawHeaders('test', ['foo'])
        i = h.copy()
        self.assertEqual(i.getRawHeaders('test'), ['foo'])
        h.addRawHeader('test', 'bar')
        self.assertEqual(i.getRawHeaders('test'), ['foo'])
        i.addRawHeader('test', 'baz')
        self.assertEqual(h.getRawHeaders('test'), ['foo', 'bar'])



class HeaderDictTests(TestCase):
    """
    Tests for the backwards compatible C{dict} interface for L{Headers}
    provided by L{_DictHeaders}.
    """
    def headers(self, **kw):
        """
        Create a L{Headers} instance populated with the header name/values
        specified by C{kw} and a L{_DictHeaders} wrapped around it and return
        them both.
        """
        h = Headers()
        for k, v in kw.iteritems():
            h.setRawHeaders(k, v)
        return h, _DictHeaders(h)


    def test_getItem(self):
        """
        L{_DictHeaders.__getitem__} returns a single header for the given name.
        """
        headers, wrapper = self.headers(test=["lemur"])
        self.assertEqual(wrapper["test"], "lemur")


    def test_getItemMultiple(self):
        """
        L{_DictHeaders.__getitem__} returns only the last header value for a
        given name.
        """
        headers, wrapper = self.headers(test=["lemur", "panda"])
        self.assertEqual(wrapper["test"], "panda")


    def test_getItemMissing(self):
        """
        L{_DictHeaders.__getitem__} raises L{KeyError} if called with a header
        which is not present.
        """
        headers, wrapper = self.headers()
        exc = self.assertRaises(KeyError, wrapper.__getitem__, "test")
        self.assertEqual(exc.args, ("test",))


    def test_iteration(self):
        """
        L{_DictHeaders.__iter__} returns an iterator the elements of which
        are the lowercase name of each header present.
        """
        headers, wrapper = self.headers(foo=["lemur", "panda"], bar=["baz"])
        self.assertEqual(set(list(wrapper)), set(["foo", "bar"]))


    def test_length(self):
        """
        L{_DictHeaders.__len__} returns the number of headers present.
        """
        headers, wrapper = self.headers()
        self.assertEqual(len(wrapper), 0)
        headers.setRawHeaders("foo", ["bar"])
        self.assertEqual(len(wrapper), 1)
        headers.setRawHeaders("test", ["lemur", "panda"])
        self.assertEqual(len(wrapper), 2)


    def test_setItem(self):
        """
        L{_DictHeaders.__setitem__} sets a single header value for the given
        name.
        """
        headers, wrapper = self.headers()
        wrapper["test"] = "lemur"
        self.assertEqual(headers.getRawHeaders("test"), ["lemur"])


    def test_setItemOverwrites(self):
        """
        L{_DictHeaders.__setitem__} will replace any previous header values for
        the given name.
        """
        headers, wrapper = self.headers(test=["lemur", "panda"])
        wrapper["test"] = "lemur"
        self.assertEqual(headers.getRawHeaders("test"), ["lemur"])


    def test_delItem(self):
        """
        L{_DictHeaders.__delitem__} will remove the header values for the given
        name.
        """
        headers, wrapper = self.headers(test=["lemur"])
        del wrapper["test"]
        self.assertFalse(headers.hasHeader("test"))


    def test_delItemMissing(self):
        """
        L{_DictHeaders.__delitem__} will raise L{KeyError} if the given name is
        not present.
        """
        headers, wrapper = self.headers()
        exc = self.assertRaises(KeyError, wrapper.__delitem__, "test")
        self.assertEqual(exc.args, ("test",))


    def test_keys(self, _method='keys', _requireList=True):
        """
        L{_DictHeaders.keys} will return a list of all present header names.
        """
        headers, wrapper = self.headers(test=["lemur"], foo=["bar"])
        keys = getattr(wrapper, _method)()
        if _requireList:
            self.assertIsInstance(keys, list)
        self.assertEqual(set(keys), set(["foo", "test"]))


    def test_iterkeys(self):
        """
        L{_DictHeaders.iterkeys} will return all present header names.
        """
        self.test_keys('iterkeys', False)


    def test_values(self, _method='values', _requireList=True):
        """
        L{_DictHeaders.values} will return a list of all present header values,
        returning only the last value for headers with more than one.
        """
        headers, wrapper = self.headers(foo=["lemur"], bar=["marmot", "panda"])
        values = getattr(wrapper, _method)()
        if _requireList:
            self.assertIsInstance(values, list)
        self.assertEqual(set(values), set(["lemur", "panda"]))


    def test_itervalues(self):
        """
        L{_DictHeaders.itervalues} will return all present header values,
        returning only the last value for headers with more than one.
        """
        self.test_values('itervalues', False)


    def test_items(self, _method='items', _requireList=True):
        """
        L{_DictHeaders.items} will return a list of all present header names
        and values as tuples, returning only the last value for headers with
        more than one.
        """
        headers, wrapper = self.headers(foo=["lemur"], bar=["marmot", "panda"])
        items = getattr(wrapper, _method)()
        if _requireList:
            self.assertIsInstance(items, list)
        self.assertEqual(set(items), set([("foo", "lemur"), ("bar", "panda")]))


    def test_iteritems(self):
        """
        L{_DictHeaders.iteritems} will return all present header names and
        values as tuples, returning only the last value for headers with more
        than one.
        """
        self.test_items('iteritems', False)


    def test_clear(self):
        """
        L{_DictHeaders.clear} will remove all headers.
        """
        headers, wrapper = self.headers(foo=["lemur"], bar=["panda"])
        wrapper.clear()
        self.assertEqual(list(headers.getAllRawHeaders()), [])


    def test_copy(self):
        """
        L{_DictHeaders.copy} will return a C{dict} with all the same headers
        and the last value for each.
        """
        headers, wrapper = self.headers(foo=["lemur", "panda"], bar=["marmot"])
        duplicate = wrapper.copy()
        self.assertEqual(duplicate, {"foo": "panda", "bar": "marmot"})


    def test_get(self):
        """
        L{_DictHeaders.get} returns the last value for the given header name.
        """
        headers, wrapper = self.headers(foo=["lemur", "panda"])
        self.assertEqual(wrapper.get("foo"), "panda")


    def test_getMissing(self):
        """
        L{_DictHeaders.get} returns C{None} for a header which is not present.
        """
        headers, wrapper = self.headers()
        self.assertIdentical(wrapper.get("foo"), None)


    def test_getDefault(self):
        """
        L{_DictHeaders.get} returns the last value for the given header name
        even when it is invoked with a default value.
        """
        headers, wrapper = self.headers(foo=["lemur"])
        self.assertEqual(wrapper.get("foo", "bar"), "lemur")


    def test_getDefaultMissing(self):
        """
        L{_DictHeaders.get} returns the default value specified if asked for a
        header which is not present.
        """
        headers, wrapper = self.headers()
        self.assertEqual(wrapper.get("foo", "bar"), "bar")


    def test_has_key(self):
        """
        L{_DictHeaders.has_key} returns C{True} if the given header is present,
        C{False} otherwise.
        """
        headers, wrapper = self.headers(foo=["lemur"])
        self.assertTrue(wrapper.has_key("foo"))
        self.assertFalse(wrapper.has_key("bar"))


    def test_contains(self):
        """
        L{_DictHeaders.__contains__} returns C{True} if the given header is
        present, C{False} otherwise.
        """
        headers, wrapper = self.headers(foo=["lemur"])
        self.assertIn("foo", wrapper)
        self.assertNotIn("bar", wrapper)


    def test_pop(self):
        """
        L{_DictHeaders.pop} returns the last header value associated with the
        given header name and removes the header.
        """
        headers, wrapper = self.headers(foo=["lemur", "panda"])
        self.assertEqual(wrapper.pop("foo"), "panda")
        self.assertIdentical(headers.getRawHeaders("foo"), None)


    def test_popMissing(self):
        """
        L{_DictHeaders.pop} raises L{KeyError} if passed a header name which is
        not present.
        """
        headers, wrapper = self.headers()
        self.assertRaises(KeyError, wrapper.pop, "foo")


    def test_popDefault(self):
        """
        L{_DictHeaders.pop} returns the last header value associated with the
        given header name and removes the header, even if it is supplied with a
        default value.
        """
        headers, wrapper = self.headers(foo=["lemur"])
        self.assertEqual(wrapper.pop("foo", "bar"), "lemur")
        self.assertIdentical(headers.getRawHeaders("foo"), None)


    def test_popDefaultMissing(self):
        """
        L{_DictHeaders.pop} returns the default value is asked for a header
        name which is not present.
        """
        headers, wrapper = self.headers(foo=["lemur"])
        self.assertEqual(wrapper.pop("bar", "baz"), "baz")
        self.assertEqual(headers.getRawHeaders("foo"), ["lemur"])


    def test_popitem(self):
        """
        L{_DictHeaders.popitem} returns some header name/value pair.
        """
        headers, wrapper = self.headers(foo=["lemur", "panda"])
        self.assertEqual(wrapper.popitem(), ("foo", "panda"))
        self.assertIdentical(headers.getRawHeaders("foo"), None)


    def test_popitemEmpty(self):
        """
        L{_DictHeaders.popitem} raises L{KeyError} if there are no headers
        present.
        """
        headers, wrapper = self.headers()
        self.assertRaises(KeyError, wrapper.popitem)


    def test_update(self):
        """
        L{_DictHeaders.update} adds the header/value pairs in the C{dict} it is
        passed, overriding any existing values for those headers.
        """
        headers, wrapper = self.headers(foo=["lemur"])
        wrapper.update({"foo": "panda", "bar": "marmot"})
        self.assertEqual(headers.getRawHeaders("foo"), ["panda"])
        self.assertEqual(headers.getRawHeaders("bar"), ["marmot"])


    def test_updateWithKeywords(self):
        """
        L{_DictHeaders.update} adds header names given as keyword arguments
        with the keyword values as the header value.
        """
        headers, wrapper = self.headers(foo=["lemur"])
        wrapper.update(foo="panda", bar="marmot")
        self.assertEqual(headers.getRawHeaders("foo"), ["panda"])
        self.assertEqual(headers.getRawHeaders("bar"), ["marmot"])

    if sys.version_info < (2, 4):
        test_updateWithKeywords.skip = (
            "Python 2.3 does not support keyword arguments to dict.update.")


    def test_setdefaultMissing(self):
        """
        If passed the name of a header which is not present,
        L{_DictHeaders.setdefault} sets the value of the given header to the
        specified default value and returns it.
        """
        headers, wrapper = self.headers(foo=["bar"])
        self.assertEqual(wrapper.setdefault("baz", "quux"), "quux")
        self.assertEqual(headers.getRawHeaders("foo"), ["bar"])
        self.assertEqual(headers.getRawHeaders("baz"), ["quux"])


    def test_setdefaultPresent(self):
        """
        If passed the name of a header which is present,
        L{_DictHeaders.setdefault} makes no changes to the headers and
        returns the last value already associated with that header.
        """
        headers, wrapper = self.headers(foo=["bar", "baz"])
        self.assertEqual(wrapper.setdefault("foo", "quux"), "baz")
        self.assertEqual(headers.getRawHeaders("foo"), ["bar", "baz"])


    def test_setdefaultDefault(self):
        """
        If a value is not passed to L{_DictHeaders.setdefault}, C{None} is
        used.
        """
        # This results in an invalid state for the headers, but maybe some
        # application is doing this an intermediate step towards some other
        # state.  Anyway, it was broken with the old implementation so it's
        # broken with the new implementation.  Compatibility, for the win.
        # -exarkun
        headers, wrapper = self.headers()
        self.assertIdentical(wrapper.setdefault("foo"), None)
        self.assertEqual(headers.getRawHeaders("foo"), [None])


    def test_dictComparison(self):
        """
        An instance of L{_DictHeaders} compares equal to a C{dict} which
        contains the same header/value pairs.  For header names with multiple
        values, the last value only is considered.
        """
        headers, wrapper = self.headers(foo=["lemur"], bar=["panda", "marmot"])
        self.assertNotEqual(wrapper, {"foo": "lemur", "bar": "panda"})
        self.assertEqual(wrapper, {"foo": "lemur", "bar": "marmot"})


    def test_otherComparison(self):
        """
        An instance of L{_DictHeaders} does not compare equal to other
        unrelated objects.
        """
        headers, wrapper = self.headers()
        self.assertNotEqual(wrapper, ())
        self.assertNotEqual(wrapper, object())
        self.assertNotEqual(wrapper, "foo")
