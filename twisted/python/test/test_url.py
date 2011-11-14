# Copyright (c) 2004-2007 Divmod.
# See LICENSE for details.

"""
Tests for L{nevow.url}.
"""

import urlparse, urllib

from twisted.python.url import URL, iridecode, iriencode, IRIDecodeError
from twisted.trial.unittest import TestCase
from twisted.python import url


theurl = "http://www.foo.com:80/a/nice/path/?zot=23&zut"

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

class TestComponentCoding(TestCase):
    """
    Test basic encoding and decoding of URI/IRI components.
    """

    # 0x00 - 0x7F (unreserved subset)
    unreserved_dec = (u'abcdefghijklmnopqrstuvwxyz' +
                      u'ABCDEFGHIJKLMNOPQRSTUVWXYZ' +
                      u'0123456789' + u'-._~')
    unreserved_enc = unreserved_dec.encode('ascii')

    # 0x00 - 0x7F (maybe-reserved subset)
    otherASCII_dec = u''.join(sorted(set(map(unichr, range(0x80)))
                                     - set(unreserved_dec)))
    otherASCII_enc = _percentenc(otherASCII_dec.encode('ascii'))

    # 0x80 - 0xFF, non-ASCII octets
    nonASCII_dec = u''.join(map(unichr, range(0x80, 0x100)))
    nonASCII_enc = _percentenc(nonASCII_dec.encode('utf-8'))

    # non-octet Unicode codepoints
    nonOctet_dec = u'\u0100\u0800\U00010000'
    nonOctet_enc = _percentenc(nonOctet_dec.encode('utf-8'))

    # Random non-string types
    nonStrings = [5, lambda: 5, [], {}, object()]


    def assertMatches(self, x, y):
        """
        Like L{assertEquals}, but also require matching types.
        """
        self.assertEquals(type(x), type(y))
        self.assertEquals(x, y)


    def test_iriencode(self):
        """
        L{iriencode} should encode URI/IRI components (L{unicode} values)
        according to RFC 3986/3987.
        """
        for (dec, enc) in [(self.unreserved_dec, self.unreserved_enc),
                           (self.otherASCII_dec, self.otherASCII_enc),
                           (self.nonASCII_dec, self.nonASCII_enc),
                           (self.nonOctet_dec, self.nonOctet_enc)]:
            self.assertMatches(iriencode(dec), enc)
            self.assertMatches(iriencode(dec, unencoded=''), enc)


    def test_iriencodeUnencoded(self):
        """
        L{iriencode} should not percent-encode octets in C{unencoded}.
        """
        self.assertMatches(iriencode(u'_:_/_', unencoded=':'), '_:_%2F_')
        self.assertMatches(iriencode(u'_:_/_', unencoded='/'), '_%3A_/_')


    def test_iriencodeASCII(self):
        """
        L{iriencode} should accept ASCII-encoded L{str} values.
        """
        for (dec, enc) in [(self.unreserved_dec, self.unreserved_enc),
                           (self.otherASCII_dec, self.otherASCII_enc)]:
            self.assertMatches(iriencode(dec.encode('ascii')), enc)
            self.assertMatches(iriencode(dec.encode('ascii'), unencoded=''),
                               enc)


    def test_iridecode(self):
        """
        L{iridecode} should decode encoded URI/IRI components (L{unicode} or
        ASCII L{str} values) to unencoded L{unicode} according to RFC 3986/3987.
        """
        for (enc, dec) in [(self.unreserved_enc, self.unreserved_dec),
                           (self.otherASCII_enc, self.otherASCII_dec),
                           (self.nonASCII_enc, self.nonASCII_dec),
                           (self.nonOctet_enc, self.nonOctet_dec)]:
            self.assertMatches(iridecode(enc), dec)
            self.assertMatches(iridecode(enc.decode('ascii')), dec)


    def test_iridecodeNonPercent(self):
        """
        L{iridecode} should return non-percent-encoded values as-is.
        """
        for dec in [self.unreserved_dec, self.otherASCII_dec.replace('%', ''),
                    self.nonASCII_dec, self.nonOctet_dec]:
            self.assertMatches(iridecode(dec), dec)


    def test_iridecodeIRIDecodeError(self):
        """
        L{iridecode} should raise L{IRIDecodeError} for percent-encoded
        sequences that do not describe valid UTF-8.
        """
        for s in [u'r%E9sum%E9', u'D%FCrst']:
            self.assertRaises(IRIDecodeError, iridecode, s)
            self.assertRaises(IRIDecodeError, iridecode, s.decode('ascii'))


    def test_nonASCII(self):
        """
        L{iriencode} and L{iridecode} should not try to interpret non-ASCII
        L{str} values.
        """
        for s in [self.nonASCII_dec.encode('latin1'),
                  self.nonASCII_dec.encode('utf-8'),
                  self.nonOctet_dec.encode('utf-8')]:
            self.assertRaises(UnicodeDecodeError, iriencode, s)
            self.assertRaises(UnicodeDecodeError, iridecode, s)


    def test_nonString(self):
        """
        L{iriencode} and L{iridecode} should raise L{TypeError} for non-string
        values.
        """
        for x in self.nonStrings:
            self.assertRaises(TypeError, iridecode, x)
            self.assertRaises(TypeError, iriencode, x)


    def test_doubleEncode(self):
        """
        Encoding and decoding an already-encoded value should not change it.
        """
        for dec in [self.unreserved_dec, self.otherASCII_dec,
                    self.nonASCII_dec, self.nonOctet_dec]:
            enc = iriencode(dec)
            uenc = enc.decode('ascii')
            self.assertMatches(iridecode(iriencode(uenc)), uenc)
            self.assertMatches(iridecode(iriencode(enc)), uenc)


    def test_iriencodePath(self):
        """
        L{url.iriencodePath} should not percent-encode characters not reserved
        in path segments.
        """
        self.assertMatches(url.iriencodePath(url.gen_delims+url.sub_delims),
                           ":%2F%3F%23%5B%5D@!$&'()*+,;=")


    def test_iriencodeQuery(self):
        """
        L{url.iriencodeQuery} should not percent-encode characters not reserved
        in x-www-form-urlencoded queries.
        """
        self.assertMatches(url.iriencodeQuery(url.gen_delims+url.sub_delims),
                           ":/?%23%5B%5D@!$%26'()*%2B,;%3D")


    def test_iriencodeFragment(self):
        """
        L{url.iriencodeFragment} should not percent-encode characters not reserved
        in fragment components.
        """
        self.assertMatches(url.iriencodeFragment(url.gen_delims+url.sub_delims),
                           ":/?%23%5B%5D@!$&'()*+,;=")


    # Examples for querify/unquerify.
    queryPairs = [('=', [('', '')]),
                  ('==', [('', '=')]),
                  ('k', [('k', None)]),
                  ('k=', [('k', '')]),
                  ('k=v', [('k', 'v')]),
                  ('%26', [('%26', None)]),
                  ('%3D', [('%3D', None)]),
                  ('%26=%3D', [('%26', '%3D')]),
                  ('%3D=%26', [('%3D', '%26')]),
                  ('%2B=%2B', [('%2B', '%2B')])]


    def test_querify(self):
        """
        L{url.querify} should compose x-www-form-urlencoded strings.
        """
        for (q, p) in self.queryPairs:
            self.assertEquals(url.querify(p), q)
            for (q2, p2) in self.queryPairs:
                self.assertEquals(url.querify(p+p2), q+'&'+q2)


    def test_unquerify(self):
        """
        L{url.unquerify} should decompose x-www-form-urlencoded strings.
        """
        for (q, p) in self.queryPairs:
            self.assertEquals(url.unquerify(q), p)
            for (q2, p2) in self.queryPairs:
                self.assertEquals(url.unquerify(q+'&'+q2), p+p2)


    def test_querifyEmpty(self):
        """
        L{url.querify} should coalesce empty fields.
        """
        for p in [[], [('', None)], [('', None), ('', None)]]:
            self.assertEquals(url.querify(p), '')


    def test_unquerifyEmpty(self):
        """
        L{url.unquerify} should coalesce empty fields.
        """
        for q in ['', '&', '&&']:
            self.assertEquals(url.unquerify(q), [])


    def test_unquerifyPlus(self):
        """
        L{url.unquerify} should replace C{'+'} with C{' '}.
        """
        self.assertEquals(url.unquerify('foo=bar+baz'), [('foo', 'bar baz')])


    # Examples for parseIRI/unparseIRI.
    uriParses = [
        ('', (u'', u'', [u''], [], u'')),
        ('/', (u'', u'', [u'', u''], [], u'')),
        ('foo', (u'', u'', [u'foo'], [], u'')),
        ('/foo', (u'', u'', [u'', u'foo'], [], u'')),
        ('foo/', (u'', u'', [u'foo', u''], [], u'')),
        ('http://foo', (u'http', u'foo', [u''], [], u'')),
        ('http://foo/', (u'http', u'foo', [u'', u''], [], u'')),
        ('http://foo/p#f', (u'http', u'foo', [u'', u'p'], [], u'f')),
        ('http://foo/p/p?q&q=q#f', (u'http', u'foo', [u'', u'p', u'p'],
                                    [(u'q', None), (u'q', u'q')], u'f')),
        (theurl, (u'http', u'www.foo.com:80',
                  [u'', u'a', u'nice', u'path', u''],
                  [(u'zot', u'23'), (u'zut', None)], u'')),
        # nesting
        ('http://foo/p?q=http://foo/p?q%26q%3Dq%23f&@=:#g',
         (u'http', u'foo', [u'', u'p'],
          [(u'q', u'http://foo/p?q&q=q#f'), ('@',':')], u'g')),
        # idna-decoding
        ('http://xn--n3h.com/%2525/%2525?%2525&%2525=%2525#%2525',
         (u'http', u'\N{SNOWMAN}.com', [u'', u'%25', u'%25'],
          [(u'%25', None), (u'%25', u'%25')], u'%25')),
        # UTF-8 decoding
        ('http://xn--n3h/%C3%A9/%C3%A9?%C3%A9&%C3%A9=%C3%A9#%C3%A9',
         (u'http', u'\N{SNOWMAN}', [u'', u'\xe9', u'\xe9'],
          [(u'\xe9', None), (u'\xe9', u'\xe9')], u'\xe9')),
    ]


    def test_parseIRI(self):
        """
        L{url.parseIRI} should parse and decode URIs and URI-encoded IRIs.
        """
        for (s, p) in self.uriParses:
            self.assertEquals(url.parseIRI(s), p)


    def test_parseIRIUnicode(self):
        """
        L{url.parseIRI} should parse and decode L{unicode} IRIs.
        """
        for (s, p) in self.uriParses:
            self.assertEquals(url.parseIRI(s.decode('ascii')), p)
        self.assertEquals(
            url.parseIRI(u'http://xn--9ca/\xe9/\xe9?\xe9&\xe9=\xe9#\xe9'),
            (u'http', u'\xe9', [u'', u'\xe9', u'\xe9'],
             [(u'\xe9', None), (u'\xe9', u'\xe9')], u'\xe9'))


    def test_unparseIRI(self):
        """
        L{url.unparseIRI} should encode and format IRI components.
        """
        for (s, p) in self.uriParses:
            self.assertMatches(url.unparseIRI(p), s)


    def test_parseIDNAHostname(self):
        """
        L{url.parseIRI} will decode hostnames using IDNA.
        """
        _, netloc, _, _, _ = url.parseIRI("http://xn--n3h.com/")
        self.assertEqual(netloc, u"\N{SNOWMAN}.com")


    def test_unparseIDNAHostname(self):
        """
        L{url.unparseIRI} will encode hostnames using IDNA.
        """
        result = url.unparseIRI((u'http', u"\N{SNOWMAN}.com", [u"", u""], u"", u""))
        self.assertEqual(result, "http://xn--n3h.com/")



class _IncompatibleSignatureURL(URL):
    """
    A test fixture for verifying that subclasses which override C{cloneURL}
    won't be copied by any other means (e.g. constructing C{self.__class___}
    directly).  It accomplishes this by having a constructor signature which
    is incompatible with L{URL}'s.
    """
    def __init__(
        self, magicValue, scheme, netloc, pathsegs, querysegs, fragment):
        URL.__init__(self, scheme, netloc, pathsegs, querysegs, fragment)
        self.magicValue = magicValue


    def cloneURL(self, scheme, netloc, pathsegs, querysegs, fragment):
        """
        Override the base implementation to pass along C{self.magicValue}.
        """
        return self.__class__(
            self.magicValue, scheme, netloc, pathsegs, querysegs, fragment)



class TestURL(TestCase):
    """
    Tests for L{URL}.
    """

    def assertUnicoded(self, u):
        """
        The given L{URL}'s components should be L{unicode}.
        """
        self.assertTrue(isinstance(u.scheme, unicode), repr(u))
        self.assertTrue(isinstance(u.netloc, unicode), repr(u))
        for seg in u.pathList():
            self.assertTrue(isinstance(seg, unicode), repr(u))
        for (k, v) in u.queryList():
            self.assertTrue(isinstance(k, unicode), repr(u))
            self.assertTrue(v is None or isinstance(v, unicode), repr(u))
        self.assertTrue(isinstance(u.fragment, unicode), repr(u))


    def assertURL(self, u, scheme, netloc, pathsegs, querysegs, fragment):
        """
        The given L{URL} should have the given components.
        """
        self.assertEqual(
            (u.scheme, u.netloc, u.pathList(), u.queryList(), u.fragment),
            (scheme, netloc, pathsegs, querysegs, fragment))


    def test_initDefaults(self):
        """
        L{URL} should have appropriate default values.
        """
        for u in [URL(),
                  URL(u'http', u'', None, None, None),
                  URL(u'http', u'', [u''], [], u'')]:
                  #URL('http', '', [''], [], '')]:
            self.assertUnicoded(u)
            self.assertURL(u, u'http', u'', [u''], [], u'')


    def test_init(self):
        """
        L{URL} should accept L{unicode} parameters.
        """
        u = URL(u's', u'h', [u'p'], [(u'k', u'v'), (u'k', None)], u'f')
        self.assertUnicoded(u)
        self.assertURL(u, u's', u'h', [u'p'], [(u'k', u'v'), (u'k', None)], u'f')

        self.assertURL(URL(u'http', u'\xe0', [u'\xe9'],
                           [(u'\u03bb', u'\u03c0')], u'\u22a5'),
                       u'http', u'\xe0', [u'\xe9'],
                       [(u'\u03bb', u'\u03c0')], u'\u22a5')


    def test_initPercent(self):
        """
        L{URL} should accept (and not interpret) percent characters.
        """
        u = URL(u's', u'%68', [u'%70'], [(u'%6B', u'%76'), (u'%6B', None)], u'%66')
        self.assertUnicoded(u)
        self.assertURL(u, u's', u'%68', [u'%70'], [(u'%6B', u'%76'), (u'%6B', None)], u'%66')


    def test_repr(self):
        """
        L{URL.__repr__} should return something meaningful.
        """
        self.assertEquals(
            repr(URL(scheme=u'http', netloc=u'foo', pathsegs=[u'bar'],
                     querysegs=[(u'baz', None), (u'k', u'v')], fragment=u'frob')),
            "URL(scheme=u'http', netloc=u'foo', pathsegs=[u'bar'], "
                "querysegs=[(u'baz', None), (u'k', u'v')], fragment=u'frob')")


    def test_fromString(self):
        """
        Round-tripping L{URL.fromString} with C{str} results in an equivalent
        URL.
        """
        urlpath = URL.fromString(theurl)
        self.assertEquals(theurl, str(urlpath))


    def test_roundtrip(self):
        """
        L{URL.__str__} should invert L{URL.fromString}.
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
            result = str(URL.fromString(test))
            self.assertEquals(test, result)


    def test_equality(self):
        """
        Two URLs decoded using L{URL.fromString} will only be equal if they
        decoded same URL string.
        """
        urlpath = URL.fromString(theurl)
        self.assertEquals(urlpath, URL.fromString(theurl))
        self.assertNotEquals(urlpath, URL.fromString('ftp://www.anotherinvaliddomain.com/foo/bar/baz/?zot=21&zut'))


    def test_fragmentEquality(self):
        """
        An URL created with the empty string for a fragment compares equal
        to an URL created with C{None} for a fragment.
        """
        self.assertEqual(URL(fragment=u''), URL(fragment=None))


    def test_path(self):
        """
        L{URL.path} should be a C{str} giving the I{path} portion of the URL
        only.  Certain bytes should not be quoted.
        """
        urlpath = URL.fromString("http://example.com/foo/bar?baz=quux#foobar")
        self.assertEqual(urlpath.path, "foo/bar")
        urlpath = URL.fromString("http://example.com/foo%2Fbar?baz=quux#foobar")
        self.assertEqual(urlpath.path, "foo%2Fbar")
        urlpath = URL.fromString("http://example.com/-_.!*'()?baz=quux#foo")
        self.assertEqual(urlpath.path, "-_.!*'()")


    def test_pathList(self):
        """
        L{URL.pathList} should return C{self.pathsegs}, copied or not.
        """
        u = URL(pathsegs=[u'foo'])
        for segs in [u.pathList(), u.pathList(copy=True)]:
            self.assertEquals(segs, u.pathsegs)
            self.assertNotIdentical(segs, u.pathsegs)
        self.assertIdentical(u.pathList(copy=False), u.pathsegs)


    def test_parentdir(self):
        """
        XXX add explicit encoding to str().
        """
        urlpath = URL.fromString(theurl)
        self.assertEquals("http://www.foo.com:80/a/nice/?zot=23&zut",
                          str(urlpath.parentdir()))
        urlpath = URL.fromString('http://www.foo.com/a')
        self.assertEquals("http://www.foo.com/",
                          str(urlpath.parentdir()))
        urlpath = URL.fromString('http://www.foo.com/a/')
        self.assertEquals("http://www.foo.com/",
                          str(urlpath.parentdir()))
        urlpath = URL.fromString('http://www.foo.com/a/b')
        self.assertEquals("http://www.foo.com/",
                          str(urlpath.parentdir()))
        urlpath = URL.fromString('http://www.foo.com/a/b/')
        self.assertEquals("http://www.foo.com/a/",
                          str(urlpath.parentdir()))
        urlpath = URL.fromString('http://www.foo.com/a/b/c')
        self.assertEquals("http://www.foo.com/a/",
                          str(urlpath.parentdir()))
        urlpath = URL.fromString('http://www.foo.com/a/b/c/')
        self.assertEquals("http://www.foo.com/a/b/",
                          str(urlpath.parentdir()))
        urlpath = URL.fromString('http://www.foo.com/a/b/c/d')
        self.assertEquals("http://www.foo.com/a/b/",
                          str(urlpath.parentdir()))
        urlpath = URL.fromString('http://www.foo.com/a/b/c/d/')
        self.assertEquals("http://www.foo.com/a/b/c/",
                          str(urlpath.parentdir()))

    def test_parent_root(self):
        urlpath = URL.fromString('http://www.foo.com/')
        self.assertEquals("http://www.foo.com/",
                          str(urlpath.parentdir()))
        self.assertEquals("http://www.foo.com/",
                          str(urlpath.parentdir().parentdir()))

    def test_child(self):
        urlpath = URL.fromString(theurl)
        self.assertEquals("http://www.foo.com:80/a/nice/path/gong?zot=23&zut",
                          str(urlpath.child(u'gong')))
        self.assertEquals("http://www.foo.com:80/a/nice/path/gong%2F?zot=23&zut",
                          str(urlpath.child(u'gong/')))
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/gong%2Fdouble?zot=23&zut",
            str(urlpath.child(u'gong/double')))
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/gong%2Fdouble%2F?zot=23&zut",
            str(urlpath.child(u'gong/double/')))

    def test_child_init_tuple(self):
        self.assertEquals(
            "http://www.foo.com/a/b/c",
            str(URL(netloc=u"www.foo.com",
                        pathsegs=[u'a', u'b']).child(u"c")))

    def test_child_init_root(self):
        self.assertEquals(
            "http://www.foo.com/c",
            str(URL(netloc=u"www.foo.com").child(u"c")))

    def test_sibling(self):
        urlpath = URL.fromString(theurl)
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/sister?zot=23&zut",
            str(urlpath.sibling(u'sister')))
        # use an url without trailing '/' to check child removal
        theurl2 = "http://www.foo.com:80/a/nice/path?zot=23&zut"
        urlpath = URL.fromString(theurl2)
        self.assertEquals(
            "http://www.foo.com:80/a/nice/sister?zot=23&zut",
            str(urlpath.sibling(u'sister')))

    def test_curdir(self):
        urlpath = URL.fromString(theurl)
        self.assertEquals(theurl, str(urlpath))
        # use an url without trailing '/' to check object removal
        theurl2 = "http://www.foo.com:80/a/nice/path?zot=23&zut"
        urlpath = URL.fromString(theurl2)
        self.assertEquals("http://www.foo.com:80/a/nice/?zot=23&zut",
                          str(urlpath.curdir()))

    def test_click(self):
        urlpath = URL.fromString(theurl)
        # a null uri should be valid (return here)
        self.assertEquals("http://www.foo.com:80/a/nice/path/?zot=23&zut",
                          str(urlpath.click("")))
        # a simple relative path remove the query
        self.assertEquals("http://www.foo.com:80/a/nice/path/click",
                          str(urlpath.click("click")))
        # an absolute path replace path and query
        self.assertEquals("http://www.foo.com:80/click",
                          str(urlpath.click("/click")))
        # replace just the query
        self.assertEquals("http://www.foo.com:80/a/nice/path/?burp",
                          str(urlpath.click("?burp")))
        # one full url to another should not generate '//' between netloc and pathsegs
        self.failIfIn("//foobar", str(urlpath.click('http://www.foo.com:80/foobar')))

        # from a url with no query clicking a url with a query,
        # the query should be handled properly
        u = URL.fromString('http://www.foo.com:80/me/noquery')
        self.failUnlessEqual('http://www.foo.com:80/me/17?spam=158',
                             str(u.click('/me/17?spam=158')))

        # Check that everything from the path onward is removed when the click link
        # has no path.
        u = URL.fromString('http://localhost/foo?abc=def')
        self.failUnlessEqual(str(u.click('http://www.python.org')),
                             'http://www.python.org')


    def test_clickDecode(self):
        """
        L{URL.click} should decode the reference.
        """
        s = ''.join(map(chr, range(0x80)))
        u = URL.fromString('http://example.com/').click(url.iriencodePath(s))
        self.assertEqual(u.pathList(), [s])


    def test_clickRFC3986(self):
        """
        L{URL.click} should correctly resolve the examples in RFC 3986.
        """
        base = URL.fromString(rfc3986_relative_link_base)
        for (ref, result) in rfc3986_relative_link_tests:
            self.failUnlessEqual(str(base.click(ref)), result)


    def test_clickSchemeRelPath(self):
        """
        L{URL.click} should not accept schemes with relative paths.
        """
        base = URL.fromString(rfc3986_relative_link_base)
        self.assertRaises(NotImplementedError, base.click, 'g:h')
        self.assertRaises(NotImplementedError, base.click, 'http:h')


    def test_cloneUnchanged(self):
        """
        Verify that L{URL.cloneURL} doesn't change any of the arguments it
        is passed.
        """
        urlpath = URL.fromString('https://x:1/y?z=1#A')
        self.assertEqual(
            urlpath.cloneURL(urlpath.scheme,
                             urlpath.netloc,
                             urlpath.pathsegs,
                             urlpath.querysegs,
                             urlpath.fragment),
            urlpath)


    def _makeIncompatibleSignatureURL(self, magicValue):
        return _IncompatibleSignatureURL(magicValue, u'', u'', None, None, u'')


    def test_clickCloning(self):
        """
        Verify that L{URL.click} uses L{URL.cloneURL} to construct its
        return value.
        """
        urlpath = self._makeIncompatibleSignatureURL(8789)
        self.assertEqual(urlpath.click('/').magicValue, 8789)


    def test_clickCloningScheme(self):
        """
        Verify that L{URL.click} uses L{URL.cloneURL} to construct its
        return value, when the clicked url has a scheme.
        """
        urlpath = self._makeIncompatibleSignatureURL(8031)
        self.assertEqual(urlpath.click('https://foo').magicValue, 8031)


    def test_addCloning(self):
        """
        Verify that L{URL.add} uses L{URL.cloneURL} to construct its
        return value.
        """
        urlpath = self._makeIncompatibleSignatureURL(8789)
        self.assertEqual(urlpath.add(u'x').magicValue, 8789)


    def test_replaceCloning(self):
        """
        Verify that L{URL.replace} uses L{URL.cloneURL} to construct
        its return value.
        """
        urlpath = self._makeIncompatibleSignatureURL(8789)
        self.assertEqual(urlpath.replace(u'x').magicValue, 8789)


    def test_removeCloning(self):
        """
        Verify that L{URL.remove} uses L{URL.cloneURL} to construct
        its return value.
        """
        urlpath = self._makeIncompatibleSignatureURL(8789)
        self.assertEqual(urlpath.remove(u'x').magicValue, 8789)


    def test_clearCloning(self):
        """
        Verify that L{URL.clear} uses L{URL.cloneURL} to construct its
        return value.
        """
        urlpath = self._makeIncompatibleSignatureURL(8789)
        self.assertEqual(urlpath.clear().magicValue, 8789)


    def test_anchorCloning(self):
        """
        Verify that L{URL.anchor} uses L{URL.cloneURL} to construct
        its return value.
        """
        urlpath = self._makeIncompatibleSignatureURL(8789)
        self.assertEqual(urlpath.anchor().magicValue, 8789)


    def test_secureCloning(self):
        """
        Verify that L{URL.secure} uses L{URL.cloneURL} to construct its
        return value.
        """
        urlpath = self._makeIncompatibleSignatureURL(8789)
        self.assertEqual(urlpath.secure().magicValue, 8789)


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
                str(URL.fromString(start).click(click)),
                result
                )

    def test_add(self):
        urlpath = URL.fromString(theurl)
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=23&zut&burp",
            str(urlpath.add(u"burp")))
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=23&zut&burp=xxx",
            str(urlpath.add(u"burp", u"xxx")))
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=23&zut&burp=xxx&zing",
            str(urlpath.add(u"burp", u"xxx").add(u"zing")))
        # note the inversion!
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=23&zut&zing&burp=xxx",
            str(urlpath.add(u"zing").add(u"burp", u"xxx")))
        # note the two values for the same name
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=23&zut&burp=xxx&zot=32",
            str(urlpath.add(u"burp", u"xxx").add(u"zot", u'32')))


    def test_add_noquery(self):
        # fromString is a different code path, test them both
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?foo=bar",
            str(URL.fromString("http://www.foo.com:80/a/nice/path/")
                .add(u"foo", u"bar")))
        self.assertEquals(
            "http://www.foo.com/?foo=bar",
            str(URL(netloc=u"www.foo.com").add(u"foo", u"bar")))


    def test_replace(self):
        urlpath = URL.fromString(theurl)
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=32&zut",
            str(urlpath.replace(u"zot", u'32')))
        # replace name without value with name/value and vice-versa
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot&zut=itworked",
            str(urlpath.replace(u"zot").replace(u"zut", u"itworked")))
        # Q: what happens when the query has two values and we replace?
        # A: we replace both values with a single one
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=32&zut",
            str(urlpath.add(u"zot", u"xxx").replace(u"zot", u'32')))


    def test_fragment(self):
        urlpath = URL.fromString(theurl)
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=23&zut#hiboy",
            str(urlpath.anchor(u"hiboy")))
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=23&zut",
            str(urlpath.anchor()))
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=23&zut",
            str(urlpath.anchor(u'')))


    def test_clear(self):
        urlpath = URL.fromString(theurl)
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zut",
            str(urlpath.clear(u"zot")))
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zot=23",
            str(urlpath.clear(u"zut")))
        # something stranger, query with two values, both should get cleared
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/?zut",
            str(urlpath.add(u"zot", u"1971").clear(u"zot")))
        # two ways to clear the whole query
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/",
            str(urlpath.clear(u"zut").clear(u"zot")))
        self.assertEquals(
            "http://www.foo.com:80/a/nice/path/",
            str(urlpath.clear()))


    def test_secure(self):
        self.assertEquals(str(URL.fromString('http://localhost/').secure()), 'https://localhost/')
        self.assertEquals(str(URL.fromString('http://localhost/').secure(True)), 'https://localhost/')
        self.assertEquals(str(URL.fromString('https://localhost/').secure()), 'https://localhost/')
        self.assertEquals(str(URL.fromString('https://localhost/').secure(False)), 'http://localhost/')
        self.assertEquals(str(URL.fromString('http://localhost/').secure(False)), 'http://localhost/')
        self.assertEquals(str(URL.fromString('http://localhost/foo').secure()), 'https://localhost/foo')
        self.assertEquals(str(URL.fromString('http://localhost/foo?bar=1').secure()), 'https://localhost/foo?bar=1')
        self.assertEquals(str(URL.fromString('http://localhost/').secure(port=443)), 'https://localhost/')
        self.assertEquals(str(URL.fromString('http://localhost:8080/').secure(port=8443)), 'https://localhost:8443/')
        self.assertEquals(str(URL.fromString('https://localhost:8443/').secure(False, 8080)), 'http://localhost:8080/')


    def test_eq_same(self):
        u = URL.fromString('http://localhost/')
        self.failUnless(u == u, "%r != itself" % u)


    def test_eq_similar(self):
        u1 = URL.fromString('http://localhost/')
        u2 = URL.fromString('http://localhost/')
        self.failUnless(u1 == u2, "%r != %r" % (u1, u2))


    def test_eq_different(self):
        u1 = URL.fromString('http://localhost/a')
        u2 = URL.fromString('http://localhost/b')
        self.failIf(u1 == u2, "%r != %r" % (u1, u2))


    def test_eq_apples_vs_oranges(self):
        u = URL.fromString('http://localhost/')
        self.failIf(u == 42, "URL must not equal a number.")
        self.failIf(u == object(), "URL must not equal an object.")


    def test_ne_same(self):
        u = URL.fromString('http://localhost/')
        self.failIf(u != u, "%r == itself" % u)


    def test_ne_similar(self):
        u1 = URL.fromString('http://localhost/')
        u2 = URL.fromString('http://localhost/')
        self.failIf(u1 != u2, "%r == %r" % (u1, u2))


    def test_ne_different(self):
        u1 = URL.fromString('http://localhost/a')
        u2 = URL.fromString('http://localhost/b')
        self.failUnless(u1 != u2, "%r == %r" % (u1, u2))


    def test_ne_apples_vs_oranges(self):
        u = URL.fromString('http://localhost/')
        self.failUnless(u != 42, "URL must differ from a number.")
        self.failUnless(u != object(), "URL must be differ from an object.")


    def test_parseEqualInParamValue(self):
        u = URL.fromString('http://localhost/?=x=x=x')
        self.failUnless(u.query == ['=x=x=x'])
        self.failUnless(str(u) == 'http://localhost/?=x%3Dx%3Dx')
        u = URL.fromString('http://localhost/?foo=x=x=x&bar=y')
        self.failUnless(u.query == ['foo=x=x=x', 'bar=y'])
        self.failUnless(str(u) == 'http://localhost/?foo=x%3Dx%3Dx&bar=y')
