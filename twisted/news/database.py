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
from twisted.internet import defer
from twisted.enterprise import adbapi
from twisted.persisted import dirdbm

import pickle, time, socket, md5, string

ERR_NOGROUP, ERR_NOARTICLE = range(2, 4)  # XXX - put NNTP values here (I guess?)

OVERVIEW_FMT = [
    'Subject', 'From', 'Date', 'Message-ID', 'References',
    'Bytes', 'Lines', 'Xref'
]

def hexdigest(md5): #XXX: argh. 1.5.2 doesn't have this.
    return string.join(map(lambda x: hex(ord(x))[2:], md5.digest()), '')

class Article:
    def __init__(self, head, body):
        self.body = body
        head = map(lambda x: string.split(x, ': ', 1), string.split(head, '\r\n'))
        self.headers = {}
        for i in head:
            if len(i) == 0:
                continue
            elif len(i) == 1:
                self.headers[string.lower(i[0])] = (i, '')
            else:
                self.headers[string.lower(i[0])] = tuple(i)

        if not self.getHeader('Message-ID'):
            s = str(time.time()) + self.body
            id = hexdigest(md5.md5(s)) + '@' + socket.gethostname()
            self.putHeader('Message-ID', '<%s>' % id)

        if not self.getHeader('Bytes'):
            self.putHeader('Bytes', str(len(self.body)))
        
        if not self.getHeader('Lines'):
            self.putHeader('Lines', str(string.count(self.body, '\n')))
        
        if not self.getHeader('Date'):
            self.putHeader('Date', time.ctime(time.time()))


    
    def getHeader(self, header):
        if self.headers.has_key(string.lower(header)):
            return self.headers[string.lower(header)][1]
        else:
            return ''

    def putHeader(self, header, value):
        self.headers[string.lower(header)] = (header, value)


    def textHeaders(self):
        headers = []
        for i in self.headers.values():
            headers.append('%s: %s' % i)
        return string.join(headers, '\r\n')
    
    def overview(self):
        xover = []
        for i in OVERVIEW_FMT:
            xover.append(self.getHeader(i))
        return xover


class NewsStorage:
    """
    An interface for storing and requesting news articles
    """
    
    def listRequest(self):
        """
        Returns a deferred whose callback will be passed a list of 4-tuples
        containing (name, max index, min index, flags) for each news group
        """
        raise NotImplementedError


    def subscriptionRequest(self):
        """
        Returns a deferred whose callback will be passed the list of
        recommended subscription groups for new server users
        """
        raise NotImplementedError
    
    
    def postRequest(self, message):
        """
        Returns a deferred whose callback will be invoked if 'message'
        is successfully posted to one or more specified groups and
        whose errback will be invoked otherwise.
        """
        raise NotImplementedError
    
    
    def overviewRequest(self):
        """
        Returns a deferred whose callback will be passed the a list of
        headers describing this server's overview format.
        """
        raise NotImplementedError


    def xoverRequest(self, group, low, high):
        """
        Returns a deferred whose callback will be passed a list of xover
        headers for the given group over the given range.  If low is None,
        the range starts at the first article.  If high is None, the range
        ends at the last article.
        """
        raise NotImplementedError


    def xhdrRequest(self, group, low, high, header):
        """
        Returns a deferred whose callback will be passed a list of XHDR data
        for the given group over the given range.  If low is None,
        the range starts at the first article.  If high is None, the range
        ends at the last article.
        """
        raise NotImplementedError

    
    def listGroupRequest(self, group):
        """
        Returns a deferred whose callback will be passed a two-tuple of
        (group name, [article indices])
        """
        raise NotImplementedError
    
    
    def groupRequest(self, group):
        """
        Returns a deferred whose callback will be passed a five-tuple of
        (group name, article count, highest index, lowest index, group flags)
        """
        raise NotImplementedError

    
    def articleExistsRequest(self, id):
        """
        Returns a deferred whose callback will be passed with a true value
        if a message with the specified Message-ID exists in the database
        and with a false value otherwise.
        """
        raise NotImplementedError

    
    def articleRequest(self, group, index):
        """
        Returns a deferred whose callback will be passed the full article
        text (headers and body) for the article of the specified index
        in the specified group, and whose errback will be invoked if the
        article or group does not exist.
        """
        raise NotImplementedError

    
    def headRequest(self, group, index):
        """
        Returns a deferred whose callback will be passed the header for
        the article of the specified index in the specified group, and
        whose errback will be invoked if the article or group does not
        exist.
        """
        raise NotImplementedError

    
    def bodyRequest(self, group, index):
        """
        Returns a deferred whose callback will be passed the body for
        the article of the specified index in the specified group, and
        whose errback will be invoked if the article or group does not
        exist.
        """
        raise NotImplementedError


class PickleStorage(NewsStorage):
    """A trivial NewsStorage implementation using pickles
    
    Contains numerous flaws and is generally unsuitable for any
    real applications.  Consider yourself warned!
    """

    sharedDBs = {}

    def __init__(self, filename, groups = None):
        self.datafile = filename
        self.load(filename, groups)

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
            flags = 'y'
            r.append((i, high, low, flags))
        return defer.succeed(r)

    def subscriptionRequest(self):
        return defer.succeed(['alt.test'])

    def postRequest(self, message):
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
        for g in self.db.values():
            for a in g.values():
                if a.getHeader('Message-ID') == id:
                    return defer.succeed(1)
        return defer.succeed(0)

    def articleRequest(self, group, index):
        if self.db.has_key(group):
            if self.db[group].has_key(index):
                a = self.db[group][index]
                return defer.succeed((index, a.getHeader('Message-ID'), a.textHeaders() + a.body))
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
                return defer.succeed((index, a.getHeader('Message-ID'), a.body))
            else:
                return defer.fail(ERR_NOARTICLE)
        else:
            return defer.fail(ERR_NOGROUP)

    def flush(self):
        pickle.dump(self.db, open(self.datafile, 'w'))

    def load(self, filename, groups = None):
        if PickleStorage.sharedDBs.has_key(filename):
            self.db = PickleStorage.sharedDBs[filename]
        else:
            try:
                self.db = pickle.load(open(filename))
                PickleStorage.sharedDBs[filename] = self.db
            except IOError, e:
                self.db = PickleStorage.sharedDBs[filename] = {}
                self.db['groups'] = groups
                if groups is not None:
                    for i in groups:
                        self.db[i] = {}
                self.flush()


class NewsStorageAugmentation(adbapi.Augmentation, NewsStorage):
    """
    A NewsStorage implementation using Twisted's asynchronous DB-API
    """

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

    CREATE UNIQUE INDEX posting_group_index ON postings (group_id);
    CREATE UNIQUE INDEX posting_article_index ON postings (article_id);

    CREATE TABLE subscriptions (
        group_id    INTEGER
    );
    
    CREATE TABLE overview (
        header      TEXT
    );
    """


    def listRequest(self):
        sql = """
            SELECT name FROM groups ORDER BY name
        """
        return self.runQuery(sql)


    def subscriptionRequest(self):
        sql = """
            SELECT groups.name FROM groups,subscriptions WHERE groups.group_id = subscriptions.group_id
        """
        return self.runQuery(sql)


    def postRequest(self, message):
        cleave = string.find(message, '\r\n\r\n')
        headers, article = message[:cleave], message[cleave + 1:]
        article = Article(headers, article)
        return self.runInteraction(self._doPost, article)


    def _doPost(self, transaction, article):
        # Get the group ids
        groups = article.getHeader('Newsgroups').split()
        sql = """
            SELECT name, group_id FROM groups
            WHERE name IN (%s)
        """ % (', '.join([("'%s'" % (adbapi.safe(group),)) for group in groups]),)

        transaction.execute(sql)
        result = transaction.fetchall()
        
        # No relevant groups, bye bye!
        if not len(result):
            return 0
        
        # Got some groups, now find the indices this article will have in each
        sql = """
            SELECT group_id, MAX(article_index) + 1 FROM postings
            WHERE group_id IN (%s)
            GROUP BY group_id
        """ % (', '.join([("%d" % (id,)) for (group, id) in results]),)

        transaction.execute(sql)
        indices = transaction.fetchall()

        # XXX - This condition is an error, log it
        if not len(indices):
            return 0
        
        # Associate indices with group names
        gidToName = dict([(b, a) for (a, b) in result])
        gidToIndex = dict(indices)
        
        nameIndex = []
        for i in gidToName:
            nameIndex.append(gidToName[i], gidToIndex[i])
            
        
        # Build xrefs
        xrefs = socket.gethostname().split()[0]
        xrefs = xrefs + ' '.join([('%s:%d' % (group, id)) for (group, id) in nameIndex])
        article.putHeader('Xref', xref)
        
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
                VALUES (%d, (SELECT last_value FROM articles_article_id_sequence), %d)
            """ % (gid, gidToIndex[gid])
            transaction.execute(sql)
        
        return len(nameIndex)


    def overviewRequest(self):
        sql = """
            SELECT header FROM overview
        """
        q = self.runQuery(sql)
        q.addCallback(lambda result: [header[0] for header in result])
        return q


    def xoverRequest(self, group, low, high):
        sql = """
            SELECT articles.article_id, articles.header FROM articles,postings,groups
            WHERE postings.group_id = groups.group_id AND groups.name = '%s'
            AND postings.article_id = articles.article_id
            AND postings.article_index >= %d
            AND postings.article_index <= %d
        """ % (adbapi.safe(group), low, high)

        q = self.runQuery(sql)
        q.addCallback(lambda results: [Article(header, None).overview() for (id, header) in results])
        return q


    def xhdrRequest(self, group, low, high, header):
        sql = """
            SELECT postings.article_index, articles.header FROM articles,postings,groups
            WHERE postings.group_id = groups.group_id AND groups.name = '%s'
            AND postings.article_id = articles.article_id
            AND postings.article_index >= %d
            AND postings.article_index <= %d
        """ % (adbapi.safe(group), low, high)

        q = self.runQuery(sql)
        q.addCallback(lambda results: [(index, Article(header, None).getHeader(header)) for (index, header) in results])
        return q


    def listGroupRequest(self, group):
        sql = """
            SELECT postings.article_index FROM postings,groups
            WHERE postings.group_id = groups.group_id
            AND groups.name = '%s'
        """ % (adbapi.safe(group),)
        
        q = self.runQuery(sql)
        q.addCallback(lambda results: (group, [res[0] for res in results]))
        return q


    def groupRequest(self, group):
        sql = """
            SELECT groups.name, COUNT(postings.article_index),
                   MAX(postings.article_index), MIN(postings.article_index),
                   groups.flags FROM groups,postings
            WHERE groups.name = '%s' AND postings.group_id = groups.group_id
        """ % (adbapi.safe(group),)
        
        q = self.runQuery(sql)
        q.addCallback(lambda results: tuple(results[0]))


    def articleExistsRequest(self, id):
        sql = """
            SELECT COUNT(message_id) FROM articles
            WHERE message_id = '%s'
        """ % (id,)
        
        q = self.runQuery(sql)
        q.addCallback(lambda result: bool(result[0][0]))
        return q

    
    def articleRequest(self, group, index):
        sql = """
            SELECT articles.header, articles.body FROM groups,postings,articles
            WHERE groups.name = '%s' AND postings.group_id = groups.group_id
            AND postings.article_index = %d
        """ % (adbapi.safe(group), index)
        
        q = self.runQuery(sql)
        q.addCallback(lambda result: result[0][0] + '\r\n' + result[0][1])
        return q


    def headRequest(self, group, index):
        sql = """
            SELECT articles.header FROM groups,postings,articles
            WHERE groups.name = '%s' AND postings.group_id = groups.group_id
            AND postings.article_index = %d
        """ % (adbapi.safe(group), index)
        
        q = self.runQuery(sql)
        q.addCallback(lambda result: result[0][0])
        return q


    def bodyRequest(self, group, index):
        sql = """
            SELECT articles.body FROM groups,postings,articles
            WHERE groups.name = '%s' AND postings.group_id = groups.group_id
            AND postings.article_index = %d
        """ % (adbapi.safe(group), index)
        
        q = self.runQuery(sql)
        q.addCallback(lambda result: result[0][0])
        return q
