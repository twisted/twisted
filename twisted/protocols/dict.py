"""
dict protocol stuff. Everything looks like twisted.protocols.smtp.* for a good reason.
"""

from twisted.protocols import basic
from twisted.internet import defer
from twisted.python import log
from StringIO import StringIO

class DictClient(basic.LineReceiver):
    """dict (RFC2229) client"""

    # list of query results, which are tuples of word, database, name, list of lines
    query = None
    d = None
    MAX_LENGTH = 1024

    def parseParam(self, line):
        """Chew one dqstring or atom from beginning of line and return (param, remaningline)"""
        if line == '':
            return (None, '')
        elif line[0] != '"': # atom
            mode = 1
        else: # dqstring
            mode = 2
        res = ""
        io = StringIO(line)
        if mode == 2: # skip the opening quote
            io.read(1)
        while 1:
            a = io.read(1)
            if a == '"':
                if mode == 2:
                    io.read(1) # skip the separating space
                    return (res, io.read())
            elif a == '\\':
                a = io.read(1)
                if a == '':
                    return (None, line) # unexpected end of string
            elif a == '':
                if mode == 1:
                    return (res, io.read())
                else:
                    return (None, line) # unexpected end of string
            elif a == ' ':
                if mode == 1:
                    return (res, io.read())
            res += a

    def connectionMade(self):
        self.state = "conn"

    def lineReceived(self, line):
        try:
            line = line.decode("UTF-8")
        except UnicodeError: # garbage received, skip
            return
        if self.state == "answtext": # we are receiving textual data
            self.dictCode_answtext(line)
            return
        if len(line) < 4:
            raise ValueError("invalid line from dict server %s" % line)
        code = int(line[:3])
        method =  getattr(self, 'dictCode_%d_%s' % (code, self.state), 
                                self.dictCode_default)
        method(line[4:])

    def makeAtom(self, line):
        """Munch a string into an 'atom'"""
        return filter(lambda x: not (x in map(chr, range(33)+[34, 39, 92])), line)
    
    def dictCode_default(self, line):
        log.msg("DictClient got unexpected message from server -- %s" % line)
        self.transport.loseConnection()
        if self.d:
            self.query = []
            self.dictCode_250_querying("")

    def dictCode_221_rdy(self, line):
        "We are about to get kicked off, do nothing"
        pass

    def dictCode_220_conn(self, line):
        "Greeting message"
        self.state = "rdy"

    def sendDefine(self, database, word):
        "Send a dict DEFINE command"
        assert self.state == "rdy", "DictClient.sendDefine called when not in ready state"
        command = "DEFINE %s %s" % (self.makeAtom(database), self.makeAtom(word))
        if len(command) > 1022:
            raise ValueError("Command string too long")
        self.state = "querying"
        self.query = []
        self.sendLine(command.encode("UTF-8"))
        self.d = defer.Deferred()
        return self.d

    def dictCode_550_querying(self, line):
        "Nonexistent database"
        self.dictCode_552_querying(line)

    def dictCode_552_querying(self, line):
        "No match"
        self.query = []
        self.dictCode_250_querying(line)

    def dictCode_150_querying(self, line):
        "n definitions retrieved"
        pass

    def dictCode_151_querying(self, line):
        "definition text follows"
        self.state = "answtext"
        (word, line) = self.parseParam(line)
        (database, line) = self.parseParam(line)
        (name, line) = self.parseParam(line)
        if not (word and database and name):
            return
        self.query.append((word, database, name, []))

    def dictCode_answtext(self, line):
        "textual data received"
        if len(line) == 1 and line[0] == '.':
            self.state = "querying"
            return
        if len(line) > 1 and line[0:2] == '..':
            line = line[1:]
        self.query[-1][3].append(line)

    def dictCode_250_querying(self, line):
        "ok"
        d = self.d
        query = self.query
        self.d = None
        self.query = None
        self.state = "rdy"
        d.callback(query)
