"""Post-office Protocol version 3
"""


from twisted.protocols import basic
import os, time, string, operator, stat, md5, binascii
import protocol

class POP3Error(Exception):
    pass

class POP3(basic.LineReceiver):

    magic = None

    def connectionMade(self):
        if self.magic is None:
            self.magic = '<%s>' % time.time()
        self.mbox = None
        self.successResponse(self.magic)

    def successResponse(self, message=''):
        self.transport.write('+OK %s\r\n' % message)

    def failResponse(self, message=''):
        self.transport.write('-ERR %s\r\n' % message)

    def lineReceived(self, line):
        try:
            return apply(self.processCommand, tuple(string.split(line)))
        except (ValueError, AttributeError, POP3Error), e:
            self.failResponse('bad protocol or server: %s: %s' % (e.__class__.__name__, e))

    def processCommand(self, command, *args):
        command = string.upper(command)
        if self.mbox is None and command != 'APOP':
            raise POP3Error("not authenticated yet: cannot do %s" % command)
        return apply(getattr(self, 'do_'+command), args)

    def do_APOP(self, user, digest):
        self.mbox = self.authenticateUserAPOP(user, digest)
        self.successResponse()

    def do_LIST(self, i=None):
        messages = self.mbox.listMessages() 
        total = reduce(operator.add, messages, 0)
        self.successResponse(len(messages))
        i = 1
        for message in messages:
            if message:
                self.transport.write('%d %d\r\n' % (i, message)) 
            i = i+1
        self.transport.write('.\r\n')

    def do_UIDL(self, i=None):
        messages = self.mbox.listMessages() 
        self.successResponse()
        for i in range(len(messages)):
            if messages[i]:
                self.transport.write('%d %s\r\n' % (i+1, self.mbox.getUidl(i))) 
        self.transport.write('.\r\n')

    def getMessageFile(self, i):
        i = int(i)-1
        list = self.mbox.listMessages()
        try:
            resp = list[i]
        except IndexError:
            self.failResponse('index out of range')
            return None, None
        if not resp:
            self.failResponse('message deleted')
            return None, None
        return resp, self.mbox.getMessage(i)

    def do_TOP(self, i, size):
        resp, fp = self.getMessageFile(i)
        if not fp:
            return
        size = max(int(size), resp)
        self.successResponse(size)
        while size:
            line = fp.readline()
            if not line:
                break
            if line[-1] == '\n':
                line = line[:-1]
            if line[:1] == '.':
                line = '.'+line
            self.transport.write(line[:size]+'\r\n')
            size = size-len(line[:size])
            

    def do_RETR(self, i):
        resp, fp = self.getMessageFile(i)
        if not fp:
            return
        self.successResponse(resp)
        while 1:
            line = fp.readline()
            if not line:
                break
            if line[-1] == '\n':
                line = line[:-1]
            if line[:1] == '.':
                line = '.'+line
            self.transport.write(line+'\r\n')
        self.transport.write('.\r\n')

    def do_DELE(self, i):
        i = int(i)-1
        self.mbox.deleteMessage(i)
        self.successResponse()

    def do_QUIT(self):
        self.mbox.sync()
        self.successResponse()
        self.transport.loseConnection()

    def authenticateUserAPOP(self, user, digest):
        return Mailbox()


class Mailbox:

    def listMessages(self):
        return []
    def getMessage(self, i):
        raise ValueError
    def getUidl(self, i):
        raise ValueError
    def deleteMessage(self, i):
        raise ValueError
    def sync(self):
        pass


NONE, SHORT, FIRST_LONG, LONG = range(4)

NEXT = {}
NEXT[NONE] = NONE
NEXT[SHORT] = NONE
NEXT[FIRST_LONG] = LONG
NEXT[LONG] = NONE

class POP3Client(basic.LineReceiver):

    mode = SHORT
    command = 'WELCOME'

    def sendShort(self, command, params):
        self.transport.write('%s %s\r\n' % (command, params))
        self.command = command
        self.mode = SHORT

    def sendLong(self, command):
        self.transport.write('%s %s\r\n' % (command, params))
        self.command = command
        self.mode = FIRST_LONG

    def handle_default(self, line):
        if line[:-4] == '-ERR':
            self.mode = NONE

    def lineReceived(self, line):
        if self.mode == SHORT or self.mode == FIRST_LONG:
            self.mode = NEXT[self.mode]
            method = getattr(self, 'handle_'+self.command, self.handle_default)
            method(line)
        elif self.mode == LONG:
            if line == '.':
                self.mode = NEXT[self.mode]
                method = getattr(self, 'handle_'+self.command+'_end', None)
                if method is not None:
                    method(line)
                return
            if line[:1] == '.':
                line = line[1:]
            method = getattr(self, 'handle_'+self.command+'_continue', None)
            if method is not None:
                method(line)

    def retr(self, i):
        self.sendLong('RETR', i)
    def dele(self, i):
        self.sendShort('DELE', i)
    def list(self, i=''):
        self.sendLong('LIST', i)
    def uidl(self, i=''):
        self.sendLong('UIDL', i)
    def user(self, name):
        self.sendShort('USER', name)
    def pass_(self, pass_):
        self.sendShort('PASS', pass_)
    def quit(self):
        self.sendShort('QUIT')


class VirtualPOP3(POP3):

    domainSpecifier = '@' # Gaagh! I hate POP3. No standardized way
                          # to indicate user@host. '@' doesn't work
                          # with NS, e.g.
    def authenticateUserAPOP(self, user, digest):
        try:
            user, domain = string.split(user, self.domainSpecifier, 1)
        except ValueError:
            domain = ''
        if not self.factory.domains.has_key(domain):
             raise POP3Error("no such domain %s" % domain)
        domain = self.factory.domains[domain]
        mbox = domain.authenticateUserAPOP(user, self.magic, digest, domain)
        if mbox is None:
            raise POP3Error("bad authentication")
        return mbox
