#       CTL            = <any US-ASCII control character
#                               (octets 0 - 31) and DEL (127)>
# 
#        separators     = "(" | ")" | "<" | ">" | "@"
#                       | "," | ";" | ":" | "\" | <">
#                       | "/" | "[" | "]" | "?" | "="
#                       | "{" | "}" | SP | HT

#       quoted-string  = ( <"> *(qdtext | quoted-pair ) <"> )
#       qdtext         = <any TEXT except <">>
#       quoted-pair    = "\" CHAR

#def parseQuoted(string):
    
token_seperators = " \t()<>@,;:\\/[]?={}"
def parseDelimList(itemparser, delim=','):
    def parse(string):
        list = []
        start = 0
        cur = 0
        quoted = False
        qpair = False
        inInitialSpaces = True
        
        for x in string:
            if quoted:
                if x == '\\':
                    qpair = True
                if not qpair and x == '"':
                    quoted = False
            else:
                if x == '"':
                    quoted = True
                elif x == delim:
                    yield itemparser(string[start:lastNonSpace])
                    start = cur+1
                    inInitialSpaces = True
                elif x == ' ' or x == '\t':
                    if inInitialSpaces:
                        start = cur+1
                else:
                    inInitialSpaces = False
            cur = cur + 1
            if not (x == ' ' or x == '\t'):
                lastNonSpace = cur
        if qpair:
            raise "Missing character after '\\'"
        if quoted:
            raise "Missing end quote"

        yield itemparser(string[start:lastNonSpace])
    return parse

def parseKeyValue(s):
    keyValue = list(parseDelimList(str,delim='=')(s))
    if len(keyValue) > 2:
        raise "Syntax error, too many equalses: "+s+"."
    return keyValue

def parseArgs(s):
    argstart = s.find(';')
    if argstart != -1:
        val=s[:argstart]
        args=s[argstart+1:]
    else:
        val=s
    
    args = dict(parseDelimList(parseKeyValue, delim=';')(args))
    return val,args

def parseAccept(s):
    type,args = parseArgs(s)
    type=type.split('/')
    if len(type) != 2:
        raise "MIME Type "+s+" invalid."
    
    return type, args


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
    def __init__(self):
        _raw_headers = []
        _headers = []

    def _addHeader(self, name, strvalue):
        old = _raw_headers.get(name, None)
        if old is None:
            old = []
            _raw_headers[name]=old
        old.append(strvalue)
    
    def parser(self, name):
        parser = self.parsers.get(name, None)
        if not parser:
            raise IllegalArgumentException("No header parser for header '%s', either add one or use getHeaderRaw.")
        return parser
    
    def getHeaderRaw(self, name):
        """Returns a sequence of headers matching the given name as the raw string given."""
        return _raw_headers[name]
    
    def getHeader(self, name):
        parsed = _headers.get(name, None)
        if parsed:
            return parsed
        _headers[name] = parser(name)(_raw_headers.get[name])


def datetimeToString(msSinceEpoch=None):
    """Convert seconds since epoch to HTTP datetime string."""
    if msSinceEpoch == None:
        msSinceEpoch = time.time()
    year, month, day, hh, mm, ss, wd, y, z = time.gmtime(msSinceEpoch)
    s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
        weekdayname[wd],
        day, monthname[month], year,
        hh, mm, ss)
    return s

def parseDateTime(dateString):
    """Convert an HTTP date string to seconds since epoch."""
    # BUGGY doesn't support all date formats
    parts = dateString.split(' ')
    day = int(parts[1])
    month = int(monthname.index(parts[2]))
    year = int(parts[3])
    hour, min, sec = map(int, parts[4].split(':'))
    return int(timegm(year, month, day, hour, min, sec))



general_headers = {
#    'Cache-Control':parseDelimList
    'Connection':parseDelimList(str),
    'Date':parseDateTime,
#    'Pragma':parseDelimList
#    'Trailer':parseDelimList
    'Transfer-Encoding':parseDelimList(str)
#    'Upgrade':parseDelimList
#    'Via':list with comment
#    'Warning':parseDelimList
}

request_headers = {
    'Accept': parseDelimList(parseAccept),
    'Accept-Charset': parseDelimList(str),
    'Accept-Encoding':None,
    'Accept-Language':None,
    'Authorization':None,
    'Expect':None,
    'From':None,
    'Host':None,
    'If-Match':None,
    'If-Modified-Since':None,
    'If-None-Match':None,
    'If-Range':None,
    'If-Unmodified-Since':None,
    'Max-Forwards':None,
    'Proxy-Authorization':None,
    'Range':None,
    'Referer':None,
    'TE':None,
    'User-Agent':None,
}
