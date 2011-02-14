# -*- test-case-name: twisted.web2.test.test_http_headers -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP header representation, parsing, and serialization.
"""

import time
from calendar import timegm
import base64
import re

def dashCapitalize(s):
    ''' Capitalize a string, making sure to treat - as a word seperator '''
    return '-'.join([ x.capitalize() for x in s.split('-')])

# datetime parsing and formatting
weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
weekdayname_lower = [name.lower() for name in weekdayname]
monthname = [None,
             'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
monthname_lower = [name and name.lower() for name in monthname]

# HTTP Header parsing API

header_case_mapping = {}

def casemappingify(d):
    global header_case_mapping
    newd = dict([(key.lower(),key) for key in d.keys()])
    header_case_mapping.update(newd)

def lowerify(d):
    return dict([(key.lower(),value) for key,value in d.items()])


class HeaderHandler(object):
    """HeaderHandler manages header generating and parsing functions.
    """
    HTTPParsers = {}
    HTTPGenerators = {}

    def __init__(self, parsers=None, generators=None):
        """
        @param parsers: A map of header names to parsing functions.
        @type parsers: L{dict}

        @param generators: A map of header names to generating functions.
        @type generators: L{dict}
        """

        if parsers:
            self.HTTPParsers.update(parsers)
        if generators:
            self.HTTPGenerators.update(generators)

    def parse(self, name, header):
        """
        Parse the given header based on its given name.

        @param name: The header name to parse.
        @type name: C{str}

        @param header: A list of unparsed headers.
        @type header: C{list} of C{str}

        @return: The return value is the parsed header representation,
            it is dependent on the header.  See the HTTP Headers document.
        """
        parser = self.HTTPParsers.get(name, None)
        if parser is None:
            raise ValueError("No header parser for header '%s', either add one or use getHeaderRaw." % (name,))

        try:
            for p in parser:
                # print "Parsing %s: %s(%s)" % (name, repr(p), repr(h))
                header = p(header)
                # if isinstance(h, types.GeneratorType):
                #     h=list(h)
        except ValueError,v:
            # print v
            header=None

        return header

    def generate(self, name, header):
        """
        Generate the given header based on its given name.

        @param name: The header name to generate.
        @type name: C{str}

        @param header: A parsed header, such as the output of
            L{HeaderHandler}.parse.

        @return: C{list} of C{str} each representing a generated HTTP header.
        """
        generator = self.HTTPGenerators.get(name, None)

        if generator is None:
            # print self.generators
            raise ValueError("No header generator for header '%s', either add one or use setHeaderRaw." % (name,))

        for g in generator:
            header = g(header)

        #self._raw_headers[name] = h
        return header

    def updateParsers(self, parsers):
        """Update en masse the parser maps.

        @param parsers: Map of header names to parser chains.
        @type parsers: C{dict}
        """
        casemappingify(parsers)
        self.HTTPParsers.update(lowerify(parsers))

    def addParser(self, name, value):
        """Add an individual parser chain for the given header.

        @param name: Name of the header to add
        @type name: C{str}

        @param value: The parser chain
        @type value: C{str}
        """
        self.updateParsers({name: value})

    def updateGenerators(self, generators):
        """Update en masse the generator maps.

        @param parsers: Map of header names to generator chains.
        @type parsers: C{dict}
        """
        casemappingify(generators)
        self.HTTPGenerators.update(lowerify(generators))

    def addGenerators(self, name, value):
        """Add an individual generator chain for the given header.

        @param name: Name of the header to add
        @type name: C{str}

        @param value: The generator chain
        @type value: C{str}
        """
        self.updateGenerators({name: value})

    def update(self, parsers, generators):
        """Conveniently update parsers and generators all at once.
        """
        self.updateParsers(parsers)
        self.updateGenerators(generators)


DefaultHTTPHandler = HeaderHandler()


## HTTP DateTime parser
def parseDateTime(dateString):
    """Convert an HTTP date string (one of three formats) to seconds since epoch."""
    parts = dateString.split()

    if not parts[0][0:3].lower() in weekdayname_lower:
        # Weekday is stupid. Might have been omitted.
        try:
            return parseDateTime("Sun, "+dateString)
        except ValueError:
            # Guess not.
            pass

    partlen = len(parts)
    if (partlen == 5 or partlen == 6) and parts[1].isdigit():
        # 1st date format: Sun, 06 Nov 1994 08:49:37 GMT
        # (Note: "GMT" is literal, not a variable timezone)
        # (also handles without "GMT")
        # This is the normal format
        day = parts[1]
        month = parts[2]
        year = parts[3]
        time = parts[4]
    elif (partlen == 3 or partlen == 4) and parts[1].find('-') != -1:
        # 2nd date format: Sunday, 06-Nov-94 08:49:37 GMT
        # (Note: "GMT" is literal, not a variable timezone)
        # (also handles without without "GMT")
        # Two digit year, yucko.
        day, month, year = parts[1].split('-')
        time = parts[2]
        year=int(year)
        if year < 69:
            year = year + 2000
        elif year < 100:
            year = year + 1900
    elif len(parts) == 5:
        # 3rd date format: Sun Nov  6 08:49:37 1994
        # ANSI C asctime() format.
        day = parts[2]
        month = parts[1]
        year = parts[4]
        time = parts[3]
    else:
        raise ValueError("Unknown datetime format %r" % dateString)

    day = int(day)
    month = int(monthname_lower.index(month.lower()))
    year = int(year)
    hour, min, sec = map(int, time.split(':'))
    return int(timegm((year, month, day, hour, min, sec)))


##### HTTP tokenizer
class Token(str):
    __slots__=[]
    tokens = {}
    def __new__(self, char):
        token = Token.tokens.get(char)
        if token is None:
            Token.tokens[char] = token = str.__new__(self, char)
        return token

    def __repr__(self):
        return "Token(%s)" % str.__repr__(self)


# RFC 2616 section 2.2
http_tokens = " \t\"()<>@,;:\\/[]?={}"
http_ctls = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f"

def tokenize(header, foldCase=True):
    """Tokenize a string according to normal HTTP header parsing rules.

    In particular:
     - Whitespace is irrelevant and eaten next to special separator tokens.
       Its existance (but not amount) is important between character strings.
     - Quoted string support including embedded backslashes.
     - Case is insignificant (and thus lowercased), except in quoted strings.
        (unless foldCase=False)
     - Multiple headers are concatenated with ','

    NOTE: not all headers can be parsed with this function.

    Takes a raw header value (list of strings), and
    Returns a generator of strings and Token class instances.
    """
    tokens=http_tokens
    ctls=http_ctls

    string = ",".join(header)
    list = []
    start = 0
    cur = 0
    quoted = False
    qpair = False
    inSpaces = -1
    qstring = None

    for x in string:
        if quoted:
            if qpair:
                qpair = False
                qstring = qstring+string[start:cur-1]+x
                start = cur+1
            elif x == '\\':
                qpair = True
            elif x == '"':
                quoted = False
                yield qstring+string[start:cur]
                qstring=None
                start = cur+1
        elif x in tokens:
            if start != cur:
                if foldCase:
                    yield string[start:cur].lower()
                else:
                    yield string[start:cur]

            start = cur+1
            if x == '"':
                quoted = True
                qstring = ""
                inSpaces = False
            elif x in " \t":
                if inSpaces is False:
                    inSpaces = True
            else:
                inSpaces = -1
                yield Token(x)
        elif x in ctls:
            raise ValueError("Invalid control character: %d in header" % ord(x))
        else:
            if inSpaces is True:
                yield Token(' ')
                inSpaces = False

            inSpaces = False
        cur = cur+1

    if qpair:
        raise ValueError, "Missing character after '\\'"
    if quoted:
        raise ValueError, "Missing end quote"

    if start != cur:
        if foldCase:
            yield string[start:cur].lower()
        else:
            yield string[start:cur]

def split(seq, delim):
    """The same as str.split but works on arbitrary sequences.
    Too bad it's not builtin to python!"""

    cur = []
    for item in seq:
        if item == delim:
            yield cur
            cur = []
        else:
            cur.append(item)
    yield cur

# def find(seq, *args):
#     """The same as seq.index but returns -1 if not found, instead
#     Too bad it's not builtin to python!"""
#     try:
#         return seq.index(value, *args)
#     except ValueError:
#         return -1


def filterTokens(seq):
    """Filter out instances of Token, leaving only a list of strings.

    Used instead of a more specific parsing method (e.g. splitting on commas)
    when only strings are expected, so as to be a little lenient.

    Apache does it this way and has some comments about broken clients which
    forget commas (?), so I'm doing it the same way. It shouldn't
    hurt anything, in any case.
    """

    l=[]
    for x in seq:
        if not isinstance(x, Token):
            l.append(x)
    return l

##### parser utilities:
def checkSingleToken(tokens):
    if len(tokens) != 1:
        raise ValueError, "Expected single token, not %s." % (tokens,)
    return tokens[0]

def parseKeyValue(val):
    if len(val) == 1:
        return val[0],None
    elif len(val) == 3 and val[1] == Token('='):
        return val[0],val[2]
    raise ValueError, "Expected key or key=value, but got %s." % (val,)

def parseArgs(field):
    args=split(field, Token(';'))
    val = args.next()
    args = [parseKeyValue(arg) for arg in args]
    return val,args

def listParser(fun):
    """Return a function which applies 'fun' to every element in the
    comma-separated list"""
    def listParserHelper(tokens):
        fields = split(tokens, Token(','))
        for field in fields:
            if len(field) != 0:
                yield fun(field)

    return listParserHelper

def last(seq):
    """Return seq[-1]"""

    return seq[-1]

##### Generation utilities
def quoteString(s):
    """
    Quote a string according to the rules for the I{quoted-string} production
    in RFC 2616 section 2.2.

    @type s: C{str}
    @rtype: C{str}
    """
    return '"%s"' % s.replace('\\', '\\\\').replace('"', '\\"')

def listGenerator(fun):
    """Return a function which applies 'fun' to every element in
    the given list, then joins the result with generateList"""
    def listGeneratorHelper(l):
        return generateList([fun(e) for e in l])

    return listGeneratorHelper

def generateList(seq):
    return ", ".join(seq)

def singleHeader(item):
    return [item]

_seperators = re.compile('[' + re.escape(http_tokens) + ']')

def generateKeyValues(parameters):
    """
    Format an iterable of key/value pairs.

    Although each header in HTTP 1.1 redefines the grammar for the formatting
    of its parameters, the grammar defined by almost all headers conforms to
    the specification given in RFC 2046.  Note also that RFC 2616 section 19.2
    note 2 points out that many implementations fail if the value is quoted,
    therefore this function only quotes the value when it is necessary.

    @param parameters: An iterable of C{tuple} of a C{str} parameter name and
        C{str} or C{None} parameter value which will be formated.

    @return: The formatted result.
    @rtype: C{str}
    """
    l = []
    for k, v in parameters:
        if v is None:
            l.append('%s' % k)
        else:
            if _seperators.search(v) is not None:
                v = quoteString(v)
            l.append('%s=%s' % (k, v))
    return ";".join(l)


class MimeType(object):
    def fromString(klass, mimeTypeString):
        """Generate a MimeType object from the given string.

        @param mimeTypeString: The mimetype to parse

        @return: L{MimeType}
        """
        return DefaultHTTPHandler.parse('content-type', [mimeTypeString])

    fromString = classmethod(fromString)

    def __init__(self, mediaType, mediaSubtype, params={}, **kwargs):
        """
        @type mediaType: C{str}

        @type mediaSubtype: C{str}

        @type params: C{dict}
        """
        self.mediaType = mediaType
        self.mediaSubtype = mediaSubtype
        self.params = dict(params)

        if kwargs:
            self.params.update(kwargs)

    def __eq__(self, other):
        if not isinstance(other, MimeType): return NotImplemented
        return (self.mediaType == other.mediaType and
                self.mediaSubtype == other.mediaSubtype and
                self.params == other.params)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "MimeType(%r, %r, %r)" % (self.mediaType, self.mediaSubtype, self.params)

    def __hash__(self):
        return hash(self.mediaType)^hash(self.mediaSubtype)^hash(tuple(self.params.iteritems()))

##### Specific header parsers.
def parseAccept(field):
    type,args = parseArgs(field)

    if len(type) != 3 or type[1] != Token('/'):
        raise ValueError, "MIME Type "+str(type)+" invalid."

    # okay, this spec is screwy. A 'q' parameter is used as the separator
    # between MIME parameters and (as yet undefined) additional HTTP
    # parameters.

    num = 0
    for arg in args:
        if arg[0] == 'q':
            mimeparams=tuple(args[0:num])
            params=args[num:]
            break
        num = num + 1
    else:
        mimeparams=tuple(args)
        params=[]

    # Default values for parameters:
    qval = 1.0

    # Parse accept parameters:
    for param in params:
        if param[0] =='q':
            qval = float(param[1])
        else:
            # Warn? ignored parameter.
            pass

    ret = MimeType(type[0],type[2],mimeparams),qval
    return ret

def parseAcceptQvalue(field):
    type,args=parseArgs(field)

    type = checkSingleToken(type)

    qvalue = 1.0 # Default qvalue is 1
    for arg in args:
        if arg[0] == 'q':
            qvalue = float(arg[1])
    return type,qvalue

def addDefaultCharset(charsets):
    if charsets.get('*') is None and charsets.get('iso-8859-1') is None:
        charsets['iso-8859-1'] = 1.0
    return charsets

def addDefaultEncoding(encodings):
    if encodings.get('*') is None and encodings.get('identity') is None:
        # RFC doesn't specify a default value for identity, only that it
        # "is acceptable" if not mentioned. Thus, give it a very low qvalue.
        encodings['identity'] = .0001
    return encodings


def parseContentType(header):
    # Case folding is disabled for this header, because of use of
    # Content-Type: multipart/form-data; boundary=CaSeFuLsTuFf
    # So, we need to explicitly .lower() the type/subtype and arg keys.

    type,args = parseArgs(header)

    if len(type) != 3 or type[1] != Token('/'):
        raise ValueError, "MIME Type "+str(type)+" invalid."

    args = [(kv[0].lower(), kv[1]) for kv in args]

    return MimeType(type[0].lower(), type[2].lower(), tuple(args))

def parseContentMD5(header):
    try:
        return base64.decodestring(header)
    except Exception,e:
        raise ValueError(e)

def parseContentRange(header):
    """Parse a content-range header into (kind, start, end, realLength).

    realLength might be None if real length is not known ('*').
    start and end might be None if start,end unspecified (for response code 416)
    """
    kind, other = header.strip().split()
    if kind.lower() != "bytes":
        raise ValueError("a range of type %r is not supported")
    startend, realLength = other.split("/")
    if startend.strip() == '*':
        start,end=None,None
    else:
        start, end = map(int, startend.split("-"))
    if realLength == "*":
        realLength = None
    else:
        realLength = int(realLength)
    return (kind, start, end, realLength)

def parseExpect(field):
    type,args=parseArgs(field)

    type=parseKeyValue(type)
    return (type[0], (lambda *args:args)(type[1], *args))

def parseExpires(header):
    # """HTTP/1.1 clients and caches MUST treat other invalid date formats,
    #    especially including the value 0, as in the past (i.e., "already expired")."""

    try:
        return parseDateTime(header)
    except ValueError:
        return 0

def parseIfModifiedSince(header):
    # Ancient versions of netscape and *current* versions of MSIE send
    #   If-Modified-Since: Thu, 05 Aug 2004 12:57:27 GMT; length=123
    # which is blantantly RFC-violating and not documented anywhere
    # except bug-trackers for web frameworks.

    # So, we'll just strip off everything after a ';'.
    return parseDateTime(header.split(';', 1)[0])

def parseIfRange(headers):
    try:
        return ETag.parse(tokenize(headers))
    except ValueError:
        return parseDateTime(last(headers))

def parseRange(range):
    range = list(range)
    if len(range) < 3 or range[1] != Token('='):
        raise ValueError("Invalid range header format: %s" %(range,))

    type=range[0]
    if type != 'bytes':
        raise ValueError("Unknown range unit: %s." % (type,))
    rangeset=split(range[2:], Token(','))
    ranges = []

    for byterangespec in rangeset:
        if len(byterangespec) != 1:
            raise ValueError("Invalid range header format: %s" % (range,))
        start,end=byterangespec[0].split('-')

        if not start and not end:
            raise ValueError("Invalid range header format: %s" % (range,))

        if start:
            start = int(start)
        else:
            start = None

        if end:
            end = int(end)
        else:
            end = None

        if start and end and start > end:
            raise ValueError("Invalid range header, start > end: %s" % (range,))
        ranges.append((start,end))
    return type,ranges

def parseRetryAfter(header):
    try:
        # delta seconds
        return time.time() + int(header)
    except ValueError:
        # or datetime
        return parseDateTime(header)

# WWW-Authenticate and Authorization

def parseWWWAuthenticate(tokenized):
    headers = []

    tokenList = list(tokenized)

    while tokenList:
        scheme = tokenList.pop(0)
        challenge = {}
        last = None
        kvChallenge = False

        while tokenList:
            token = tokenList.pop(0)
            if token == Token('='):
                kvChallenge = True
                challenge[last] = tokenList.pop(0)
                last = None

            elif token == Token(','):
                if kvChallenge:
                    if len(tokenList) > 1 and tokenList[1] != Token('='):
                        break

                else:
                    break

            else:
                last = token

        if last and scheme and not challenge and not kvChallenge:
            challenge = last
            last = None

        headers.append((scheme, challenge))

    if last and last not in (Token('='), Token(',')):
        if headers[-1] == (scheme, challenge):
            scheme = last
            challenge = {}
            headers.append((scheme, challenge))

    return headers

def parseAuthorization(header):
    scheme, rest = header.split(' ', 1)
    # this header isn't tokenized because it may eat characters
    # in the unquoted base64 encoded credentials
    return scheme.lower(), rest

#### Header generators
def generateAccept(accept):
    mimeType,q = accept

    out="%s/%s"%(mimeType.mediaType, mimeType.mediaSubtype)
    if mimeType.params:
        out+=';'+generateKeyValues(mimeType.params.iteritems())

    if q != 1.0:
        out+=(';q=%.3f' % (q,)).rstrip('0').rstrip('.')

    return out

def removeDefaultEncoding(seq):
    for item in seq:
        if item[0] != 'identity' or item[1] != .0001:
            yield item

def generateAcceptQvalue(keyvalue):
    if keyvalue[1] == 1.0:
        return "%s" % keyvalue[0:1]
    else:
        return ("%s;q=%.3f" % keyvalue).rstrip('0').rstrip('.')

def parseCacheControl(kv):
    k, v = parseKeyValue(kv)
    if k == 'max-age' or k == 'min-fresh' or k == 's-maxage':
        # Required integer argument
        if v is None:
            v = 0
        else:
            v = int(v)
    elif k == 'max-stale':
        # Optional integer argument
        if v is not None:
            v = int(v)
    elif k == 'private' or k == 'no-cache':
        # Optional list argument
        if v is not None:
            v = [field.strip().lower() for field in v.split(',')]
    return k, v

def generateCacheControl((k, v)):
    if v is None:
        return str(k)
    else:
        if k == 'no-cache' or k == 'private':
            # quoted list of values
            v = quoteString(generateList(
                [header_case_mapping.get(name) or dashCapitalize(name) for name in v]))
        return '%s=%s' % (k,v)

def generateContentRange(tup):
    """tup is (type, start, end, len)
    len can be None.
    """
    type, start, end, len = tup
    if len == None:
        len = '*'
    else:
        len = int(len)
    if start == None and end == None:
        startend = '*'
    else:
        startend = '%d-%d' % (start, end)

    return '%s %s/%s' % (type, startend, len)

def generateDateTime(secSinceEpoch):
    """Convert seconds since epoch to HTTP datetime string."""
    year, month, day, hh, mm, ss, wd, y, z = time.gmtime(secSinceEpoch)
    s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
        weekdayname[wd],
        day, monthname[month], year,
        hh, mm, ss)
    return s

def generateExpect(item):
    if item[1][0] is None:
        out = '%s' % (item[0],)
    else:
        out = '%s=%s' % (item[0], item[1][0])
    if len(item[1]) > 1:
        out += ';'+generateKeyValues(item[1][1:])
    return out

def generateRange(range):
    def noneOr(s):
        if s is None:
            return ''
        return s

    type,ranges=range

    if type != 'bytes':
        raise ValueError("Unknown range unit: "+type+".")

    return (type+'='+
            ','.join(['%s-%s' % (noneOr(startend[0]), noneOr(startend[1]))
                      for startend in ranges]))

def generateRetryAfter(when):
    # always generate delta seconds format
    return str(int(when - time.time()))

def generateContentType(mimeType):
    out="%s/%s"%(mimeType.mediaType, mimeType.mediaSubtype)
    if mimeType.params:
        out+=';'+generateKeyValues(mimeType.params.iteritems())
    return out

def generateIfRange(dateOrETag):
    if isinstance(dateOrETag, ETag):
        return dateOrETag.generate()
    else:
        return generateDateTime(dateOrETag)

# WWW-Authenticate and Authorization

def generateWWWAuthenticate(headers):
    _generated = []
    for seq in headers:
        scheme, challenge = seq[0], seq[1]

        # If we're going to parse out to something other than a dict
        # we need to be able to generate from something other than a dict

        try:
            l = []
            for k,v in dict(challenge).iteritems():
                l.append("%s=%s" % (k, quoteString(v)))

            _generated.append("%s %s" % (scheme, ", ".join(l)))
        except ValueError:
            _generated.append("%s %s" % (scheme, challenge))

    return _generated

def generateAuthorization(seq):
    return [' '.join(seq)]


####
class ETag(object):
    def __init__(self, tag, weak=False):
        self.tag = str(tag)
        self.weak = weak

    def match(self, other, strongCompare):
        # Sec 13.3.
        # The strong comparison function: in order to be considered equal, both
        #   validators MUST be identical in every way, and both MUST NOT be weak.
        #
        # The weak comparison function: in order to be considered equal, both
        #   validators MUST be identical in every way, but either or both of
        #   them MAY be tagged as "weak" without affecting the result.

        if not isinstance(other, ETag) or other.tag != self.tag:
            return False

        if strongCompare and (other.weak or self.weak):
            return False
        return True

    def __eq__(self, other):
        return isinstance(other, ETag) and other.tag == self.tag and other.weak == self.weak

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "Etag(%r, weak=%r)" % (self.tag, self.weak)

    def parse(tokens):
        tokens=tuple(tokens)
        if len(tokens) == 1 and not isinstance(tokens[0], Token):
            return ETag(tokens[0])

        if(len(tokens) == 3 and tokens[0] == "w"
           and tokens[1] == Token('/')):
            return ETag(tokens[2], weak=True)

        raise ValueError("Invalid ETag.")

    parse=staticmethod(parse)

    def generate(self):
        if self.weak:
            return 'W/'+quoteString(self.tag)
        else:
            return quoteString(self.tag)

def parseStarOrETag(tokens):
    tokens=tuple(tokens)
    if tokens == ('*',):
        return '*'
    else:
        return ETag.parse(tokens)

def generateStarOrETag(etag):
    if etag=='*':
        return etag
    else:
        return etag.generate()

#### Cookies. Blech!
class Cookie(object):
    # __slots__ = ['name', 'value', 'path', 'domain', 'ports', 'expires', 'discard', 'secure', 'comment', 'commenturl', 'version']

    def __init__(self, name, value, path=None, domain=None, ports=None, expires=None, discard=False, secure=False, comment=None, commenturl=None, version=0):
        self.name=name
        self.value=value
        self.path=path
        self.domain=domain
        self.ports=ports
        self.expires=expires
        self.discard=discard
        self.secure=secure
        self.comment=comment
        self.commenturl=commenturl
        self.version=version

    def __repr__(self):
        s="Cookie(%r=%r" % (self.name, self.value)
        if self.path is not None: s+=", path=%r" % (self.path,)
        if self.domain is not None: s+=", domain=%r" % (self.domain,)
        if self.ports is not None: s+=", ports=%r" % (self.ports,)
        if self.expires is not None: s+=", expires=%r" % (self.expires,)
        if self.secure is not False: s+=", secure=%r" % (self.secure,)
        if self.comment is not None: s+=", comment=%r" % (self.comment,)
        if self.commenturl is not None: s+=", commenturl=%r" % (self.commenturl,)
        if self.version != 0: s+=", version=%r" % (self.version,)
        s+=")"
        return s

    def __eq__(self, other):
        return (isinstance(other, Cookie) and
                other.path == self.path and
                other.domain == self.domain and
                other.ports == self.ports and
                other.expires == self.expires and
                other.secure == self.secure and
                other.comment == self.comment and
                other.commenturl == self.commenturl and
                other.version == self.version)

    def __ne__(self, other):
        return not self.__eq__(other)


def parseCookie(headers):
    """Bleargh, the cookie spec sucks.
    This surely needs interoperability testing.
    There are two specs that are supported:
    Version 0) http://wp.netscape.com/newsref/std/cookie_spec.html
    Version 1) http://www.faqs.org/rfcs/rfc2965.html
    """

    cookies = []
    # There can't really be multiple cookie headers according to RFC, because
    # if multiple headers are allowed, they must be joinable with ",".
    # Neither new RFC2965 cookies nor old netscape cookies are.

    header = ';'.join(headers)
    if header[0:8].lower() == "$version":
        # RFC2965 cookie
        h=tokenize([header], foldCase=False)
        r_cookies = split(h, Token(','))
        for r_cookie in r_cookies:
            last_cookie = None
            rr_cookies = split(r_cookie, Token(';'))
            for cookie in rr_cookies:
                nameval = tuple(split(cookie, Token('=')))
                if len(nameval) == 2:
                    (name,), (value,) = nameval
                else:
                    (name,), = nameval
                    value = None

                name=name.lower()
                if name == '$version':
                    continue
                if name[0] == '$':
                    if last_cookie is not None:
                        if name == '$path':
                            last_cookie.path=value
                        elif name == '$domain':
                            last_cookie.domain=value
                        elif name == '$port':
                            if value is None:
                                last_cookie.ports = ()
                            else:
                                last_cookie.ports=tuple([int(s) for s in value.split(',')])
                else:
                    last_cookie = Cookie(name, value, version=1)
                    cookies.append(last_cookie)
    else:
        # Oldstyle cookies don't do quoted strings or anything sensible.
        # All characters are valid for names except ';' and '=', and all
        # characters are valid for values except ';'. Spaces are stripped,
        # however.
        r_cookies = header.split(';')
        for r_cookie in r_cookies:
            name,value = r_cookie.split('=', 1)
            name=name.strip(' \t')
            value=value.strip(' \t')

            cookies.append(Cookie(name, value))

    return cookies

cookie_validname = "[^"+re.escape(http_tokens+http_ctls)+"]*$"
cookie_validname_re = re.compile(cookie_validname)
cookie_validvalue = cookie_validname+'|"([^"]|\\\\")*"$'
cookie_validvalue_re = re.compile(cookie_validvalue)

def generateCookie(cookies):
    # There's a fundamental problem with the two cookie specifications.
    # They both use the "Cookie" header, and the RFC Cookie header only allows
    # one version to be specified. Thus, when you have a collection of V0 and
    # V1 cookies, you have to either send them all as V0 or send them all as
    # V1.

    # I choose to send them all as V1.

    # You might think converting a V0 cookie to a V1 cookie would be lossless,
    # but you'd be wrong. If you do the conversion, and a V0 parser tries to
    # read the cookie, it will see a modified form of the cookie, in cases
    # where quotes must be added to conform to proper V1 syntax.
    # (as a real example: "Cookie: cartcontents=oid:94680,qty:1,auto:0,esp:y")

    # However, that is what we will do, anyways. It has a high probability of
    # breaking applications that only handle oldstyle cookies, where some other
    # application set a newstyle cookie that is applicable over for site
    # (or host), AND where the oldstyle cookie uses a value which is invalid
    # syntax in a newstyle cookie.

    # Also, the cookie name *cannot* be quoted in V1, so some cookies just
    # cannot be converted at all. (e.g. "Cookie: phpAds_capAd[32]=2"). These
    # are just dicarded during conversion.

    # As this is an unsolvable problem, I will pretend I can just say
    # OH WELL, don't do that, or else upgrade your old applications to have
    # newstyle cookie parsers.

    # I will note offhandedly that there are *many* sites which send V0 cookies
    # that are not valid V1 cookie syntax. About 20% for my cookies file.
    # However, they do not generally mix them with V1 cookies, so this isn't
    # an issue, at least right now. I have not tested to see how many of those
    # webapps support RFC2965 V1 cookies. I suspect not many.

    max_version = max([cookie.version for cookie in cookies])

    if max_version == 0:
        # no quoting or anything.
        return ';'.join(["%s=%s" % (cookie.name, cookie.value) for cookie in cookies])
    else:
        str_cookies = ['$Version="1"']
        for cookie in cookies:
            if cookie.version == 0:
                # Version 0 cookie: we make sure the name and value are valid
                # V1 syntax.

                # If they are, we use them as is. This means in *most* cases,
                # the cookie will look literally the same on output as it did
                # on input.
                # If it isn't a valid name, ignore the cookie.
                # If it isn't a valid value, quote it and hope for the best on
                # the other side.

                if cookie_validname_re.match(cookie.name) is None:
                    continue

                value=cookie.value
                if cookie_validvalue_re.match(cookie.value) is None:
                    value = quoteString(value)

                str_cookies.append("%s=%s" % (cookie.name, value))
            else:
                # V1 cookie, nice and easy
                str_cookies.append("%s=%s" % (cookie.name, quoteString(cookie.value)))

            if cookie.path:
                str_cookies.append("$Path=%s" % quoteString(cookie.path))
            if cookie.domain:
                str_cookies.append("$Domain=%s" % quoteString(cookie.domain))
            if cookie.ports is not None:
                if len(cookie.ports) == 0:
                    str_cookies.append("$Port")
                else:
                    str_cookies.append("$Port=%s" % quoteString(",".join([str(x) for x in cookie.ports])))
        return ';'.join(str_cookies)

def parseSetCookie(headers):
    setCookies = []
    for header in headers:
        try:
            parts = header.split(';')
            l = []

            for part in parts:
                namevalue = part.split('=',1)
                if len(namevalue) == 1:
                    name=namevalue[0]
                    value=None
                else:
                    name,value=namevalue
                    value=value.strip(' \t')

                name=name.strip(' \t')

                l.append((name, value))

            setCookies.append(makeCookieFromList(l, True))
        except ValueError:
            # If we can't parse one Set-Cookie, ignore it,
            # but not the rest of Set-Cookies.
            pass
    return setCookies

def parseSetCookie2(toks):
    outCookies = []
    for cookie in [[parseKeyValue(x) for x in split(y, Token(';'))]
                   for y in split(toks, Token(','))]:
        try:
            outCookies.append(makeCookieFromList(cookie, False))
        except ValueError:
            # Again, if we can't handle one cookie -- ignore it.
            pass
    return outCookies

def makeCookieFromList(tup, netscapeFormat):
    name, value = tup[0]
    if name is None or value is None:
        raise ValueError("Cookie has missing name or value")
    if name.startswith("$"):
        raise ValueError("Invalid cookie name: %r, starts with '$'." % name)
    cookie = Cookie(name, value)
    hadMaxAge = False

    for name,value in tup[1:]:
        name = name.lower()

        if value is None:
            if name in ("discard", "secure"):
                # Boolean attrs
                value = True
            elif name != "port":
                # Can be either boolean or explicit
                continue

        if name in ("comment", "commenturl", "discard", "domain", "path", "secure"):
            # simple cases
            setattr(cookie, name, value)
        elif name == "expires" and not hadMaxAge:
            if netscapeFormat and value[0] == '"' and value[-1] == '"':
                value = value[1:-1]
            cookie.expires = parseDateTime(value)
        elif name == "max-age":
            hadMaxAge = True
            cookie.expires = int(value) + time.time()
        elif name == "port":
            if value is None:
                cookie.ports = ()
            else:
                if netscapeFormat and value[0] == '"' and value[-1] == '"':
                    value = value[1:-1]
                cookie.ports = tuple([int(s) for s in value.split(',')])
        elif name == "version":
            cookie.version = int(value)

    return cookie


def generateSetCookie(cookies):
    setCookies = []
    for cookie in cookies:
        out = ["%s=%s" % (cookie.name, cookie.value)]
        if cookie.expires:
            out.append("expires=%s" % generateDateTime(cookie.expires))
        if cookie.path:
            out.append("path=%s" % cookie.path)
        if cookie.domain:
            out.append("domain=%s" % cookie.domain)
        if cookie.secure:
            out.append("secure")

        setCookies.append('; '.join(out))
    return setCookies

def generateSetCookie2(cookies):
    setCookies = []
    for cookie in cookies:
        out = ["%s=%s" % (cookie.name, quoteString(cookie.value))]
        if cookie.comment:
            out.append("Comment=%s" % quoteString(cookie.comment))
        if cookie.commenturl:
            out.append("CommentURL=%s" % quoteString(cookie.commenturl))
        if cookie.discard:
            out.append("Discard")
        if cookie.domain:
            out.append("Domain=%s" % quoteString(cookie.domain))
        if cookie.expires:
            out.append("Max-Age=%s" % (cookie.expires - time.time()))
        if cookie.path:
            out.append("Path=%s" % quoteString(cookie.path))
        if cookie.ports is not None:
            if len(cookie.ports) == 0:
                out.append("Port")
            else:
                out.append("Port=%s" % quoteString(",".join([str(x) for x in cookie.ports])))
        if cookie.secure:
            out.append("Secure")
        out.append('Version="1"')
        setCookies.append('; '.join(out))
    return setCookies

def parseDepth(depth):
    if depth not in ("0", "1", "infinity"):
        raise ValueError("Invalid depth header value: %s" % (depth,))
    return depth

def parseOverWrite(overwrite):
    if overwrite == "F":
        return False
    elif overwrite == "T":
        return True
    raise ValueError("Invalid overwrite header value: %s" % (overwrite,))

def generateOverWrite(overwrite):
    if overwrite:
        return "T"
    else:
        return "F"

##### Random stuff that looks useful.
# def sortMimeQuality(s):
#     def sorter(item1, item2):
#         if item1[0] == '*':
#             if item2[0] == '*':
#                 return 0


# def sortQuality(s):
#     def sorter(item1, item2):
#         if item1[1] < item2[1]:
#             return -1
#         if item1[1] < item2[1]:
#             return 1
#         if item1[0] == item2[0]:
#             return 0


# def getMimeQuality(mimeType, accepts):
#     type,args = parseArgs(mimeType)
#     type=type.split(Token('/'))
#     if len(type) != 2:
#         raise ValueError, "MIME Type "+s+" invalid."

#     for accept in accepts:
#         accept,acceptQual=accept
#         acceptType=accept[0:1]
#         acceptArgs=accept[2]

#         if ((acceptType == type or acceptType == (type[0],'*') or acceptType==('*','*')) and
#             (args == acceptArgs or len(acceptArgs) == 0)):
#             return acceptQual

# def getQuality(type, accepts):
#     qual = accepts.get(type)
#     if qual is not None:
#         return qual

#     return accepts.get('*')

# Headers object
class __RecalcNeeded(object):
    def __repr__(self):
        return "<RecalcNeeded>"

_RecalcNeeded = __RecalcNeeded()

class Headers(object):
    """
    This class stores the HTTP headers as both a parsed representation
    and the raw string representation. It converts between the two on
    demand.
    """

    def __init__(self, headers=None, rawHeaders=None, handler=DefaultHTTPHandler):
        self._raw_headers = {}
        self._headers = {}
        self.handler = handler
        if headers is not None:
            for key, value in headers.iteritems():
                self.setHeader(key, value)
        if rawHeaders is not None:
            for key, value in rawHeaders.iteritems():
                self.setRawHeaders(key, value)

    def _setRawHeaders(self, headers):
        self._raw_headers = headers
        self._headers = {}

    def _toParsed(self, name):
        r = self._raw_headers.get(name, None)
        h = self.handler.parse(name, r)
        if h is not None:
            self._headers[name] = h
        return h

    def _toRaw(self, name):
        h = self._headers.get(name, None)
        r = self.handler.generate(name, h)
        if r is not None:
            self._raw_headers[name] = r
        return r

    def hasHeader(self, name):
        """Does a header with the given name exist?"""
        name=name.lower()
        return self._raw_headers.has_key(name)

    def getRawHeaders(self, name, default=None):
        """Returns a list of headers matching the given name as the raw string given."""

        name=name.lower()
        raw_header = self._raw_headers.get(name, default)
        if raw_header is not _RecalcNeeded:
            return raw_header

        return self._toRaw(name)

    def getHeader(self, name, default=None):
        """Ret9urns the parsed representation of the given header.
        The exact form of the return value depends on the header in question.

        If no parser for the header exists, raise ValueError.

        If the header doesn't exist, return default (or None if not specified)
        """
        name=name.lower()
        parsed = self._headers.get(name, default)
        if parsed is not _RecalcNeeded:
            return parsed
        return self._toParsed(name)

    def setRawHeaders(self, name, value):
        """Sets the raw representation of the given header.
        Value should be a list of strings, each being one header of the
        given name.
        """
        name=name.lower()
        self._raw_headers[name] = value
        self._headers[name] = _RecalcNeeded

    def setHeader(self, name, value):
        """Sets the parsed representation of the given header.
        Value should be a list of objects whose exact form depends
        on the header in question.
        """
        name=name.lower()
        self._raw_headers[name] = _RecalcNeeded
        self._headers[name] = value

    def addRawHeader(self, name, value):
        """
        Add a raw value to a header that may or may not already exist.
        If it exists, add it as a separate header to output; do not
        replace anything.
        """
        name=name.lower()
        raw_header = self._raw_headers.get(name)
        if raw_header is None:
            # No header yet
            raw_header = []
            self._raw_headers[name] = raw_header
        elif raw_header is _RecalcNeeded:
            raw_header = self._toRaw(name)

        raw_header.append(value)
        self._headers[name] = _RecalcNeeded

    def removeHeader(self, name):
        """Removes the header named."""

        name=name.lower()
        if self._raw_headers.has_key(name):
            del self._raw_headers[name]
            del self._headers[name]

    def __repr__(self):
        return '<Headers: Raw: %s Parsed: %s>'% (self._raw_headers, self._headers)

    def canonicalNameCaps(self, name):
        """Return the name with the canonical capitalization, if known,
        otherwise, Caps-After-Dashes"""
        return header_case_mapping.get(name) or dashCapitalize(name)

    def getAllRawHeaders(self):
        """Return an iterator of key,value pairs of all headers
        contained in this object, as strings. The keys are capitalized
        in canonical capitalization."""
        for k,v in self._raw_headers.iteritems():
            if v is _RecalcNeeded:
                v = self._toRaw(k)
            yield self.canonicalNameCaps(k), v

    def makeImmutable(self):
        """Make this header set immutable. All mutating operations will
        raise an exception."""
        self.setHeader = self.setRawHeaders = self.removeHeader = self._mutateRaise

    def _mutateRaise(self, *args):
        raise AttributeError("This header object is immutable as the headers have already been sent.")


"""The following dicts are all mappings of header to list of operations
   to perform. The first operation should generally be 'tokenize' if the
   header can be parsed according to the normal tokenization rules. If
   it cannot, generally the first thing you want to do is take only the
   last instance of the header (in case it was sent multiple times, which
   is strictly an error, but we're nice.).
   """

iteritems = lambda x: x.iteritems()


parser_general_headers = {
    'Cache-Control':(tokenize, listParser(parseCacheControl), dict),
    'Connection':(tokenize,filterTokens),
    'Date':(last,parseDateTime),
#    'Pragma':tokenize
#    'Trailer':tokenize
    'Transfer-Encoding':(tokenize,filterTokens),
#    'Upgrade':tokenize
#    'Via':tokenize,stripComment
#    'Warning':tokenize
}

generator_general_headers = {
    'Cache-Control':(iteritems, listGenerator(generateCacheControl), singleHeader),
    'Connection':(generateList,singleHeader),
    'Date':(generateDateTime,singleHeader),
#    'Pragma':
#    'Trailer':
    'Transfer-Encoding':(generateList,singleHeader),
#    'Upgrade':
#    'Via':
#    'Warning':
}

parser_request_headers = {
    'Accept': (tokenize, listParser(parseAccept), dict),
    'Accept-Charset': (tokenize, listParser(parseAcceptQvalue), dict, addDefaultCharset),
    'Accept-Encoding':(tokenize, listParser(parseAcceptQvalue), dict, addDefaultEncoding),
    'Accept-Language':(tokenize, listParser(parseAcceptQvalue), dict),
    'Authorization': (last, parseAuthorization),
    'Cookie':(parseCookie,),
    'Expect':(tokenize, listParser(parseExpect), dict),
    'From':(last,),
    'Host':(last,),
    'If-Match':(tokenize, listParser(parseStarOrETag), list),
    'If-Modified-Since':(last, parseIfModifiedSince),
    'If-None-Match':(tokenize, listParser(parseStarOrETag), list),
    'If-Range':(parseIfRange,),
    'If-Unmodified-Since':(last,parseDateTime),
    'Max-Forwards':(last,int),
#    'Proxy-Authorization':str, # what is "credentials"
    'Range':(tokenize, parseRange),
    'Referer':(last,str), # TODO: URI object?
    'TE':(tokenize, listParser(parseAcceptQvalue), dict),
    'User-Agent':(last,str),
}

generator_request_headers = {
    'Accept': (iteritems,listGenerator(generateAccept),singleHeader),
    'Accept-Charset': (iteritems, listGenerator(generateAcceptQvalue),singleHeader),
    'Accept-Encoding': (iteritems, removeDefaultEncoding, listGenerator(generateAcceptQvalue),singleHeader),
    'Accept-Language': (iteritems, listGenerator(generateAcceptQvalue),singleHeader),
    'Authorization': (generateAuthorization,), # what is "credentials"
    'Cookie':(generateCookie,singleHeader),
    'Expect':(iteritems, listGenerator(generateExpect), singleHeader),
    'From':(str,singleHeader),
    'Host':(str,singleHeader),
    'If-Match':(listGenerator(generateStarOrETag), singleHeader),
    'If-Modified-Since':(generateDateTime,singleHeader),
    'If-None-Match':(listGenerator(generateStarOrETag), singleHeader),
    'If-Range':(generateIfRange, singleHeader),
    'If-Unmodified-Since':(generateDateTime,singleHeader),
    'Max-Forwards':(str, singleHeader),
#    'Proxy-Authorization':str, # what is "credentials"
    'Range':(generateRange,singleHeader),
    'Referer':(str,singleHeader),
    'TE': (iteritems, listGenerator(generateAcceptQvalue),singleHeader),
    'User-Agent':(str,singleHeader),
}

parser_response_headers = {
    'Accept-Ranges':(tokenize, filterTokens),
    'Age':(last,int),
    'ETag':(tokenize, ETag.parse),
    'Location':(last,), # TODO: URI object?
#    'Proxy-Authenticate'
    'Retry-After':(last, parseRetryAfter),
    'Server':(last,),
    'Set-Cookie':(parseSetCookie,),
    'Set-Cookie2':(tokenize, parseSetCookie2),
    'Vary':(tokenize, filterTokens),
    'WWW-Authenticate': (lambda h: tokenize(h, foldCase=False),
                         parseWWWAuthenticate,)
}

generator_response_headers = {
    'Accept-Ranges':(generateList, singleHeader),
    'Age':(str, singleHeader),
    'ETag':(ETag.generate, singleHeader),
    'Location':(str, singleHeader),
#    'Proxy-Authenticate'
    'Retry-After':(generateRetryAfter, singleHeader),
    'Server':(str, singleHeader),
    'Set-Cookie':(generateSetCookie,),
    'Set-Cookie2':(generateSetCookie2,),
    'Vary':(generateList, singleHeader),
    'WWW-Authenticate':(generateWWWAuthenticate,)
}

parser_entity_headers = {
    'Allow':(lambda str:tokenize(str, foldCase=False), filterTokens),
    'Content-Encoding':(tokenize, filterTokens),
    'Content-Language':(tokenize, filterTokens),
    'Content-Length':(last, int),
    'Content-Location':(last,), # TODO: URI object?
    'Content-MD5':(last, parseContentMD5),
    'Content-Range':(last, parseContentRange),
    'Content-Type':(lambda str:tokenize(str, foldCase=False), parseContentType),
    'Expires':(last, parseExpires),
    'Last-Modified':(last, parseDateTime),
    }

generator_entity_headers = {
    'Allow':(generateList, singleHeader),
    'Content-Encoding':(generateList, singleHeader),
    'Content-Language':(generateList, singleHeader),
    'Content-Length':(str, singleHeader),
    'Content-Location':(str, singleHeader),
    'Content-MD5':(base64.encodestring, lambda x: x.strip("\n"), singleHeader),
    'Content-Range':(generateContentRange, singleHeader),
    'Content-Type':(generateContentType, singleHeader),
    'Expires':(generateDateTime, singleHeader),
    'Last-Modified':(generateDateTime, singleHeader),
    }

DefaultHTTPHandler.updateParsers(parser_general_headers)
DefaultHTTPHandler.updateParsers(parser_request_headers)
DefaultHTTPHandler.updateParsers(parser_response_headers)
DefaultHTTPHandler.updateParsers(parser_entity_headers)

DefaultHTTPHandler.updateGenerators(generator_general_headers)
DefaultHTTPHandler.updateGenerators(generator_request_headers)
DefaultHTTPHandler.updateGenerators(generator_response_headers)
DefaultHTTPHandler.updateGenerators(generator_entity_headers)


# casemappingify(DefaultHTTPParsers)
# casemappingify(DefaultHTTPGenerators)

# lowerify(DefaultHTTPParsers)
# lowerify(DefaultHTTPGenerators)
