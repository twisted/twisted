import types
from calendar import timegm
from time import gmtime

# datetime parsing and formatting
weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
monthname = [None,
             'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

## HTTP DateTime parser
def parseDateTime(dateString):
    """Convert an HTTP date string (one of three formats) to seconds since epoch."""
    parts = dateString.split()
    if parts[1].isdigit():
        # 1st date format: Sun, 06 Nov 1994 08:49:37 GMT
        # (Note: "GMT" is literal, not a variable timezone)
        # This is the normal format
        day = parts[1]
        month = parts[2]
        year = parts[3]
        time = parts[4]
    elif parts[1].find('-') != -1:
        # 2nd date format: Sunday, 06-Nov-94 08:49:37 GMT
        # (Note: "GMT" is literal, not a variable timezone)
        # Two digit year, yucko.
        day, month, year = parts[1].split('-')
        time = parts[2]
        year=int(year)
        if year < 69:
            year = year + 2000
        elif year < 100:
            year = year + 1900
    else:
        # 3rd date format: Sun Nov  6 08:49:37 1994
        # ANSI C asctime() format.
        day = parts[2]
        month = parts[1]
        year = parts[4]
        time = parts[3]
        
    day = int(day)
    month = int(monthname.index(month))
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

    tokens = " \t\"()<>@,;:\\/[]?={}"
    ctls = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f"
    
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

def find(seq, *args):
    """The same as seq.index but returns -1 if not found, instead 
    Too bad it's not builtin to python!"""
    try:
        return seq.index(value, *args)
    except ValueError:
        return -1
    

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
        return val[0],True
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

##### Specific header parsers.
def parseAccept(field):
    type,args = parseArgs(field)

    if len(type) != 3 or type[1] != Token('/'):
        raise ValueError, "MIME Type "+str(type)+" invalid."
    
    # okay, this spec is screwy. A 'q' parameter is used as the separator
    # between MIME parameters and (as yet undefined) additional HTTP
    # parameters.

    # I wonder if we actually need to support 'accept-extension'.
    # If not, paramdict doesn't need to be a dictionary.
    
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
    paramdict={'q':1.0}
    
    # Parse accept parameters:
    for param in params:
        if param[0] =='q':
            paramdict['q'] = float(param[1])
        else:
            # Warn? ignored parameter.
            pass

    ret = (type[0],type[2],mimeparams),paramdict
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

def parseExpect(field):
    type,args=parseArgs(field)
    
    type=parseKeyValue(type)
    return (type[0], (lambda *args:args)(type[1], *args))

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
        startend=byterangespec[0].split('-')
        if len(startend) != 2:
            raise ValueError("Invalid range header format: %s" % (range,))
        
        start = end = None
        if startend[0]:
            start = int(startend[0])
        if startend[1]:
            end = int(startend[1])
        ranges.append((start,end))
    return type,ranges

def parseRetryAfter(header):
    try:
        # delta seconds
        return time.time() + int(header)
    except:
        # or datetime
        return parseDateTime(header)


##### Header generation
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

def generateKeyValues(kvs):
    l = []
    for k,v in kvs:
        if v is True:
            l.append('%s' % k)
        else:
            l.append('%s=%s' % (k,v))
    return ';'.join(l)

def generateAccept(accept):
    mimeType,params = accept

    out="%s/%s"%(mimeType[0], mimeType[1])
    if mimeType[2]:
        out+=';'+generateKeyValues(mimeType[2])

    if params:
        q = params.get('q')
        if not q:
            raise ValueError, "Cannot have Accept params without a 'q' param."
        
        params = params.copy()
        del params['q']
        if q != 1.0 or params:
            out+=(';q=%.2f' % (q,)).rstrip('0').rstrip('.')
        
        if params:
            out+=';'+generateKeyValues(params)
    return out

def removeDefaultEncoding(seq):
    for item in seq:
        if item[0] != 'identity' or item[1] != .0001:
            yield item

def generateAcceptQvalue(keyvalue):
    if keyvalue[1] == 1.0:
        return "%s" % keyvalue[0:1]
    else:
        return ("%s;q=%.2f" % keyvalue).rstrip('0').rstrip('.')

def generateDateTime(secSinceEpoch):
    """Convert seconds since epoch to HTTP datetime string."""
    year, month, day, hh, mm, ss, wd, y, z = gmtime(secSinceEpoch)
    s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
        weekdayname[wd],
        day, monthname[month], year,
        hh, mm, ss)
    return s

def generateExpect(item):
    if item[1][0] is True:
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

def generateRetryAfter(aftersecs):
    # always generate delta seconds format
    return str(int(header) - time.time())


##### Random shits
def sortMimeQuality(s):
    def sorter(item1, item2):
        if item1[0] == '*':
            if item2[0] == '*':
                return 0


def sortQuality(s):
    def sorter(item1, item2):
        if item1[1] < item2[1]:
            return -1
        if item1[1] < item2[1]:
            return 1
        if item1[0] == item2[0]:
            return 0
            
            
def getMimeQuality(mimeType, accepts):
    type,args = parseArgs(mimeType)
    type=type.split(Token('/'))
    if len(type) != 2:
        raise ValueError, "MIME Type "+s+" invalid."

    for accept in accepts:
        accept,acceptQual=accept
        acceptType=accept[0:1]
        acceptArgs=accept[2]
        
        if ((acceptType == type or acceptType == (type[0],'*') or acceptType==('*','*')) and
            (args == acceptArgs or len(acceptArgs) == 0)):
            return acceptQual

def getQuality(type, accepts):
    qual = accepts.get(type)
    if qual is not None:
        return qual
    
    return accepts.get('*')

def parseContentRange(header):
    """Parse a content-range header into (start, end, realLength).
    
    realLength might be None if real length is not known ('*').
    """
    kind, other = header.strip().split()
    if kind.lower() != "bytes":
        raise ValueError, "a range of type %r is not supported"
    startend, realLength = other.split("/")
    start, end = map(int, startend.split("-"))
    if realLength == "*":
        realLength = None
    else:
        realLength = int(realLength)
    return (start, end, realLength)

def addCookie(self, k, v, expires=None, domain=None, path=None, max_age=None, comment=None, secure=None):
    """Set an outgoing HTTP cookie.

    In general, you should consider using sessions instead of cookies, see
    twisted.web.server.Request.getSession and the
    twisted.web.server.Session class for details.
    """
    cookie = '%s=%s' % (k, v)
    if expires != None:
        cookie = cookie +"; Expires=%s" % expires
    if domain != None:
        cookie = cookie +"; Domain=%s" % domain
    if path != None:
        cookie = cookie +"; Path=%s" % path
    if max_age != None:
        cookie = cookie +"; Max-Age=%s" % max_age
    if comment != None:
        cookie = cookie +"; Comment=%s" % comment
    if secure:
        cookie = cookie +"; Secure"
    self.cookies.append(cookie)


# Header object
_RecalcNeeded = object()

class Headers:
    """This class stores the HTTP headers as both a parsed representation and
    the raw string representation. It converts between the two on demand."""
    
    def __init__(self, parsers=None, generators=None):
        self._raw_headers = {}
        self._headers = {}
        self.parsers=parsers
        self.generators=generators

    def _setRawHeaders(self, headers):
        self._raw_headers = headers
        self._headers = {}
        
    def _addHeader(self, name, strvalue):
        """Add a header & value to the collection of headers. Appends not replaces
        a previous header of the same name."""
        old = self._raw_headers.get(name, None)
        if old is None:
            old = []
            self._raw_headers[name]=old
        old.append(strvalue)
    
    def _parser(self, name):
        parser = self.parsers.get(name, None)
        if parser is None:
            raise ValueError("No header parser for header '%s', either add one or use getHeaderRaw." % (name,))

        return parser

    def _generator(self, name):
        generator = self.generators.get(name, None)
        if generator is None:
            raise ValueError("No header generator for header '%s', either add one or use setHeaderRaw." % (name,))

        return generator

    def hasHeader(self, name):
        return self._raw_headers.has_key(name)
    
    def getRawHeader(self, name, default=Exception):
        """Returns a list of headers matching the given name as the raw string given."""
        
        raw_header = self._raw_headers.get(name, default)
        if raw_header is not _RecalcNeeded:
            if raw_header is Exception:
                raise KeyError(name)
            else:
                return raw_header
        
        generator = self._generator(name)
        
        h = self._headers[name]
        for g in generator:
            h = g(h)

        self._raw_headers[name] = h
        return h
    
    def getHeader(self, name, default=Exception):
        """Returns the parsed representation of the given header.
        The exact form of the return value depends on the header in question.
        
        If no parser for the header exists, raise ValueError.
        
        If the header doesn't exist, return default if specified, else
        raise KeyError
        """
    
        parsed = self._headers.get(name, default)
        if parsed is not _RecalcNeeded:
            if parsed is Exception:
                raise KeyError(name)
            else:
                return parsed
        parser = self._parser(name)
        
        h = self._raw_headers[name]
        for p in parser:
            # print "Parsing %s: %s(%s)" % (name, repr(p), repr(h))
            h = p(h)
            # if isinstance(h, types.GeneratorType):
            #     h=list(h)
        
        self._headers[name]=h
        return h
    
    def setRawHeader(self, name, value):
        """Sets the raw representation of the given header.
        Value should be a list of strings, each being one header of the
        given name.
        """
        
        self._raw_headers[name] = value
        self._headers[name] = _RecalcNeeded

    def setHeader(self, name, value):
        """Sets the parsed representation of the given header.
        Value should be a list of objects whose exact form depends
        on the header in question.
        """
        self._raw_headers[name] = _RecalcNeeded
        self._headers[name] = value

    def removeHeader(self, name):
        """Removes the header named."""
        
        del self._raw_headers[name]
        del self._headers[name]


"""The following dicts are all mappings of header to list of operations
   to perform. The first operation should generally be 'tokenize' if the
   header can be parsed according to the normal tokenization rules. If
   it cannot, generally the first thing you want to do is take only the
   last instance of the header (in case it was sent multiple times, which
   is strictly an error, but we're nice.).
   """

# Counterpart to evilness in test_http_headers
try:
    _http_headers_isBeingTested
    print "isbeingtested"
    from twisted.python.util import OrderedDict
    toDict = OrderedDict
except:
    toDict = dict

iteritems = lambda x: x.iteritems()


parser_general_headers = {
#    'Cache-Control':(tokenize,...)
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
#    'Cache-Control':
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
    'Accept': (tokenize, listParser(parseAccept), toDict),
    'Accept-Charset': (tokenize, listParser(parseAcceptQvalue), toDict, addDefaultCharset),
    'Accept-Encoding':(tokenize, listParser(parseAcceptQvalue), toDict, addDefaultEncoding),
    'Accept-Language':(tokenize, listParser(parseAcceptQvalue), toDict),
#    'Authorization':str # what is "credentials"
    'Expect':(tokenize, listParser(parseExpect), toDict),
    'From':(last,),
    'Host':(last,),
#    'If-Match':
    'If-Modified-Since':(last,parseDateTime),
#    'If-None-Match':None,
#    'If-Range':None,
    'If-Unmodified-Since':(last,parseDateTime),
    'Max-Forwards':(last,int),
#    'Proxy-Authorization':str, # what is "credentials"
    'Range':(tokenize, parseRange),
    'Referer':(last,str),
    'TE':None,
    'User-Agent':(last,str),
}


generator_request_headers = {
    'Accept': (iteritems,listGenerator(generateAccept),singleHeader),
    'Accept-Charset': (iteritems, listGenerator(generateAcceptQvalue),singleHeader),
    'Accept-Encoding': (iteritems, removeDefaultEncoding, listGenerator(generateAcceptQvalue),singleHeader),
    'Accept-Language': (iteritems, listGenerator(generateAcceptQvalue),singleHeader),
#    'Authorization':str # what is "credentials"
    'Expect':(iteritems, listGenerator(generateExpect), singleHeader),
    'From':(str,singleHeader),
    'Host':(str,singleHeader),
#    'If-Match':
    'If-Modified-Since':(generateDateTime,singleHeader),
#    'If-None-Match':None,
#    'If-Range':None,
    'If-Unmodified-Since':(generateDateTime,singleHeader),
    'Max-Forwards':(str, singleHeader),
#    'Proxy-Authorization':str, # what is "credentials"
    'Range':(generateRange,singleHeader),
    'Referer':(str,singleHeader),
    'TE':None,
    'User-Agent':(str,singleHeader),
}

parser_response_headers = {
    'Accept-Ranges':(tokenize, filterTokens),
    'Age':(last,int),
#    'ETag'
    'Location':(last,),
#    'Proxy-Authenticate'
    'Retry-After':(last, parseRetryAfter),
    'Server':(last,),
    'Vary':(tokenize, filterTokens),
#    'WWW-Authenticate'
}

generator_response_headers = {
    'Accept-Ranges':(generateList, singleHeader),
    'Age':(str, singleHeader),
#    'ETag'
    'Location':(str, singleHeader),
#    'Proxy-Authenticate'
##    'Retry-After':(generateRetryAfter, singleHeader),
    'Server':(str, singleHeader),
    'Vary':(generateList, singleHeader),
#    'WWW-Authenticate'
}

parser_entity_headers = {
    'Allow':(lambda str:tokenize(str, foldCase=False), filterTokens),
    'Content-Encoding':(tokenize, filterTokens),
    'Content-Language':(tokenize, filterTokens),
    'Content-Length':(last, int),
    'Content-Location':(last,),
    'Content-MD5':(last,),
#    'Content-Range'
#    'Content-Type'
#    'Expires'
    'Last-Modified':(last, parseDateTime),
    }

generator_entity_headers = {
    'Allow':(generateList, singleHeader),
    'Content-Encoding':(generateList, singleHeader),
    'Content-Language':(generateList, singleHeader),
    'Content-Length':(str, singleHeader),
    'Content-Location':(str, singleHeader),
    'Content-MD5':(str, singleHeader),
#    'Content-Range':
#    'Content-Type':
#    'Expires':
    'Last-Modified':(generateDateTime, singleHeader),
    }

DefaultHTTPParsers = dict()
DefaultHTTPParsers.update(parser_general_headers)
DefaultHTTPParsers.update(parser_request_headers)
DefaultHTTPParsers.update(parser_entity_headers)

DefaultHTTPGenerators = dict()
DefaultHTTPGenerators.update(generator_general_headers)
DefaultHTTPGenerators.update(generator_request_headers)
DefaultHTTPGenerators.update(generator_entity_headers)

