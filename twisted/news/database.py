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
from twisted.python import defer
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
        head = map(lambda x: string.split(x, ': ', 1), string.split(head, '\r\n'))
        self.headers = {}
        for i in head:
            if len(i) == 0:
                continue
            elif len(i) == 1:
                self.headers[string.lower(i[0])] = (i, '')
            else:
                self.headers[string.lower(i[0])] = tuple(i)

        self.body = body
    
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

class PickleStorage:
    """A trivial NewsStorage implementation using pickles
    
    Contains numerous flaws and is generally unsuitable for any
    real applications.  Consider yourself warned!
    """

    sharedDBs = {}

    def __init__(self, filename, groups = None):
        self.datafile = filename
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
        cleave = string.find(message, '\r\n\r\n')
        headers, article = message[:cleave], message[cleave + 1:]

        a = Article(headers, article)
        groups = string.split(a.getHeader('Newsgroups'))
        xref = []

        for group in groups:
            if self.db.has_key(group):
                if len(self.db[group].keys()):
                    index = max(self.db[group].keys()) + 1
                else:
                    index = 1
                xref.append((group, str(index)))
                self.db[group][index] = a

        if len(xref) == 0:
            return defer.fail(None)
        
        if not a.getHeader('Message-ID'):
            s = str(time.time()) + a.body
            id = hexdigest(md5.md5(s)) + '@' + socket.gethostname()
            a.putHeader('Message-ID', id)

        if not a.getHeader('Bytes'):
            a.putHeader('Bytes', str(len(a.body)))
        
        if not a.getHeader('Lines'):
            a.putHeader('Lines', str(string.count(a.body, '\n')))
        
        if not a.getHeader('Date'):
            a.putHeader('Date', time.ctime(time.time()))

        a.putHeader('Xref', '%s %s' % (string.split(socket.gethostname())[0], string.join(map(lambda x: string.join(x, ':'), xref), '')))

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
                r.append((i, self.db[group][i].headers[header]))
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

class DatabaseStorage(adbapi.Augmentation):
    """
    A DB-API 2.0 NewsStorage implementation
    """

    def __init__(self):
        self._dbPool = adbapi.ConnectionPool('pgdb', 'localhost', 'news', 'news')
        adbapi.Augmentation.__init__(self, DatabaseStorage._dbPool)

    def listRequest(self):
        sql = "SELECT name FROM Groups ORDER BY name"
        return self.runOperation(sql)

    def articleRequest(self, group, index):
        sql = "SELECT head, body FROM Articles WHERE group = ? AND index = ?"
        return self.runOperation(sql, group, index)

    def headRequest(self, group, index):
        sql = "SELECT head FROM Articles WHERE group = ? AND index = ?"
        return self.runOperation(sql, group, index)

    def bodyRequest(self, group, index):
        sql = "SELECT body FROM Articles WHERE group = ? AND index = ?"
        return self.runOperation(sql, group, index)

class NewsSQLdb:
    CREATE_GROUP = """
        create table Groups (
            id        int auto_increment,
            name    text,
            
            key(id)
        )
    """

    CREATE_ARTICLE = """
        create table Articles (
            number    int,
            id        text,
            gid        int,
            header    text,
            body    text
        )
    """
 
    def __init__(self, db, host = 'localhost', port = 3306, user = 'news', pwd = 'news'):
        self.db = MySQLdb.Connect(host=host, port=port, user=user, passwd=pwd)
        self.cursor = self.db.cursor()

        try:
            self.db.select_db(db)
        except MySQLdb.OperationalError:
            self.cursor.execute('create database %s' % db)
            self.db.select_db(db)
            self.cursor = self.db.cursor()

        if self.cursor.execute('show tables') != 2:
            try:
                self.cursor.execute(NewsSQLdb.CREATE_GROUP)
                self.cursor.execute(NewsSQLdb.CREATE_ARTICLE)
            except Exception, e:
                self.cursor.execute('drop table if exists Groups')
                self.cursor.execute('drop table if exists Articles')
                raise e

    def getGroups(self):
        QUERY = """
            select max(number), min(number) from Articles 
            where gid=%d
        """
        l = []
        self.cursor.execute('select name, id from Groups')
        for i in self.cursor.fetchall():
            self.cursor.execute(QUERY % i[1])
            l.append(self.fetchall())
        return l
