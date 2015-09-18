# -*- test-case-name: twisted.news.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
News server backend implementations.
"""

import getpass, pickle, time, socket
import os
import StringIO
from hashlib import md5
from email.Message import Message
from email.Generator import Generator
from zope.interface import implements, Interface

from twisted.news.nntp import NNTPError
from twisted.mail import smtp
from twisted.internet import defer
from twisted.enterprise import adbapi
from twisted.persisted import dirdbm



ERR_NOGROUP, ERR_NOARTICLE = range(2, 4)  # XXX - put NNTP values here (I guess?)

OVERVIEW_FMT = [
    'Subject', 'From', 'Date', 'Message-ID', 'References',
    'Bytes', 'Lines', 'Xref'
]

def hexdigest(md5): #XXX: argh. 1.5.2 doesn't have this.
    return ''.join(map(lambda x: hex(ord(x))[2:], md5.digest()))

class Article:
    def __init__(self, head, body):
        self.body = body
        self.headers = {}
        header = None
        for line in head.split('\r\n'):
            if line[0] in ' \t':
                i = list(self.headers[header])
                i[1] += '\r\n' + line
            else:
                i = line.split(': ', 1)
                header = i[0].lower()
            self.headers[header] = tuple(i)

        if not self.getHeader('Message-ID'):
            s = str(time.time()) + self.body
            id = hexdigest(md5(s)) + '@' + socket.gethostname()
            self.putHeader('Message-ID', '<%s>' % id)

        if not self.getHeader('Bytes'):
            self.putHeader('Bytes', str(len(self.body)))

        if not self.getHeader('Lines'):
            self.putHeader('Lines', str(self.body.count('\n')))

        if not self.getHeader('Date'):
            self.putHeader('Date', time.ctime(time.time()))


    def getHeader(self, header):
        h = header.lower()
        if h in self.headers:
            return self.headers[h][1]
        else:
            return ''


    def putHeader(self, header, value):
        self.headers[header.lower()] = (header, value)


    def textHeaders(self):
        headers = []
        for i in self.headers.values():
            headers.append('%s: %s' % i)
        return '\r\n'.join(headers) + '\r\n'

    def overview(self):
        xover = []
        for i in OVERVIEW_FMT:
            xover.append(self.getHeader(i))
        return xover


class NewsServerError(Exception):
    pass


class INewsStorage(Interface):
    """
    An interface for storing and requesting news articles
    """

    def listRequest():
        """
        Returns a deferred whose callback will be passed a list of 4-tuples
        containing (name, max index, min index, flags) for each news group
        """


    def subscriptionRequest():
        """
        Returns a deferred whose callback will be passed the list of
        recommended subscription groups for new server users
        """


    def postRequest(message):
        """
        Returns a deferred whose callback will be invoked if 'message'
        is successfully posted to one or more specified groups and
        whose errback will be invoked otherwise.
        """


    def overviewRequest():
        """
        Returns a deferred whose callback will be passed the a list of
        headers describing this server's overview format.
        """


    def xoverRequest(group, low, high):
        """
        Returns a deferred whose callback will be passed a list of xover
        headers for the given group over the given range.  If low is None,
        the range starts at the first article.  If high is None, the range
        ends at the last article.
        """


    def xhdrRequest(group, low, high, header):
        """
        Returns a deferred whose callback will be passed a list of XHDR data
        for the given group over the given range.  If low is None,
        the range starts at the first article.  If high is None, the range
        ends at the last article.
        """


    def listGroupRequest(group):
        """
        Returns a deferred whose callback will be passed a two-tuple of
        (group name, [article indices])
        """


    def groupRequest(group):
        """
        Returns a deferred whose callback will be passed a five-tuple of
        (group name, article count, highest index, lowest index, group flags)
        """


    def articleExistsRequest(id):
        """
        Returns a deferred whose callback will be passed with a true value
        if a message with the specified Message-ID exists in the database
        and with a false value otherwise.
        """


    def articleRequest(group, index, id = None):
        """
        Returns a deferred whose callback will be passed a file-like object
        containing the full article text (headers and body) for the article
        of the specified index in the specified group, and whose errback
        will be invoked if the article or group does not exist.  If id is
        not None, index is ignored and the article with the given Message-ID
        will be returned instead, along with its index in the specified
        group.
        """


    def headRequest(group, index):
        """
        Returns a deferred whose callback will be passed the header for
        the article of the specified index in the specified group, and
        whose errback will be invoked if the article or group does not
        exist.
        """


    def bodyRequest(group, index):
        """
        Returns a deferred whose callback will be passed the body for
        the article of the specified index in the specified group, and
        whose errback will be invoked if the article or group does not
        exist.
        """

class NewsStorage:
    """
    Backwards compatibility class -- There is no reason to inherit from this,
    just implement INewsStorage instead.
    """
    def listRequest(self):
        raise NotImplementedError()
    def subscriptionRequest(self):
        raise NotImplementedError()
    def postRequest(self, message):
        raise NotImplementedError()
    def overviewRequest(self):
        return defer.succeed(OVERVIEW_FMT)
    def xoverRequest(self, group, low, high):
        raise NotImplementedError()
    def xhdrRequest(self, group, low, high, header):
        raise NotImplementedError()
    def listGroupRequest(self, group):
        raise NotImplementedError()
    def groupRequest(self, group):
        raise NotImplementedError()
    def articleExistsRequest(self, id):
        raise NotImplementedError()
    def articleRequest(self, group, index, id = None):
        raise NotImplementedError()
    def headRequest(self, group, index):
        raise NotImplementedError()
    def bodyRequest(self, group, index):
        raise NotImplementedError()



class _ModerationMixin:
    """
    Storage implementations can inherit from this class to get the easy-to-use
    C{notifyModerators} method which will take care of sending messages which
    require moderation to a list of moderators.
    """
    sendmail = staticmethod(smtp.sendmail)

    def notifyModerators(self, moderators, article):
        """
        Send an article to a list of group moderators to be moderated.

        @param moderators: A C{list} of C{str} giving RFC 2821 addresses of
            group moderators to notify.

        @param article: The article requiring moderation.
        @type article: L{Article}

        @return: A L{Deferred} which fires with the result of sending the email.
        """
        # Moderated postings go through as long as they have an Approved
        # header, regardless of what the value is
        group = article.getHeader('Newsgroups')
        subject = article.getHeader('Subject')

        if self._sender is None:
            # This case should really go away.  This isn't a good default.
            sender = 'twisted-news@' + socket.gethostname()
        else:
            sender = self._sender

        msg = Message()
        msg['Message-ID'] = smtp.messageid()
        msg['From'] = sender
        msg['To'] = ', '.join(moderators)
        msg['Subject'] = 'Moderate new %s message: %s' % (group, subject)
        msg['Content-Type'] = 'message/rfc822'

        payload = Message()
        for header, value in article.headers.values():
            payload.add_header(header, value)
        payload.set_payload(article.body)

        msg.attach(payload)

        out = StringIO.StringIO()
        gen = Generator(out, False)
        gen.flatten(msg)
        msg = out.getvalue()

        return self.sendmail(self._mailhost, sender, moderators, msg)



class PickleStorage(_ModerationMixin):
    """
    A trivial NewsStorage implementation using pickles

    Contains numerous flaws and is generally unsuitable for any
    real applications.  Consider yourself warned!
    """

    implements(INewsStorage)

    sharedDBs = {}

    def __init__(self, filename, groups=None, moderators=(),
                 mailhost=None, sender=None):
        """
        @param mailhost: A C{str} giving the mail exchange host which will
            accept moderation emails from this server.  Must accept emails
            destined for any address specified as a moderator.

        @param sender: A C{str} giving the address which will be used as the
            sender of any moderation email generated by this server.
        """
        self.datafile = filename
        self.load(filename, groups, moderators)
        self._mailhost = mailhost
        self._sender = sender


    def getModerators(self, groups):
        # first see if any groups are moderated.  if so, nothing gets posted,
        # but the whole messages gets forwarded to the moderator address
        moderators = []
        for group in groups:
            moderators.extend(self.db['moderators'].get(group, None))
        return filter(None, moderators)


    def listRequest(self):
        "Returns a list of 4-tuples: (name, max index, min index, flags)"
        l = self.db['groups']
        r = []
        for i in l:
            if len(self.db[i].keys()):
                low = min(self.db[i].keys())
                high = max(self.db[i].keys()) + 1
            else:
                low = high = 0
            if self.db['moderators'].has_key(i):
                flags = 'm'
            else:
                flags = 'y'
            r.append((i, high, low, flags))
        return defer.succeed(r)

    def subscriptionRequest(self):
        return defer.succeed(['alt.test'])

    def postRequest(self, message):
        cleave = message.find('\r\n\r\n')
        headers, article = message[:cleave], message[cleave + 4:]

        a = Article(headers, article)
        groups = a.getHeader('Newsgroups').split()
        xref = []

        # Check moderated status
        moderators = self.getModerators(groups)
        if moderators and not a.getHeader('Approved'):
            return self.notifyModerators(moderators, a)

        for group in groups:
            if group in self.db:
                if len(self.db[group].keys()):
                    index = max(self.db[group].keys()) + 1
                else:
                    index = 1
                xref.append((group, str(index)))
                self.db[group][index] = a

        if len(xref) == 0:
            return defer.fail(None)

        a.putHeader('Xref', '%s %s' % (
            socket.gethostname().split()[0],
            ''.join(map(lambda x: ':'.join(x), xref))
        ))

        self.flush()
        return defer.succeed(None)


    def overviewRequest(self):
        return defer.succeed(OVERVIEW_FMT)


    def xoverRequest(self, group, low, high):
        if not self.db.has_key(group):
            return defer.succeed([])
        r = []
        for i in self.db[group].keys():
            if (low is None or i >= low) and (high is None or i <= high):
                r.append([str(i)] + self.db[group][i].overview())
        return defer.succeed(r)


    def xhdrRequest(self, group, low, high, header):
        if not self.db.has_key(group):
            return defer.succeed([])
        r = []
        for i in self.db[group].keys():
            if low is None or i >= low and high is None or i <= high:
                r.append((i, self.db[group][i].getHeader(header)))
        return defer.succeed(r)


    def listGroupRequest(self, group):
        if self.db.has_key(group):
            return defer.succeed((group, self.db[group].keys()))
        else:
            return defer.fail(None)

    def groupRequest(self, group):
        if self.db.has_key(group):
            if len(self.db[group].keys()):
                num = len(self.db[group].keys())
                low = min(self.db[group].keys())
                high = max(self.db[group].keys())
            else:
                num = low = high = 0
            flags = 'y'
            return defer.succeed((group, num, high, low, flags))
        else:
            return defer.fail(ERR_NOGROUP)


    def articleExistsRequest(self, id):
        for group in self.db['groups']:
            for a in self.db[group].values():
                if a.getHeader('Message-ID') == id:
                    return defer.succeed(1)
        return defer.succeed(0)


    def articleRequest(self, group, index, id = None):
        if id is not None:
            raise NotImplementedError

        if self.db.has_key(group):
            if self.db[group].has_key(index):
                a = self.db[group][index]
                return defer.succeed((
                    index,
                    a.getHeader('Message-ID'),
                    StringIO.StringIO(a.textHeaders() + '\r\n' + a.body)
                ))
            else:
                return defer.fail(ERR_NOARTICLE)
        else:
            return defer.fail(ERR_NOGROUP)


    def headRequest(self, group, index):
        if self.db.has_key(group):
            if self.db[group].has_key(index):
                a = self.db[group][index]
                return defer.succeed((index, a.getHeader('Message-ID'), a.textHeaders()))
            else:
                return defer.fail(ERR_NOARTICLE)
        else:
            return defer.fail(ERR_NOGROUP)


    def bodyRequest(self, group, index):
        if self.db.has_key(group):
            if self.db[group].has_key(index):
                a = self.db[group][index]
                return defer.succeed((index, a.getHeader('Message-ID'), StringIO.StringIO(a.body)))
            else:
                return defer.fail(ERR_NOARTICLE)
        else:
            return defer.fail(ERR_NOGROUP)


    def flush(self):
        f = open(self.datafile, 'w')
        pickle.dump(self.db, f)
        f.close()


    def load(self, filename, groups = None, moderators = ()):
        if filename in PickleStorage.sharedDBs:
            self.db = PickleStorage.sharedDBs[filename]
        else:
            try:
                self.db = pickle.load(open(filename))
                PickleStorage.sharedDBs[filename] = self.db
            except IOError:
                self.db = PickleStorage.sharedDBs[filename] = {}
                self.db['groups'] = groups
                if groups is not None:
                    for i in groups:
                        self.db[i] = {}
                self.db['moderators'] = dict(moderators)
                self.flush()


class Group:
    name = None
    flags = ''
    minArticle = 1
    maxArticle = 0
    articles = None

    def __init__(self, name, flags = 'y'):
        self.name = name
        self.flags = flags
        self.articles = {}


class NewsShelf(_ModerationMixin):
    """
    A NewStorage implementation using Twisted's dirdbm persistence module.
    """

    implements(INewsStorage)

    def __init__(self, mailhost, path, sender=None):
        """
        @param mailhost: A C{str} giving the mail exchange host which will
            accept moderation emails from this server.  Must accept emails
            destined for any address specified as a moderator.

        @param sender: A C{str} giving the address which will be used as the
            sender of any moderation email generated by this server.
        """
        self.path = path
        self._mailhost = self.mailhost = mailhost
        self._sender = sender

        if not os.path.exists(path):
            os.mkdir(path)

        self.dbm = dirdbm.Shelf(os.path.join(path, "newsshelf"))
        if not len(self.dbm.keys()):
            self.initialize()


    def initialize(self):
        # A dictionary of group name/Group instance items
        self.dbm['groups'] = dirdbm.Shelf(os.path.join(self.path, 'groups'))

        # A dictionary of group name/email address
        self.dbm['moderators'] = dirdbm.Shelf(os.path.join(self.path, 'moderators'))

        # A list of group names
        self.dbm['subscriptions'] = []

        # A dictionary of MessageID strings/xref lists
        self.dbm['Message-IDs'] = dirdbm.Shelf(os.path.join(self.path, 'Message-IDs'))


    def addGroup(self, name, flags):
        self.dbm['groups'][name] = Group(name, flags)


    def addSubscription(self, name):
        self.dbm['subscriptions'] = self.dbm['subscriptions'] + [name]


    def addModerator(self, group, email):
        self.dbm['moderators'][group] = email


    def listRequest(self):
        result = []
        for g in self.dbm['groups'].values():
            result.append((g.name, g.maxArticle, g.minArticle, g.flags))
        return defer.succeed(result)


    def subscriptionRequest(self):
        return defer.succeed(self.dbm['subscriptions'])


    def getModerator(self, groups):
        # first see if any groups are moderated.  if so, nothing gets posted,
        # but the whole messages gets forwarded to the moderator address
        for group in groups:
            try:
                return self.dbm['moderators'][group]
            except KeyError:
                pass
        return None


    def notifyModerator(self, moderator, article):
        """
        Notify a single moderator about an article requiring moderation.

        C{notifyModerators} should be preferred.
        """
        return self.notifyModerators([moderator], article)


    def postRequest(self, message):
        cleave = message.find('\r\n\r\n')
        headers, article = message[:cleave], message[cleave + 4:]

        article = Article(headers, article)
        groups = article.getHeader('Newsgroups').split()
        xref = []

        # Check for moderated status
        moderator = self.getModerator(groups)
        if moderator and not article.getHeader('Approved'):
            return self.notifyModerators([moderator], article)


        for group in groups:
            try:
                g = self.dbm['groups'][group]
            except KeyError:
                pass
            else:
                index = g.maxArticle + 1
                g.maxArticle += 1
                g.articles[index] = article
                xref.append((group, str(index)))
                self.dbm['groups'][group] = g

        if not xref:
            return defer.fail(NewsServerError("No groups carried: " + ' '.join(groups)))

        article.putHeader('Xref', '%s %s' % (socket.gethostname().split()[0], ' '.join(map(lambda x: ':'.join(x), xref))))
        self.dbm['Message-IDs'][article.getHeader('Message-ID')] = xref
        return defer.succeed(None)


    def overviewRequest(self):
        return defer.succeed(OVERVIEW_FMT)


    def xoverRequest(self, group, low, high):
        if not self.dbm['groups'].has_key(group):
            return defer.succeed([])

        if low is None:
            low = 0
        if high is None:
            high = self.dbm['groups'][group].maxArticle
        r = []
        for i in range(low, high + 1):
            if self.dbm['groups'][group].articles.has_key(i):
                r.append([str(i)] + self.dbm['groups'][group].articles[i].overview())
        return defer.succeed(r)


    def xhdrRequest(self, group, low, high, header):
        if group not in self.dbm['groups']:
            return defer.succeed([])

        if low is None:
            low = 0
        if high is None:
            high = self.dbm['groups'][group].maxArticle
        r = []
        for i in range(low, high + 1):
            if i in self.dbm['groups'][group].articles:
                r.append((i, self.dbm['groups'][group].articles[i].getHeader(header)))
        return defer.succeed(r)


    def listGroupRequest(self, group):
        if self.dbm['groups'].has_key(group):
            return defer.succeed((group, self.dbm['groups'][group].articles.keys()))
        return defer.fail(NewsServerError("No such group: " + group))


    def groupRequest(self, group):
        try:
            g = self.dbm['groups'][group]
        except KeyError:
            return defer.fail(NewsServerError("No such group: " + group))
        else:
            flags = g.flags
            low = g.minArticle
            high = g.maxArticle
            num = high - low + 1
            return defer.succeed((group, num, high, low, flags))


    def articleExistsRequest(self, id):
        return defer.succeed(id in self.dbm['Message-IDs'])


    def articleRequest(self, group, index, id = None):
        if id is not None:
            try:
                xref = self.dbm['Message-IDs'][id]
            except KeyError:
                return defer.fail(NewsServerError("No such article: " + id))
            else:
                group, index = xref[0]
                index = int(index)

        try:
            a = self.dbm['groups'][group].articles[index]
        except KeyError:
            return defer.fail(NewsServerError("No such group: " + group))
        else:
            return defer.succeed((
                index,
                a.getHeader('Message-ID'),
                StringIO.StringIO(a.textHeaders() + '\r\n' + a.body)
            ))


    def headRequest(self, group, index, id = None):
        if id is not None:
            try:
                xref = self.dbm['Message-IDs'][id]
            except KeyError:
                return defer.fail(NewsServerError("No such article: " + id))
            else:
                group, index = xref[0]
                index = int(index)

        try:
            a = self.dbm['groups'][group].articles[index]
        except KeyError:
            return defer.fail(NewsServerError("No such group: " + group))
        else:
            return defer.succeed((index, a.getHeader('Message-ID'), a.textHeaders()))


    def bodyRequest(self, group, index, id = None):
        if id is not None:
            try:
                xref = self.dbm['Message-IDs'][id]
            except KeyError:
                return defer.fail(NewsServerError("No such article: " + id))
            else:
                group, index = xref[0]
                index = int(index)

        try:
            a = self.dbm['groups'][group].articles[index]
        except KeyError:
            return defer.fail(NewsServerError("No such group: " + group))
        else:
            return defer.succeed((index, a.getHeader('Message-ID'), StringIO.StringIO(a.body)))


class NewsStorageAugmentation:
    """
    A NewsStorage implementation using Twisted's asynchronous DB-API
    """

    implements(INewsStorage)

    schema = """

    CREATE TABLE groups (
        group_id      SERIAL,
        name          VARCHAR(80) NOT NULL,

        flags         INTEGER DEFAULT 0 NOT NULL
    );

    CREATE UNIQUE INDEX group_id_index ON groups (group_id);
    CREATE UNIQUE INDEX name_id_index ON groups (name);

    CREATE TABLE articles (
        article_id    SERIAL,
        message_id    TEXT,

        header        TEXT,
        body          TEXT
    );

    CREATE UNIQUE INDEX article_id_index ON articles (article_id);
    CREATE UNIQUE INDEX article_message_index ON articles (message_id);

    CREATE TABLE postings (
        group_id      INTEGER,
        article_id    INTEGER,
        article_index INTEGER NOT NULL
    );

    CREATE UNIQUE INDEX posting_article_index ON postings (article_id);

    CREATE TABLE subscriptions (
        group_id    INTEGER
    );

    CREATE TABLE overview (
        header      TEXT
    );
    """

    def __init__(self, info):
        self.info = info
        self.dbpool = adbapi.ConnectionPool(**self.info)


    def __setstate__(self, state):
        self.__dict__ = state
        self.info['password'] = getpass.getpass('Database password for %s: ' % (self.info['user'],))
        self.dbpool = adbapi.ConnectionPool(**self.info)
        del self.info['password']


    def listRequest(self):
        # COALESCE may not be totally portable
        # it is shorthand for
        # CASE WHEN (first parameter) IS NOT NULL then (first parameter) ELSE (second parameter) END
        sql = """
            SELECT groups.name,
                COALESCE(MAX(postings.article_index), 0),
                COALESCE(MIN(postings.article_index), 0),
                groups.flags
            FROM groups LEFT OUTER JOIN postings
            ON postings.group_id = groups.group_id
            GROUP BY groups.name, groups.flags
            ORDER BY groups.name
        """
        return self.dbpool.runQuery(sql)


    def subscriptionRequest(self):
        sql = """
            SELECT groups.name FROM groups,subscriptions WHERE groups.group_id = subscriptions.group_id
        """
        return self.dbpool.runQuery(sql)


    def postRequest(self, message):
        cleave = message.find('\r\n\r\n')
        headers, article = message[:cleave], message[cleave + 4:]
        article = Article(headers, article)
        return self.dbpool.runInteraction(self._doPost, article)


    def _doPost(self, transaction, article):
        # Get the group ids
        groups = article.getHeader('Newsgroups').split()
        if not len(groups):
            raise NNTPError('Missing Newsgroups header')

        sql = """
            SELECT name, group_id FROM groups
            WHERE name IN (%s)
        """ % (', '.join([("'%s'" % (adbapi.safe(group),)) for group in groups]),)

        transaction.execute(sql)
        result = transaction.fetchall()

        # No relevant groups, bye bye!
        if not len(result):
            raise NNTPError('None of groups in Newsgroup header carried')

        # Got some groups, now find the indices this article will have in each
        sql = """
            SELECT groups.group_id, COALESCE(MAX(postings.article_index), 0) + 1
            FROM groups LEFT OUTER JOIN postings
            ON postings.group_id = groups.group_id
            WHERE groups.group_id IN (%s)
            GROUP BY groups.group_id
        """ % (', '.join([("%d" % (id,)) for (group, id) in result]),)

        transaction.execute(sql)
        indices = transaction.fetchall()

        if not len(indices):
            raise NNTPError('Internal server error - no indices found')

        # Associate indices with group names
        gidToName = dict([(b, a) for (a, b) in result])
        gidToIndex = dict(indices)

        nameIndex = []
        for i in gidToName:
            nameIndex.append((gidToName[i], gidToIndex[i]))

        # Build xrefs
        xrefs = socket.gethostname().split()[0]
        xrefs = xrefs + ' ' + ' '.join([('%s:%d' % (group, id)) for (group, id) in nameIndex])
        article.putHeader('Xref', xrefs)

        # Hey!  The article is ready to be posted!  God damn f'in finally.
        sql = """
            INSERT INTO articles (message_id, header, body)
            VALUES ('%s', '%s', '%s')
        """ % (
            adbapi.safe(article.getHeader('Message-ID')),
            adbapi.safe(article.textHeaders()),
            adbapi.safe(article.body)
        )

        transaction.execute(sql)

        # Now update the posting to reflect the groups to which this belongs
        for gid in gidToName:
            sql = """
                INSERT INTO postings (group_id, article_id, article_index)
                VALUES (%d, (SELECT last_value FROM articles_article_id_seq), %d)
            """ % (gid, gidToIndex[gid])
            transaction.execute(sql)

        return len(nameIndex)


    def overviewRequest(self):
        sql = """
            SELECT header FROM overview
        """
        return self.dbpool.runQuery(sql).addCallback(lambda result: [header[0] for header in result])


    def xoverRequest(self, group, low, high):
        sql = """
            SELECT postings.article_index, articles.header
            FROM articles,postings,groups
            WHERE postings.group_id = groups.group_id
            AND groups.name = '%s'
            AND postings.article_id = articles.article_id
            %s
            %s
        """ % (
            adbapi.safe(group),
            low is not None and "AND postings.article_index >= %d" % (low,) or "",
            high is not None and "AND postings.article_index <= %d" % (high,) or ""
        )

        return self.dbpool.runQuery(sql).addCallback(
            lambda results: [
                [id] + Article(header, None).overview() for (id, header) in results
            ]
        )


    def xhdrRequest(self, group, low, high, header):
        sql = """
            SELECT articles.header
            FROM groups,postings,articles
            WHERE groups.name = '%s' AND postings.group_id = groups.group_id
            AND postings.article_index >= %d
            AND postings.article_index <= %d
        """ % (adbapi.safe(group), low, high)

        return self.dbpool.runQuery(sql).addCallback(
            lambda results: [
                (i, Article(h, None).getHeader(h)) for (i, h) in results
            ]
        )


    def listGroupRequest(self, group):
        sql = """
            SELECT postings.article_index FROM postings,groups
            WHERE postings.group_id = groups.group_id
            AND groups.name = '%s'
        """ % (adbapi.safe(group),)

        return self.dbpool.runQuery(sql).addCallback(
            lambda results, group = group: (group, [res[0] for res in results])
        )


    def groupRequest(self, group):
        sql = """
            SELECT groups.name,
                COUNT(postings.article_index),
                COALESCE(MAX(postings.article_index), 0),
                COALESCE(MIN(postings.article_index), 0),
                groups.flags
            FROM groups LEFT OUTER JOIN postings
            ON postings.group_id = groups.group_id
            WHERE groups.name = '%s'
            GROUP BY groups.name, groups.flags
        """ % (adbapi.safe(group),)

        return self.dbpool.runQuery(sql).addCallback(
            lambda results: tuple(results[0])
        )


    def articleExistsRequest(self, id):
        sql = """
            SELECT COUNT(message_id) FROM articles
            WHERE message_id = '%s'
        """ % (adbapi.safe(id),)

        return self.dbpool.runQuery(sql).addCallback(
            lambda result: bool(result[0][0])
        )


    def articleRequest(self, group, index, id = None):
        if id is not None:
            sql = """
                SELECT postings.article_index, articles.message_id, articles.header, articles.body
                FROM groups,postings LEFT OUTER JOIN articles
                ON articles.message_id = '%s'
                WHERE groups.name = '%s'
                AND groups.group_id = postings.group_id
            """ % (adbapi.safe(id), adbapi.safe(group))
        else:
            sql = """
                SELECT postings.article_index, articles.message_id, articles.header, articles.body
                FROM groups,articles LEFT OUTER JOIN postings
                ON postings.article_id = articles.article_id
                WHERE postings.article_index = %d
                AND postings.group_id = groups.group_id
                AND groups.name = '%s'
            """ % (index, adbapi.safe(group))

        return self.dbpool.runQuery(sql).addCallback(
            lambda result: (
                result[0][0],
                result[0][1],
                StringIO.StringIO(result[0][2] + '\r\n' + result[0][3])
            )
        )


    def headRequest(self, group, index):
        sql = """
            SELECT postings.article_index, articles.message_id, articles.header
            FROM groups,articles LEFT OUTER JOIN postings
            ON postings.article_id = articles.article_id
            WHERE postings.article_index = %d
            AND postings.group_id = groups.group_id
            AND groups.name = '%s'
        """ % (index, adbapi.safe(group))

        return self.dbpool.runQuery(sql).addCallback(lambda result: result[0])


    def bodyRequest(self, group, index):
        sql = """
            SELECT postings.article_index, articles.message_id, articles.body
            FROM groups,articles LEFT OUTER JOIN postings
            ON postings.article_id = articles.article_id
            WHERE postings.article_index = %d
            AND postings.group_id = groups.group_id
            AND groups.name = '%s'
        """ % (index, adbapi.safe(group))

        return self.dbpool.runQuery(sql).addCallback(
            lambda result: result[0]
        ).addCallback(
            lambda (index, id, body): (index, id, StringIO.StringIO(body))
        )

####
#### XXX - make these static methods some day
####
def makeGroupSQL(groups):
    res = ''
    for g in groups:
        res = res + """\n    INSERT INTO groups (name) VALUES ('%s');\n""" % (adbapi.safe(g),)
    return res


def makeOverviewSQL():
    res = ''
    for o in OVERVIEW_FMT:
        res = res + """\n    INSERT INTO overview (header) VALUES ('%s');\n""" % (adbapi.safe(o),)
    return res
