# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""NNTP protocol support.

  The following protocol commands are currently understood:
    LIST        LISTGROUP    NEWSGROUPS    XOVER    XHDR
    POST        GROUP        ARTICLE       STAT     HEAD
    BODY        NEXT         LAST          MODE     QUIT
    
  The following protocol commands require implementation:
    HELP        IHAVE        NEWNEWS       SLAVE    CHECK
    MODE STREAM TAKETHIS     XGTITLE       XINDEX   XPAT
    XPATH       XROVER       XTHREAD       AUTHINFO NEWGROUPS


  Other desired features:
    A real backend
    More robust client input handling
    A control protocol
"""

from twisted.protocols import basic
from twisted.python import log

import string, random, socket

def parseRange(text):
    articles = text.split('-')
    if len(articles) == 1:
        try:
            a = int(articles[0])
            return a, a
        except ValueError, e:
            return None, None
    elif len(articles) == 2:
        try:
            if len(articles[0]):
                l = int(articles[0])
            else:
                l = None
            if len(articles[1]):
                h = int(articles[1])
            else:
                h = None
        except ValueError, e:
            return None, None
    return l, h
    
class NNTPError(Exception):
    def __init__(self, string):
        self.string = string

    def __str__(self):
        return 'NNTPError: %s' % self.string

class NNTPClient(basic.LineReceiver):
    # State constants
    ST_INITIAL, ST_GROUP, ST_LIST, ST_ARTICLE, ST_HEAD, ST_BODY, ST_POST, ST_POSTED = range(8)

    def __init__(self):
        self.state = []
        self.state.append(NNTPClient.ST_INITIAL)
        self.currentGroup = None

    def connectionMade(self):
        try:
            self.ip = self.transport.socket.getpeername()
        #We're not always connected with a socket
        except AttributeError:
            self.ip = "unknown"

    def gotAllGroups(self, groups):
        "Override for notification when fetchGroups() action is completed"
        pass

    def gotGroup(self, info):
        "Override for notification when fetchGroup() action is completed"
        pass

    def gotArticle(self, info):
        "Override for notification when fetchArticle() action is completed"
        pass

    def gotHead(self, info):
        "Override for notification when fetchHead() action is completed"
        pass

    def gotBody(self, info):
        "Override for notification when fetchBody() action is completed"
        pass

    def postOk(self):
        "Override for notification when postArticle() action is successful"
        pass
    
    def postFailed(self, error):
        "Override for notification when postArticle() action fails"
        pass

    def fetchGroups(self):
        log.msg('%s: fetchGroups()' % self.ip)
        self.sendLine('LIST')
        self.state.append(NNTPClient.ST_LIST)
        self._groups = None

    def fetchGroup(self, group):
        log.msg('%s: fetchGroup()' % self.ip)
        self.sendLine('GROUP %s' % group)
        self.state.append(NNTPClient.ST_GROUP)

    def fetchHead(self, index):
        log.msg('%s: fetchHead(%s)' % (self.ip, index))
        self.sendLine('HEAD %d' % index)
        self.state.append(NNTPClient.ST_HEAD)
        self._head = None
        
    def fetchBody(self, index):
        log.msg('%s: fetchBody(%s)' % (self.ip, index))
        self.sendLine('BODY %d' % index)
        self.state.append(NNTPClient.ST_BODY)
        self._body = None

    def fetchArticle(self, index):
        log.msg('%s: fetchArticle(%s)' % (self.ip, index))
        self.sendLine('ARTICLE %d' % index)
        self.state.append(NNTPClient.ST_ARTICLE)
        self._article = None

    def postArticle(self, text):
        log.msg('%s: postArticle()')
        self.sendLine('POST')
        self.state.append(NNTPClient.ST_POST)
        self._postText = text

    def lineReceived(self, line):
        if len(self.state):
            apply(getattr(self, NNTPClient.states[self.state[0]]), (line,))
        else:
            self._statePassive(self, line)

    def _statePassive(self, line):
        print 'Server said: ', line

    def _stateInitial(self, line):
        l = filter(None, string.split(string.strip(line)))
        try:
            status = int(l[0])
        except ValueError:
            raise NNTPError('Invalid server response: %s' % l[0])
        except IndexError:
            raise NNTPError('Empty server response')
        else:
            if status / 100 != 2:
                raise NNTPError('Server responded: %s' % line)
            del self.state[0]

    def _stateList(self, line):
        if self._groups != None:
            if line == '.':
                del self.state[0]
                groups, self._groups = self._groups, None
                self.gotAllGroups(groups)
            else:
                l = filter(None, string.split(string.strip(line)))
                self._groups.append((l[0], int(l[1]), int(l[2]), l[3]))
                log.msg('%s: got group: %s' % (self.ip, self._groups[-1]))
        else:
            try:
                x = int(string.split(line)[0])
                if x / 100 != 2:
                    del self.state[0]
                    self.sendLine('501 command parse error')
                else:
                    self._groups = []
            except Exception, e:
                print '_stateList exception:', e
        
    def _stateGroup(self, line):
        info = string.split(string.strip(line))
        if int(info[0]) / 100 != 2:
            raise NNTPError('Invalid GROUP response: %s' % line)
        else:
            del self.state[0]
            self.gotGroup(tuple(info[1:]))

    def _stateArticle(self, line):
        if self._article != None:
            if line == '.':
                del self.state[0]
                article, self._article = self._article, None
                self.gotArticle(article)
            else:
                self._article = self._article + line + '\n'
        else:
            try:
                x = int(string.split(line)[0])
                if x / 100 != 2:
                    del self.state[0]
                    self.sendLine('501 command parse error')
                else:
                    self._article = ''
            except Exception, e:
                print '_stateArticle exception: ', e

    def _stateHead(self, line):
        if self._head != None:
            if line == '.':
                del self.state[0]
                head = self._head
                self._head = None
                self.gotHead(head)
            else:
                self._head = self._head + line + '\n'
        else:
            try:
                x = int(string.split(line)[0])
                if x / 100 != 2:
                    del self.state[0]
                    self.sendLine('501 command parse error')
                else:
                    self._head = ''
            except Exception, e:
                print '_stateHead exception', e

    def _stateBody(self, line):
        if self._body != None:
            if line == '.':
                del self.state[0]
                body = self._body
                self._body = None
                self.gotBody(body)
            else:
                self._body = self._body + line + '\n'
        else:
            try:
                x = int(string.split(line)[0])
                if x / 100 != 2:
                    del self.state[0]
                    self.sendLine('501 command parse error')
                else:
                    self._body = ''
            except Exception, e:
                print '_stateBody exception', e

    def _statePost(self, line):
        del self.state[0]
        code = string.split(line)
        if len(code):
            code = int(code[0])
            if code == 340:
                self.transport.write(self._postText)
                if self._postText[-2:] != '\r\n':
                    self.sendLine('\r\n')
                self.sendLine('.')
                self.state.append(NNTPClient.ST_POSTED)
            else:
                self.postFailed(line)
        else:
            self.postFailed('No response')

    def _statePosted(self, line):
        del self.state[0]
        code = string.split(line)
        if len(code):
            code = int(code[0])
            if code == 240:
                self.postOk()
            else:
                self.postFailed(line)

    # A function/state for each command we can transmit,
    # plus the initial state
    states = (
        '_stateInitial', '_stateGroup', '_stateList',
        '_stateArticle', '_stateHead', '_stateBody',
        '_statePost', '_statePosted'
    )


class NNTPServer(NNTPClient):
    COMMANDS = [
        'LIST', 'GROUP', 'ARTICLE', 'STAT', 'NEWSGROUPS',
        'MODE', 'LISTGROUP', 'XOVER', 'XHDR', 'HEAD', 'BODY',
        'NEXT', 'LAST', 'POST', 'QUIT'
    ]

    def __init__(self):
        NNTPClient.__init__(self)

    def connectionMade(self):
        try:
            self.ip = self.transport.socket.getpeername()
        #We're not always connected with a socket
        except AttributeError:
            self.ip = "unknown"
        self.posting = 0
        self.currentGroup = None
        self.currentIndex = None
        self.sendLine('200 server ready - posting allowed')

    def lineReceived(self, line):
#        print line
        if self.posting == 1:
            self._doingPost(line)
        else:
            parts = filter(None, string.split(string.strip(line)))
            if len(parts):
                cmd, parts = string.upper(parts[0]), parts[1:]
                if cmd in NNTPServer.COMMANDS:
                    func = getattr(self, 'do_%s' % cmd)
                    apply(func, (parts,))
                else:
                    self.sendLine('500 command not recognized')

    def do_LIST(self, parts):
        if parts:
            subcmd = string.lower(parts[0])
            if subcmd == 'newsgroups':
                self.sendLine('215 Descriptions in form "group description".')
                self.sendLine('.')
            elif subcmd == 'overview.fmt':
                defer = self.factory.backend.overviewRequest()
                defer.addCallbacks(self._gotOverview, self._errOverview)
                print 'overview'
            elif subcmd == 'subscriptions':
                defer = self.factory.backend.subscriptionRequest()
                defer.addCallbacks(self._gotSubscription, self._errSubscription)
                print 'subscriptions'
            else:
                self.sendLine('500 command not recognized')
        else:
            defer = self.factory.backend.listRequest()
            defer.addCallbacks(self._gotList, self._errList)

    def _gotList(self, list):
        # Currently a RFC 977 list - understand no arguments
        self.sendLine('215 newsgroups in form "group high low flags"')
        for i in list:
            self.sendLine('%s %d %d %s' % i)
        self.sendLine('.')

    def _errList(self, error):
        self.sendLine('%s' % str(error))

    def _gotSubscription(self, parts):
        self.sendLine('215 information follows')
        for i in parts:
            self.sendLine(i)
        self.sendLine('.')

    def _errSubscription(self):
        self.sendLine('503 program error, function not performed')

    def _gotOverview(self, parts):
        self.sendLine('215 Order of fields in overview database.')
        for i in parts:
            self.sendLine(i + ':')
        self.sendLine('.')

    def _errOverview(self):
        self.sendLine('503 program error, function not performed')


    def do_LISTGROUP(self, parts):
        if len(parts):
            group = parts[0]
        else:
            if self.currentGroup is None:
                self.sendLine('412 Not currently in newsgroup')
                return
            else:
                group = self.currentGroup
        
        defer = self.factory.backend.listGroupRequest(group)
        defer.addCallbacks(self._gotListGroup, self._errListGroup)

    def _gotListGroup(self, parts):
        group, articles = parts
        self.currentGroup = group
        if len(articles):
            self.currentIndex = int(articles[0])
        else:
            self.currentIndex = None

        self.sendLine('211 list of article numbers follow')
        for i in articles:
            self.sendLine('%d' % i)
        self.sendLine('.')

    def _errListGroup(self):
        self.sendLine('502 no permission')


    def do_NEWSGROUPS(self, parts):
        pass


    def do_XOVER(self, parts):
        if self.currentGroup is None:
            self.sendLine('412 No news group currently selected')
        else:
            if not len(parts):
                self.sendLine('501 command syntax error')
                return
            l, h = parseRange(parts[0])
            defer = self.factory.backend.xoverRequest(self.currentGroup, l, h)
            defer.addCallbacks(self._gotXOver, self._errXOver)

    def _gotXOver(self, parts):
        self.sendLine('224 Overview information follows')
        for i in parts:
            self.sendLine(string.join(i, '\t'))
        self.sendLine('.')

    def _errXOver(self, error):
        self.sendLine('420 No article(s) selected')


    def do_XHDR(self, parts):
        if self.currentGroup is None:
            self.sendLine('412 No news group currently selected')
        else:
            if len(parts) == 0:
                self.sendLine('501 header [range|MessageID]')
            elif len(parts) == 1:
                if self.currentIndex is None:
                    self.sendLine('420 No current article selected')
                    return
                else:
                    header = parts[0]
                    l = h = self.currentIndex
            else:
                header, articles = parts
                # FIXME: articles may be a message-id
                l, h = parseRange(articles)

            if l is h is None:
                self.sendLine('430 no such article')
            else:
                defer = self.factory.backend.xhdrRequest(self.currentGroup, l, h, header)
                defer.addCallbacks(self._gotXHDR, self._errXHDR)

    def _gotXHDR(self, parts):
        self.sendLine('221 Header follows')
        for i in parts:
            self.sendLine('%d %s' % i)
        self.sendLine('.')

    def _errXHDR(self):
        self.sendLine('502 no permission')


    def do_POST(self, parts):
        self.posting = 1
        self.message = ''
        self.sendLine('340 send article to be posted.  End with <CR-LF>.<CR-LF>')

    def _doingPost(self, line):
        if line == '.':
            self.posting = 0
            group, article = self.currentGroup, self.message
            del self.message

            defer = self.factory.backend.postRequest(article)
            defer.addCallbacks(self._gotPost, self._errPost)
        else:
            if line and line[0] == '.':
                line = '.' + line
            self.message = self.message + line + '\r\n'

    def _gotPost(self, parts):
        self.sendLine('240 article posted ok')
    
    def _errPost(self, parts):
        self.sendLine('441 posting failed')


    def do_GROUP(self, parts):
        defer = self.factory.backend.groupRequest(parts[0])
        defer.addCallbacks(self._gotGroup, self._errGroup)
    
    def _gotGroup(self, parts):
        name, num, high, low, flags = parts
        self.currentGroup = name
        self.currentIndex = low
        self.sendLine('211 %d %d %d %s group selected' % (num, low, high, name))
    
    def _errGroup(self, group):
        self.sendLine('411 no such group')


    def do_ARTICLE(self, parts):
        if len(parts):
            if parts[0][0] == '<':
                # FIXME: Request for article by message-id not implemented
                self.sendLine('501 ARTICLE <message-id> not implemented :(')
            else:
                i = int(parts[0])
        else:
            i = self.currentIndex
        defer = self.factory.backend.articleRequest(self.currentGroup, i)
        defer.addCallbacks(self._gotArticle, self._errArticle)

    def _gotArticle(self, parts):
        index, id, article = parts
        self.currentIndex = index
        self.sendLine('220 %d %s article' % (index, id))
        self.transport.write(article)
        self.sendLine('.')

    def _errArticle(self, article):
        self.sendLine('423 bad article number')


    def do_STAT(self, parts):
        if len(parts):
            i = int(parts[0])
        else:
            i = self.currentIndex
        defer = self.factory.backend.articleRequest(self.currentGroup, i)
        defer.addCallbacks(self._gotStat, self._errStat)
    
    def _gotStat(self, parts):
        index, id, article = parts
        self.currentIndex = index
        self.sendLine('223 %d %s article retreived - request text separately' % (index, id))

    def _errStat(self, parts):
        self.sendLine('423 bad article number')


    def do_HEAD(self, parts):
        if len(parts):
            i = int(parts[0])
        else:
            i = self.currentIndex
        defer = self.factory.backend.headRequest(self.currentGroup, i)
        defer.addCallbacks(self._gotHead, self._errHead)
    
    def _gotHead(self, parts):
        index, id, head = parts
        self.currentIndex = index
        self.sendLine('221 %d %s article retrieved' % (index, id))
        self.transport.write(head + '\r\n')
        self.sendLine('.')
    
    def _errHead(self, head):
        self.sendLine('423 no such article number in this group')


    def do_BODY(self, parts):
        if len(parts):
            i = int(parts[0])
        else:
            i = self.currentIndex
        defer = self.factory.backend.bodyRequest(self.currentGroup, i)
        defer.addCallbacks(self._gotBody, self._errBody)

    def _gotBody(self, parts):
        index, id, body = parts
        self.currentIndex = index
        self.sendLine('221 %d %s article retrieved' % (index, id))
        self.transport.write(body.replace('\r\n..', '\r\n.') + '\r\n')
        self.sendLine('.')

    def _errBody(self, body):
        self.sendLine('423 no such article number in this group')


    # NEXT and LAST are just STATs that increment currentIndex first.
    # Accordingly, use the STAT callbacks.
    def do_NEXT(self, parts):
        i = self.currentIndex + 1
        defer = self.factory.backend.articleRequest(self.currentGroup, i)
        defer.addCallbacks(self._gotStat, self._errStat)

    def do_LAST(self, parts):
        i = self.currentIndex - 1
        defer = self.factory.backend.articleRequest(self.currentGroup, i)
        defer.addCallbacks(self._gotStat, self._errStat)


    def do_MODE(self, parts):
        self.sendLine('200 Hello, you can post')


    def do_QUIT(self, parts):
        self.sendLine('205 goodbye')
        self.transport.loseConnection()


    def sendLine(self, line):
#        print 'sending: ', line
        basic.LineReceiver.sendLine(self, line)
