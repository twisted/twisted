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
    LIST        LISTGROUP                  XOVER        XHDR
    POST        GROUP        ARTICLE       STAT         HEAD
    BODY        NEXT         MODE STREAM   MODE READER  SLAVE
    LAST        QUIT         HELP          IHAVE        XPATH
    XINDEX      XROVER       TAKETHIS      CHECK
    
  The following protocol commands require implementation:
                             NEWNEWS
                             XGTITLE                XPAT
                             XTHREAD       AUTHINFO NEWGROUPS


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


def extractCode(line):
    line = line.split(' ', 1)
    if len(line) != 2:
        return None
    try:
        return int(line[0]), line[1]
    except ValueError:
        return None

    
class NNTPError(Exception):
    def __init__(self, string):
        self.string = string

    def __str__(self):
        return 'NNTPError: %s' % self.string


class NNTPClient(basic.LineReceiver):
    def __init__(self):
        self.currentGroup = None
        
        self._state = []
        self._error = []
        self._inputBuffers = []
        self._responseCodes = []
        self._responseHandlers = []
        
        self._postText = []
        
        self._newState(self._statePassive, None, self._headerInitial)


    def connectionMade(self):
        try:
            self.ip = self.transport.socket.getpeername()
        # We're not always connected with a socket
        except AttributeError:
            self.ip = "unknown"


    def gotAllGroups(self, groups):
        "Override for notification when fetchGroups() action is completed"
    
    
    def getAllGroupsFailed(self, error):
        "Override for notification when fetchGroups() action fails"


    def gotOverview(self, overview):
        "Override for notification when fetchOverview() action is completed"


    def getOverviewFailed(self, error):
        "Override for notification when fetchOverview() action fails"


    def gotSubscriptions(self, subscriptions):
        "Override for notification when fetchSubscriptions() action is completed"


    def getSubscriptionsFailed(self, error):
        "Override for notification when fetchSubscriptions() action fails"


    def gotGroup(self, group):
        "Override for notification when fetchGroup() action is completed"


    def getGroupFailed(self, error):
        "Override for notification when fetchGroup() action fails"


    def gotArticle(self, article):
        "Override for notification when fetchArticle() action is completed"


    def getArticleFailed(self, error):
        "Override for notification when fetchArticle() action fails"


    def gotHead(self, head):
        "Override for notification when fetchHead() action is completed"


    def getHeadFailed(self, error):
        "Override for notification when fetchHead() action fails"


    def gotBody(self, info):
        "Override for notification when fetchBody() action is completed"


    def getBodyFailed(self, body):
        "Override for notification when fetchBody() action fails"


    def postedOk(self):
        "Override for notification when postArticle() action is successful"

    
    def postFailed(self, error):
        "Override for notification when postArticle() action fails"


    def gotXHeader(self, headers):
        "Override for notification when getXHeader() action is successful"
    
    
    def getXHeaderFailed(self, error):
        "Override for notification when getXHeader() action fails"


    def fetchGroups(self):
        """fetchGroups(self)
        
        Request a list of all news groups from the server.  gotAllGroups()
        is called on success, getGroupsFailed() on failure
        """
        self.sendLine('LIST')
        self._newState(self._stateList, self.getAllGroupsFailed)


    def fetchOverview(self):
        """fetchOverview(self)
        
        Request the overview format from the server.  gotOverview() is called
        on success, getOverviewFailed() on failure
        """
        self.sendLine('LIST OVERVIEW.FMT')
        self._newState(self._stateOverview, self.getOverviewFailed)


    def fetchSubscriptions(self):
        """fetchSubscriptions()
        
        Request a list of the groups it is recommended a new user subscribe to.
        gotSubscriptions() is called on success, getSubscriptionsFailed() on
        failure
        """
        self.sendLine('LIST SUBSCRIPTIONS')
        self._newState(self._stateSubscriptions, self.getSubscriptionsFailed)


    def fetchGroup(self, group):
        """fetchGroup(self, groupName)
        
        Get group information for the specified group from the server.  gotGroup()
        is called on success, getGroupFailed() on failure.
        """
        self.sendLine('GROUP %s' % (group,))
        self._newState(None, self.getGroupFailed, self._headerGroup)


    def fetchHead(self, index = ''):
        """fetchHead(self, index = '')
        
        Get the header for the specified article (or the currently selected
        article if index is '') from the server.  gotHead() is called on
        success, getHeadFailed() on failure
        """
        self.sendLine('HEAD %s' % (index,))
        self._newState(self._stateHead, self.getHeadFailed)

        
    def fetchBody(self, index = ''):
        """fetchBody(self, index = '')
        
        Get the body for the specified article (or the currently selected
        article if index is '') from the server.  gotBody() is called on
        success, getBodyFailed() on failure
        """
        self.sendLine('BODY %s' % (index,))
        self._newState(self._stateBody, self.getBodyFailed)


    def fetchArticle(self, index = ''):
        """fetchArticle(self, index = '')
        
        Get the complete article with the specified index (or the currently
        selected article if index is '') from the server.  gotArticle() is
        called on success, getArticleFailed() on failure
        """
        self.sendLine('ARTICLE %s' % (index,))
        self._newState(self._stateArticle, self.getArticleFailed)


    def postArticle(self, text):
        """postArticle(self, text)
        
        Attempt to post an article with the specified text to the server.  'text'
        must consist of both head and body data, as specified by RFC 850.  If the
        article is posted successfully, postedOk() is called, otherwise postFailed()
        is called.
        """
        self.sendLine('POST')
        self._newState(None, self.postFailed, self._headerPost)
        self._postText.append(text)


    def fetchXHeader(self, header, low = None, high = None, id = None):
        """fetchXHeader(self, header, low = None, high = None, id = None)
        
        Request a specific header from the server for an article or range
        of articles.  If 'id' is not None, a header for only the article
        with that Message-ID will be requested.  If both low and high are
        None, a header for the currently selected article will be selected;
        If both low and high are zero-length strings, headers for all articles
        in the currently selected group will be requested;  Otherwise, high
        and low will be used as bounds - if one is None the first or last
        article index will be substituted, as appropriate.
        """
        if id is not None:
            r = header + ' <%s>' % (id,)
        elif low is high is None:
            r = header
        elif high is None:
            r = header + ' %d-' % (low,)
        elif low is None:
            r = header + ' -%d' % (high,)
        else:
            r = header + ' %d-%d' % (low, high)
        self.sendLine('XHDR ' + r)
        self._newState(self._stateXHDR, self.getXHeaderFailed)


    def _newState(self, method, error, responseHandler = None):
        self._inputBuffers.append([])
        self._responseCodes.append(None)
        self._state.append(method)
        self._error.append(error)
        self._responseHandlers.append(responseHandler)


    def _endState(self):
        buf = self._inputBuffers[0]
        del self._responseCodes[0]
        del self._inputBuffers[0]
        del self._state[0]
        del self._error[0]
        del self._responseHandlers[0]
        return buf


    def _newLine(self, line, check = 1):
        if check and line and line[0] == '.':
            line = '.' + line
        self._inputBuffers[0].append(line)


    def _setResponseCode(self, code):
        self._responseCodes[0] = code
    
    
    def _getResponseCode(self):
        return self._responseCodes[0]


    def lineReceived(self, line):
        if not len(self._state):
            self._statePassive(line)
        elif self._getResponseCode() is None:
            code = extractCode(line)
            if code is None or not (200 <= code[0] < 400):    # An error!
                self._error[0](line)
                self._endState()
            else:
                self._setResponseCode(code)
                if self._responseHandlers[0]:
                    self._responseHandlers[0](code)
        else:
            self._state[0](line)


    def _statePassive(self, line):
        log.msg('Server said: %s' % line)


    def _passiveError(self, error):
        log.err('Passive Error: %s' % (error,))


    def _headerInitial(self, (code, message)):
        if code == 200:
            self.canPost = 1
        else:
            self.canPost = 0
        self._endState()


    def _stateList(self, line):
        if line != '.':
            data = filter(None, line.strip().split())
            self._newLine((data[0], int(data[1]), int(data[2]), data[3]), 0)
        else:
            self.gotAllGroups(self._endState())


    def _stateOverview(self, line):
        if line != '.':
            self._newLine(filter(None, line.strip().split()), 0)
        else:
            self.gotOverview(self._endState())


    def _stateSubscriptions(self, line):
        if line != '.':
            self._newLine(line.strip(), 0)
        else:
            self.gotSubscriptions(self._endState())


    def _headerGroup(self, (code, line)):
        self.gotGroup(tuple(line.split()))
        self._endState()


    def _stateArticle(self, line):
        if line != '.':
            self._newLine(line, 0)
        else:
            self.gotArticle('\n'.join(self._endState()))


    def _stateHead(self, line):
        if line != '.':
            self._newLine(line, 0)
        else:
            self.gotHead('\n'.join(self._endState()))


    def _stateBody(self, line):
        if line != '.':
            self._newLine(line, 0)
        else:
            self.gotBody('\n'.join(self._endState()))


    def _headerPost(self, (code, message)):
        if code == 340:
            self.transport.write(self._postText[0])
            if self._postText[-2:] != '\r\n':
                self.sendLine('\r\n')
            self.sendLine('.')
            del self._postText[0]
            self._newState(None, self.postFailed, self._headerPosted)
        else:
            self.postFailed(line)
        self._endState()


    def _headerPosted(self, (code, message)):
        if code == 240:
            self.postedOk()
        else:
            self.postFailed('%d %s' % (code, message))
        self._endState()


    def _stateXHDR(self, line):
        if line != '.':
            self._newLine(line.split(), 0)
        else:
            self._gotXHeader(self._endState())


class NNTPServer(NNTPClient):
    COMMANDS = [
        'LIST', 'GROUP', 'ARTICLE', 'STAT', 'MODE', 'LISTGROUP', 'XOVER',
        'XHDR', 'HEAD', 'BODY', 'NEXT', 'LAST', 'POST', 'QUIT', 'IHAVE',
        'HELP', 'SLAVE', 'XPATH', 'XINDEX', 'XROVER', 'TAKETHIS', 'CHECK'
    ]

    def __init__(self):
        NNTPClient.__init__(self)
        self.servingSlave = 0

    def connectionMade(self):
        try:
            self.ip = self.transport.socket.getpeername()
        #We're not always connected with a socket
        except AttributeError:
            self.ip = "unknown"
        self.inputHandler = None
        self.currentGroup = None
        self.currentIndex = None
        self.sendLine('200 server ready - posting allowed')

    def lineReceived(self, line):
        if self.inputHandler is not None:
            self.inputHandler(line)
        else:
            parts = filter(None, string.split(string.strip(line)))
            if len(parts):
                cmd, parts = string.upper(parts[0]), parts[1:]
                if cmd in NNTPServer.COMMANDS:
                    func = getattr(self, 'do_%s' % cmd)
                    try:
                        apply(func, parts)
                    except TypeError:
                        self.sendLine('501 command syntax error')
                    except:
                        self.sendLine('503 program fault - command not performed')
                        raise
                else:
                    self.sendLine('500 command not recognized')


    def do_LIST(self, subcmd = ''):
        subcmd = subcmd.strip().lower()
        if subcmd == 'newsgroups':
            # XXX - this could use a real implementation, eh?
            self.sendLine('215 Descriptions in form "group description"')
            self.sendLine('.')
        elif subcmd == 'overview.fmt':
            defer = self.factory.backend.overviewRequest()
            defer.addCallbacks(self._gotOverview, self._errOverview)
            log.msg('overview')
        elif subcmd == 'subscriptions':
            defer = self.factory.backend.subscriptionRequest()
            defer.addCallbacks(self._gotSubscription, self._errSubscription)
            log.msg('subscriptions')
        elif subcmd == '':
            defer = self.factory.backend.listRequest()
            defer.addCallbacks(self._gotList, self._errList)
        else:
            self.sendLine('500 command not recognized')


    def _gotList(self, list):
        self.sendLine('215 newsgroups in form "group high low flags"')
        for i in list:
            self.sendLine('%s %d %d %s' % i)
        self.sendLine('.')


    def _errList(self, failure):
        self.sendLine('503 program fault - command not performed')


    def _gotSubscription(self, parts):
        self.sendLine('215 information follows')
        for i in parts:
            self.sendLine(i)
        self.sendLine('.')


    def _errSubscription(self, failure):
        self.sendLine('503 program error, function not performed')


    def _gotOverview(self, parts):
        self.sendLine('215 Order of fields in overview database.')
        for i in parts:
            self.sendLine(i + ':')
        self.sendLine('.')


    def _errOverview(self, failure):
        self.sendLine('503 program error, function not performed')


    def do_LISTGROUP(self, group = None):
        group = group or self.currentGroup
        if group is None:
            self.sendLine('412 Not currently in newsgroup')
        else:
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


    def _errListGroup(self, failure):
        self.sendLine('502 no permission')


    def do_XOVER(self, range):
        if self.currentGroup is None:
            self.sendLine('412 No news group currently selected')
        else:
            l, h = parseRange(range)
            defer = self.factory.backend.xoverRequest(self.currentGroup, l, h)
            defer.addCallbacks(self._gotXOver, self._errXOver)


    def _gotXOver(self, parts):
        self.sendLine('224 Overview information follows')
        for i in parts:
            self.sendLine(string.join(i, '\t'))
        self.sendLine('.')


    def _errXOver(self, failure):
        self.sendLine('420 No article(s) selected')


    def xhdrWork(self, header, range):
        if self.currentGroup is None:
            self.sendLine('412 No news group currently selected')
        else:
            if range is None:
                if self.currentIndex is None:
                    self.sendLine('420 No current article selected')
                    return
                else:
                    l = h = self.currentIndex
            else:
                # FIXME: articles may be a message-id
                l, h = parseRange(range)
            
            if l is h is None:
                self.sendLine('430 no such article')
            else:
                return self.factory.backend.xhdrRequest(self.currentGroup, l, h, header)


    def do_XHDR(self, header, range = None):
        d = self.xhdrWork(header, range)
        if d:
            d.addCallbacks(self._gotXHDR, self._errXHDR)


    def _gotXHDR(self, parts):
        self.sendLine('221 Header follows')
        for i in parts:
            self.sendLine('%d %s' % i)
        self.sendLine('.')

    def _errXHDR(self, failure):
        self.sendLine('502 no permission')


    def do_XROVER(self, header, range = None):
        d = self.xhdrWork(header, range)
        if d:
            d.addCallbacks(self._gotXROVER, self._errXROVER)
    
    
    def _gotXROVER(self, parts):
        self.sendLine('224 Overview information follows')
        for i in parts:
            self.sendLine('%d %s' % i)
        self.sendLine('.')


    def _errXROVER(self, failure):
        self._errXHDR(failure)


    def do_POST(self):
        self.inputHandler = self._doingPost
        self.message = ''
        self.sendLine('340 send article to be posted.  End with <CR-LF>.<CR-LF>')


    def _doingPost(self, line):
        if line == '.':
            self.inputHandler = None
            group, article = self.currentGroup, self.message
            self.message = ''

            defer = self.factory.backend.postRequest(article)
            defer.addCallbacks(self._gotPost, self._errPost)
        else:
            if line and line[0] == '.':
                line = '.' + line
            self.message = self.message + line + '\r\n'


    def _gotPost(self, parts):
        self.sendLine('240 article posted ok')
        
    
    def _errPost(self, failure):
        self.sendLine('441 posting failed')


    def do_CHECK(self, id):
        d = self.factory.backend.articleExistsRequest(id)
        d.addCallbacks(self._gotCheck, self._errCheck)
    
    
    def _gotCheck(self, result):
        if result:
            self.sendLine("438 already have it, please don't send it to me")
        else:
            self.sendLine('238 no such article found, please send it to me')
    
    
    def _errCheck(self, failure):
        self.sendLine('431 try sending it again later')


    def do_TAKETHIS(self, id):
        self.inputHandler = self._doingTakeThis
        self.message = ''
    
    
    def _doingTakeThis(self, line):
        if line == '.':
            self.inputHandler = None
            article = self.message
            self.message = ''
            d = self.factory.backend.postRequest(article)
            d.addCallbacks(self._didTakeThis, self._errTakeThis)
        else:
            if line and line[0] == '.':
                line = '.' + line
            self.message = self.message + line + '\r\n'


    def _didTakeThis(self, result):
        self.sendLine('239 article transferred ok')
    
    
    def _errTakeThis(self, result):
        self.sendLine('439 article transfer failed')


    def do_GROUP(self, group):
        defer = self.factory.backend.groupRequest(group)
        defer.addCallbacks(self._gotGroup, self._errGroup)

    
    def _gotGroup(self, parts):
        name, num, high, low, flags = parts
        self.currentGroup = name
        self.currentIndex = low
        self.sendLine('211 %d %d %d %s group selected' % (num, low, high, name))
    
    
    def _errGroup(self, failure):
        self.sendLine('411 no such group')


    def articleWork(self, article, cmd):
        if self.currentGroup is None:
            self.sendLine('412 no newsgroup has been selected')
        else:
            if article is None:
                article = self.currentIndex
            else:
                if article[0] == '<':
                    # XXX - FIXME: Request for article by message-id not implemented
                    self.sendLine('501 %s <message-id> not implemented :(' % (cmd,))
                    return
                else:
                    try:
                        article = int(article)
                    except ValueError, e:
                        self.sendLine('503 command syntax error')
                        return

            return self.factory.backend.articleRequest(self.currentGroup, article)

    def do_ARTICLE(self, article = None):
        defer = self.articleWork(article, 'ARTICLE')
        if defer:
            defer.addCallbacks(self._gotArticle, self._errArticle)


    def _gotArticle(self, (index, id, article)):
        self.currentIndex = index
        self.sendLine('220 %d %s article' % (index, id))
        self.transport.write(article.replace('\r\n..', '\r\n.') + '\r\n')
        self.sendLine('.')

    def _errArticle(self, article):
        self.sendLine('423 bad article number')


    def do_STAT(self, article = None):
        defer = self.articleWork(article, 'STAT')
        if defer:
            defer.addCallbacks(self._gotStat, self._errStat)
    
    
    def _gotStat(self, (index, id, article)):
        self.currentIndex = index
        self.sendLine('223 %d %s article retreived - request text separately' % (index, id))


    def _errStat(self, failure):
        self.sendLine('423 bad article number')


    def do_HEAD(self, article = None):
        defer = self.articleWork(article, 'HEAD')
        if defer:
            defer.addCallbacks(self._gotHead, self._errHead)
    
    
    def _gotHead(self, (index, id, head)):
        self.currentIndex = index
        self.sendLine('221 %d %s article retrieved' % (index, id))
        self.transport.write(head + '\r\n')
        self.sendLine('.')
    
    
    def _errHead(self, failure):
        self.sendLine('423 no such article number in this group')


    def do_BODY(self, article):
        defer = self.articleWork(article, 'BODY')
        if defer:
            defer.addCallbacks(self._gotBody, self._errBody)


    def _gotBody(self, (index, id, body)):
        self.currentIndex = index
        self.sendLine('221 %d %s article retrieved' % (index, id))
        self.transport.write(body.replace('\r\n..', '\r\n.') + '\r\n')
        self.sendLine('.')


    def _errBody(self, failure):
        self.sendLine('423 no such article number in this group')


    # NEXT and LAST are just STATs that increment currentIndex first.
    # Accordingly, use the STAT callbacks.
    def do_NEXT(self):
        i = self.currentIndex + 1
        defer = self.factory.backend.articleRequest(self.currentGroup, i)
        defer.addCallbacks(self._gotStat, self._errStat)


    def do_LAST(self):
        i = self.currentIndex - 1
        defer = self.factory.backend.articleRequest(self.currentGroup, i)
        defer.addCallbacks(self._gotStat, self._errStat)


    def do_MODE(self, cmd):
        cmd = cmd[0].strip().upper()
        if cmd == 'READER':
            self.servingSlave = 0
            self.sendLine('200 Hello, you can post')
        elif cmd == 'STREAM':
            self.sendLine('500 Command not understood')
        else:
            # This is not a mistake
            self.sendLine('500 Command not understood')


    def do_QUIT(self):
        self.sendLine('205 goodbye')
        self.transport.loseConnection()

    
    def do_HELP(self):
        self.sendLine('100 help text follows')
        self.sendLine('Read the RFC.')
        self.sendLine('.')
    
    
    def do_SLAVE(self):
        self.sendLine('202 slave status noted')
        self.servingeSlave = 1


    def do_XPATH(self, article):
        # XPATH is a silly thing to have.  No client has the right to ask
        # for this piece of information from me, and so that is what I'll
        # tell them.
        self.sendLine('502 access restriction or permission denied')


    def do_XINDEX(self, article):
        # XINDEX is another silly command.  The RFC suggests it be relegated
        # to the history books, and who am I to disagree?
        self.sendLine('502 access restriction or permission denied')


    def do_XROVER(self, range = None):
        self.do_XHDR(self, 'References', range)


    def do_IHAVE(self, id):
        self.factory.backend.articleExistsRequest(id).addCallback(self._foundArticle)

    
    def _foundArticle(self, result):
        if result:
            self.sendLine('437 article rejected - do not try again')
        else:
            self.sendLine('335 send article to be transferred.  End with <CR-LF>.<CR-LF>')
            self.inputHandler = self._handleIHAVE
            self.message = ''
    
    
    def _handleIHAVE(self, line):
        if line == '.':
            self.inputHandler = None
            self.factory.backend.postRequest(
                self.message
            ).addCallbacks(self._gotIHAVE, self._errIHAVE)
            
            self.message = ''
        else:
            if line.startswith('.'):
                line = '.' + line
            self.message = self.message + line + '\r\n'


    def _gotIHAVE(self, result):
        self.sendLine('235 article transferred ok')
    
    
    def _errIHAVE(self, failure):
        self.sendLine('436 transfer failed - try again later')
