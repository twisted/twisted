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

    def __eq__(self, other):
        return self is other
    
    def __repr__(self):
        return "Token(%s)" % str.__repr__(self)


def tokenize(header, tokens=" \t\"()<>@,;:\\/[]?={}"):
    """Tokenize a string according to normal HTTP header parsing rules.

    In particular:
    - Whitespace is irrelevant and eaten next to special separator tokens.
      Its existance (but not amount) is important between character strings.
    - Quoted string support including embedded backslashes.
    - Case is insignificant (and thus lowercased), except in quoted strings.
    - Multiple headers are concatenated with ','
    
    NOTE: not all headers can be parsed with this function.
    
    Takes a raw header value (list of strings), and
    Returns a generator of strings and Token class instances.
    """
    
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
                yield string[start:cur].lower()
                
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
        yield string[start:cur].lower()

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
    """Filter out instances of Token, leaving only strings.
    
    Used instead of a more specific parsing method (e.g. splitting on commas)
    when only strings are expected, so as to be a little lenient.

    Apache does it this way and has some comments about broken clients which
    forget commas (?), so I'm doing it the same way. It shouldn't
    hurt anything, in any case.
    """
    
    for x in seq:
        if not isinstance(x, Token):
            yield x

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
def parseAcceptMIME(field):
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

def parseRange(range):
    range = list(range)
    if len(range) != 3 or range[1] != Token('='):
        raise ValueError("Invalid range header format: "+range)
    type=range[0]
    startend=range[2].split('-',1)
    if len(startend) != 2:
        raise ValueError("Invalid range header format: "+range)
    start,end=startend
    return type,start,end


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
        
        if (acceptType == type or acceptType == (type[0],'*') or acceptType==('*','*')) and (args == acceptArgs or len(acceptArgs) == 0):
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

class ReceivedHeaders:
    def __init__(self, parsers):
        self._raw_headers = {}
        self._headers = {}
        self.parsers=parsers

    def _addHeader(self, name, strvalue):
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
    
    def getHeaderRaw(self, name):
        """Returns a list of headers matching the given name as the raw string given."""
        return _raw_headers[name]
    
    def getHeader(self, name):
        """Returns the parsed representation of the given header.
        The exact form of the return value depends on the header in question.

        If no parser for the header exists, raise ValueError.
        If the header doesn't exist, raise KeyError"""
        
        parsed = self._headers.get(name, None)
        if parsed:
            return parsed
        parser = self._parser(name)

        h = self._raw_headers[name]
        for p in parser:
#            print "Parsing %s: %s(%s)" % (name, repr(p), repr(h))
            h = p(h)
#            if isinstance(h, types.GeneratorType):
#                h=list(h)
        
        self._headers[name]=h
        return h



def datetimeToString(msSinceEpoch=None):
    """Convert seconds since epoch to HTTP datetime string."""
    if msSinceEpoch == None:
        msSinceEpoch = time.time()
    year, month, day, hh, mm, ss, wd, y, z = gmtime(msSinceEpoch)
    s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
        weekdayname[wd],
        day, monthname[month], year,
        hh, mm, ss)
    return s




"""The following dicts are all mappings of header to list of operations
   to perform. The first operation should generally be 'tokenize' if the
   header can be parsed according to the normal tokenization rules. If
   it cannot, generally the first thing you want to do is take only the
   last instance of the header (in case it was sent multiple times, which
   is strictly an error, but we're nice.).
   """

general_headers = {
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


request_headers = {
    'Accept': (tokenize, listParser(parseAcceptMIME), dict),
    'Accept-Charset': (tokenize, listParser(parseAcceptQvalue), dict, addDefaultCharset),
    'Accept-Encoding':(tokenize, listParser(parseAcceptQvalue), dict, addDefaultEncoding),
    'Accept-Language':(tokenize, listParser(parseAcceptQvalue), dict),
#    'Authorization':str # what is "credentials"
#    'Expect':(tokenize, listParser(parseExpect), dict),
    'From':(last,str),
    'Host':(last,str),
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

response_headers = {
#    'Accept-Ranges'
#    'Age'
#    'ETag'
#    'Location'
#    'Proxy-Authenticate'
#    'Retry-After'
#    'Server'
#    'Vary'
#    'WWW-Authenticate'
}

entity_headers = {
#    'Allow'
#    'Content-Encoding'
#    'Content-Language'
#    'Content-Length'
#    'Content-Location'
#    'Content-MD5'
#    'Content-Range'
#    'Content-Type'
#    'Expires'
#    'Last-Modified'
    }

DefaultHTTPParsers = dict()
DefaultHTTPParsers.update(general_headers)
DefaultHTTPParsers.update(request_headers)
DefaultHTTPParsers.update(entity_headers)


