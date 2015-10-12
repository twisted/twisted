# Copyright (c) 2004-2007 Divmod.
# See LICENSE for details.

"""
Tests for L{twisted.python.url}.
"""

from __future__ import unicode_literals

from twisted.python.url import URL
from twisted.trial.unittest import TestCase
from twisted.python import url


theurl = "http://www.foo.com/a/nice/path/?zot=23&zut"

# Examples from RFC 3986 section 5.4, Reference Resolution Examples
rfc3986_relative_link_base = 'http://a/b/c/d;p?q'
rfc3986_relative_link_tests = [
    # "Normal"
    #('g:h', 'g:h'),     # Not supported:  scheme with relative path
    ('g', 'http://a/b/c/g'),
    ('./g', 'http://a/b/c/g'),
    ('g/', 'http://a/b/c/g/'),
    ('/g', 'http://a/g'),
    ('//g', 'http://g'),
    ('?y', 'http://a/b/c/d;p?y'),
    ('g?y', 'http://a/b/c/g?y'),
    ('#s', 'http://a/b/c/d;p?q#s'),
    ('g#s', 'http://a/b/c/g#s'),
    ('g?y#s', 'http://a/b/c/g?y#s'),
    (';x', 'http://a/b/c/;x'),
    ('g;x', 'http://a/b/c/g;x'),
    ('g;x?y#s', 'http://a/b/c/g;x?y#s'),
    ('', 'http://a/b/c/d;p?q'),
    ('.', 'http://a/b/c/'),
    ('./', 'http://a/b/c/'),
    ('..', 'http://a/b/'),
    ('../', 'http://a/b/'),
    ('../g', 'http://a/b/g'),
    ('../..', 'http://a/'),
    ('../../', 'http://a/'),
    ('../../g', 'http://a/g'),

    # Abnormal examples
    # ".." cannot be used to change the authority component of a URI
    ('../../../g', 'http://a/g'),
    ('../../../../g', 'http://a/g'),
    # "." and ".." when they are only part of a segment
    ('/./g', 'http://a/g'),
    ('/../g', 'http://a/g'),
    ('g.', 'http://a/b/c/g.'),
    ('.g', 'http://a/b/c/.g'),
    ('g..', 'http://a/b/c/g..'),
    ('..g', 'http://a/b/c/..g'),
    # unnecessary or nonsensical forms of "." and ".."
    ('./../g', 'http://a/b/g'),
    ('./g/.', 'http://a/b/c/g/'),
    ('g/./h', 'http://a/b/c/g/h'),
    ('g/../h', 'http://a/b/c/h'),
    ('g;x=1/./y', 'http://a/b/c/g;x=1/y'),
    ('g;x=1/../y', 'http://a/b/c/y'),
    # separating the reference's query and/or fragment components from the path
    ('g?y/./x', 'http://a/b/c/g?y/./x'),
    ('g?y/../x', 'http://a/b/c/g?y/../x'),
    ('g#s/./x', 'http://a/b/c/g#s/./x'),
    ('g#s/../x', 'http://a/b/c/g#s/../x'),

    # Not supported:  scheme with relative path
    #("http:g", "http:g"),              # strict
    #("http:g", "http://a/b/c/g"),      # non-strict
]


_percentenc = lambda s: ''.join('%%%02X' % ord(c) for c in s)

class TestURL(TestCase):
    """
    Tests for L{URL}.
    """

    def assertUnicoded(self, u):
        """
        The given L{URL}'s components should be L{unicode}.
        """
        self.assertTrue(isinstance(u.scheme, unicode)
                        or u.scheme is None, repr(u))
        self.assertTrue(isinstance(u.host, unicode)
                        or u.host is None, repr(u))
        for seg in u.pathSegments:
            self.assertTrue(isinstance(seg, unicode), repr(u))
        for (k, v) in u.queryParameters:
            self.assertTrue(isinstance(k, unicode), repr(u))
            self.assertTrue(v is None or isinstance(v, unicode), repr(u))
        self.assertTrue(isinstance(u.fragment, unicode), repr(u))


    def assertURL(self, u, scheme, host, pathSegments, queryParameters,
                  fragment, port):
        """
        The given L{URL} should have the given components.
        """
        actual = (u.scheme, u.host, u.pathSegments, u.queryParameters,
                  u.fragment, u.port)
        expected = (scheme, host, pathSegments, queryParameters, fragment,
                    port)
        self.assertEqual(actual, expected)


    def test_initDefaults(self):
        """
        L{URL} should have appropriate default values.
        """
        for u in [URL(u'http', u''),
                  URL(u'http', u'', None, None, None),
                  URL(u'http', u'', [u''], [], u'')]:
                  #URL('http', '', [''], [], '')]:
            self.assertUnicoded(u)
            self.assertURL(u, u'http', u'', [u''], [], u'', 80)


    def test_init(self):
        """
        L{URL} should accept L{unicode} parameters.
        """
        u = URL(u's', u'h', [u'p'], [(u'k', u'v'), (u'k', None)], u'f')
        self.assertUnicoded(u)
        self.assertURL(u, u's', u'h', [u'p'], [(u'k', u'v'), (u'k', None)],
                       u'f', None)

        self.assertURL(URL(u'http', u'\xe0', [u'\xe9'],
                           [(u'\u03bb', u'\u03c0')], u'\u22a5'),
                       u'http', u'\xe0', [u'\xe9'],
                       [(u'\u03bb', u'\u03c0')], u'\u22a5', 80)


    def test_initPercent(self):
        """
        L{URL} should accept (and not interpret) percent characters.
        """
        u = URL(u's', u'%68', [u'%70'], [(u'%6B', u'%76'), (u'%6B', None)], u'%66')
        self.assertUnicoded(u)
        self.assertURL(u,
                       u's', u'%68', [u'%70'],
                       [(u'%6B', u'%76'), (u'%6B', None)],
                       u'%66', None)


    def test_repr(self):
        """
        L{URL.__repr__} should return something meaningful.
        """
        self.assertEquals(
            repr(URL(scheme=u'http', host=u'foo', pathSegments=[u'bar'],
                     queryParameters=[(u'baz', None), (u'k', u'v')],
                     fragment=u'frob')),
            "URL(scheme=u'http', host=u'foo', pathSegments=[u'bar'], "
            "queryParameters=[(u'baz', None), (u'k', u'v')], fragment=u'frob', "
            "port=80)"
        )


    def test_fromText(self):
        """
        Round-tripping L{URL.fromText} with C{str} results in an equivalent
        URL.
        """
        urlpath = URL.fromText(theurl)
        self.assertEquals(theurl, urlpath.asText())


    def test_roundtrip(self):
        """
        L{URL.__str__} should invert L{URL.fromText}.
        """
        tests = (
            "http://localhost",
            "http://localhost/",
            "http://localhost/foo",
            "http://localhost/foo/",
            "http://localhost/foo!!bar/",
            "http://localhost/foo%20bar/",
            "http://localhost/foo%2Fbar/",
            "http://localhost/foo?n",
            "http://localhost/foo?n=v",
            "http://localhost/foo?n=/a/b",
            "http://example.com/foo!@$bar?b!@z=123",
            "http://localhost/asd?a=asd%20sdf/345",
            "http://(%2525)/(%2525)?(%2525)&(%2525)=(%2525)#(%2525)",
            "http://(%C3%A9)/(%C3%A9)?(%C3%A9)&(%C3%A9)=(%C3%A9)#(%C3%A9)",
            )
        for test in tests:
            result = URL.fromText(test).asText()
            self.assertEquals(test, result)


    def test_equality(self):
        """
        Two URLs decoded using L{URL.fromText} will only be equal if they
        decoded same URL string.
        """
        urlpath = URL.fromText(theurl)
        self.assertEquals(urlpath, URL.fromText(theurl))
        self.assertNotEquals(urlpath, URL.fromText('ftp://www.anotherinvaliddomain.com/foo/bar/baz/?zot=21&zut'))


    def test_fragmentEquality(self):
        """
        An URL created with the empty string for a fragment compares equal
        to an URL created with C{None} for a fragment.
        """
        self.assertEqual(URL(fragment=u''), URL(fragment=None))


    def test_child(self):
        urlpath = URL.fromText(theurl)
        self.assertEquals("http://www.foo.com/a/nice/path/gong?zot=23&zut",
                          urlpath.child(u'gong').asText())
        self.assertEquals("http://www.foo.com/a/nice/path/gong%2F?zot=23&zut",
                          urlpath.child(u'gong/').asText())
        self.assertEquals(
            "http://www.foo.com/a/nice/path/gong%2Fdouble?zot=23&zut",
            urlpath.child(u'gong/double').asText()
        )
        self.assertEquals(
            "http://www.foo.com/a/nice/path/gong%2Fdouble%2F?zot=23&zut",
            urlpath.child(u'gong/double/').asText()
        )


    def test_child_init_tuple(self):
        self.assertEquals(
            "http://www.foo.com/a/b/c",
            URL(host=u"www.foo.com",
                pathSegments=[u'a', u'b']).child(u"c").asText())

    def test_child_init_root(self):
        self.assertEquals(
            "http://www.foo.com/c",
            URL(host=u"www.foo.com").child(u"c").asText())

    def test_sibling(self):
        urlpath = URL.fromText(theurl)
        self.assertEquals(
            "http://www.foo.com/a/nice/path/sister?zot=23&zut",
            urlpath.sibling(u'sister').asText()
        )
        # use an url without trailing '/' to check child removal
        theurl2 = "http://www.foo.com/a/nice/path?zot=23&zut"
        urlpath = URL.fromText(theurl2)
        self.assertEquals(
            "http://www.foo.com/a/nice/sister?zot=23&zut",
            urlpath.sibling(u'sister').asText()
        )

    def test_click(self):
        urlpath = URL.fromText(theurl)
        # a null uri should be valid (return here)
        self.assertEquals("http://www.foo.com/a/nice/path/?zot=23&zut",
                          urlpath.click("").asText())
        # a simple relative path remove the query
        self.assertEquals("http://www.foo.com/a/nice/path/click",
                          urlpath.click("click").asText())
        # an absolute path replace path and query
        self.assertEquals("http://www.foo.com/click",
                          urlpath.click("/click").asText())
        # replace just the query
        self.assertEquals("http://www.foo.com/a/nice/path/?burp",
                          urlpath.click("?burp").asText())
        # one full url to another should not generate '//' between authority
        # and pathSegments
        self.failIfIn("//foobar",
                      urlpath.click('http://www.foo.com/foobar').asText())

        # from a url with no query clicking a url with a query,
        # the query should be handled properly
        u = URL.fromText('http://www.foo.com/me/noquery')
        self.failUnlessEqual('http://www.foo.com/me/17?spam=158',
                             u.click('/me/17?spam=158').asText())

        # Check that everything from the path onward is removed when the click
        # link has no path.
        u = URL.fromText('http://localhost/foo?abc=def')
        self.failUnlessEqual(u.click('http://www.python.org').asText(),
                             'http://www.python.org')


    def test_clickRFC3986(self):
        """
        L{URL.click} should correctly resolve the examples in RFC 3986.
        """
        base = URL.fromText(rfc3986_relative_link_base)
        for (ref, expected) in rfc3986_relative_link_tests:
            self.failUnlessEqual(base.click(ref).asText(), expected)


    def test_clickSchemeRelPath(self):
        """
        L{URL.click} should not accept schemes with relative paths.
        """
        base = URL.fromText(rfc3986_relative_link_base)
        self.assertRaises(NotImplementedError, base.click, 'g:h')
        self.assertRaises(NotImplementedError, base.click, 'http:h')


    def test_cloneUnchanged(self):
        """
        Verify that L{URL.replace} doesn't change any of the arguments it
        is passed.
        """
        urlpath = URL.fromText('https://x:1/y?z=1#A')
        self.assertEqual(
            urlpath.replace(urlpath.scheme,
                            urlpath.host,
                            urlpath.pathSegments,
                            urlpath.queryParameters,
                            urlpath.fragment,
                            urlpath.port),
            urlpath)
        self.assertEqual(
            urlpath.replace(),
            urlpath)


    def test_clickCollapse(self):
        tests = [
            ['http://localhost/', '.', 'http://localhost/'],
            ['http://localhost/', '..', 'http://localhost/'],
            ['http://localhost/a/b/c', '.', 'http://localhost/a/b/'],
            ['http://localhost/a/b/c', '..', 'http://localhost/a/'],
            ['http://localhost/a/b/c', './d/e', 'http://localhost/a/b/d/e'],
            ['http://localhost/a/b/c', '../d/e', 'http://localhost/a/d/e'],
            ['http://localhost/a/b/c', '/./d/e', 'http://localhost/d/e'],
            ['http://localhost/a/b/c', '/../d/e', 'http://localhost/d/e'],
            ['http://localhost/a/b/c/', '../../d/e/', 'http://localhost/a/d/e/'],
            ['http://localhost/a/./c', '../d/e', 'http://localhost/d/e'],
            ['http://localhost/a/./c/', '../d/e', 'http://localhost/a/d/e'],
            ['http://localhost/a/b/c/d', './e/../f/../g', 'http://localhost/a/b/c/g'],
            ['http://localhost/a/b/c', 'd//e', 'http://localhost/a/b/d//e'],
            ]
        for start, click, result in tests:
            self.assertEquals(
                URL.fromText(start).click(click).asText(),
                result
            )

    def test_add(self):
        urlpath = URL.fromText(theurl)
        self.assertEquals(
            "http://www.foo.com/a/nice/path/?zot=23&zut&burp",
            urlpath.query.add(u"burp").asText())
        self.assertEquals(
            "http://www.foo.com/a/nice/path/?zot=23&zut&burp=xxx",
            urlpath.query.add(u"burp", u"xxx").asText())
        self.assertEquals(
            "http://www.foo.com/a/nice/path/?zot=23&zut&burp=xxx&zing",
            urlpath.query.add(u"burp", u"xxx").query.add(u"zing").asText())
        # note the inversion!
        self.assertEquals(
            "http://www.foo.com/a/nice/path/?zot=23&zut&zing&burp=xxx",
            urlpath.query.add(u"zing").query.add(u"burp", u"xxx").asText())
        # note the two values for the same name
        self.assertEquals(
            "http://www.foo.com/a/nice/path/?zot=23&zut&burp=xxx&zot=32",
            urlpath.query.add(u"burp", u"xxx").query.add(u"zot", u'32')
            .asText())


    def test_add_noquery(self):
        # fromText is a different code path, test them both
        self.assertEquals(
            "http://www.foo.com/a/nice/path/?foo=bar",
            URL.fromText("http://www.foo.com/a/nice/path/")
            .query.add(u"foo", u"bar").asText())
        self.assertEquals(
            "http://www.foo.com/?foo=bar",
            URL(host=u"www.foo.com").query.add(u"foo", u"bar")
            .asText())


    def test_setQueryParam(self):
        urlpath = URL.fromText(theurl)
        self.assertEquals(
            "http://www.foo.com/a/nice/path/?zot=32&zut",
            urlpath.query.set(u"zot", u'32').asText())
        # replace name without value with name/value and vice-versa
        self.assertEquals(
            "http://www.foo.com/a/nice/path/?zot&zut=itworked",
            urlpath.query.set(u"zot").query.set(u"zut", u"itworked").asText()
        )
        # Q: what happens when the query has two values and we replace?
        # A: we replace both values with a single one
        self.assertEquals(
            "http://www.foo.com/a/nice/path/?zot=32&zut",
            urlpath.query.add(u"zot", u"xxx").query.set(u"zot", u'32').asText()
        )


    def test_clear(self):
        urlpath = URL.fromText(theurl)
        self.assertEquals(
            "http://www.foo.com/a/nice/path/",
            urlpath.query.clear().asText())


    def test_eq_same(self):
        u = URL.fromText('http://localhost/')
        self.failUnless(u == u, "%r != itself" % u)


    def test_eq_similar(self):
        u1 = URL.fromText('http://localhost/')
        u2 = URL.fromText('http://localhost/')
        self.failUnless(u1 == u2, "%r != %r" % (u1, u2))


    def test_eq_different(self):
        u1 = URL.fromText('http://localhost/a')
        u2 = URL.fromText('http://localhost/b')
        self.failIf(u1 == u2, "%r != %r" % (u1, u2))


    def test_eq_apples_vs_oranges(self):
        u = URL.fromText('http://localhost/')
        self.failIf(u == 42, "URL must not equal a number.")
        self.failIf(u == object(), "URL must not equal an object.")


    def test_ne_same(self):
        u = URL.fromText('http://localhost/')
        self.failIf(u != u, "%r == itself" % u)


    def test_ne_similar(self):
        u1 = URL.fromText('http://localhost/')
        u2 = URL.fromText('http://localhost/')
        self.failIf(u1 != u2, "%r == %r" % (u1, u2))


    def test_ne_different(self):
        u1 = URL.fromText('http://localhost/a')
        u2 = URL.fromText('http://localhost/b')
        self.failUnless(u1 != u2, "%r == %r" % (u1, u2))


    def test_ne_apples_vs_oranges(self):
        u = URL.fromText('http://localhost/')
        self.failUnless(u != 42, "URL must differ from a number.")
        self.failUnless(u != object(), "URL must be differ from an object.")


    def test_parseEqualInParamValue(self):
        u = URL.fromText('http://localhost/?=x=x=x')
        self.assertEqual(u.query.get(u''), ['x=x=x'])
        self.assertEqual(u.asText(), 'http://localhost/?=x%3Dx%3Dx')
        u = URL.fromText('http://localhost/?foo=x=x=x&bar=y')
        self.assertEqual(u.queryParameters, [('foo', 'x=x=x'),
                                             ('bar', 'y')])
        self.assertEqual(u.asText(), 'http://localhost/?foo=x%3Dx%3Dx&bar=y')
