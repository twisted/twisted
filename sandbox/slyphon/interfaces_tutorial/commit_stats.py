#!/usr/bin/env python2.3 

from mailbox import PortableUnixMailbox as pmbox
from pprint import pprint as pp
from cStringIO import StringIO
import time, sys, re, rfc822
import calendar
from datetime import tzinfo, timedelta, datetime
from pprint import pprint as pp

import cPickle
from pickle import PickleError

from twisted.python import components
from twisted.scripts import mailmail as mm


COMMITS_LIST = "divmod-commits"
PICKLE_PATH = '/home/slyphon/Projects/Quotient/sandbox/slyphon/cvsstat.pkl'

class Options:
    pass

def sendmail(msg):
    
    o = Options
    o.sender = 'cvs_stats@divmod.org'
    o.to = 'slyphon@divmod.org'
    o.body = '''From: <cvs_stats@divmod.org>
To: <slyphon@divmod.org>
Reply-to: 
MIME-Version: 1.0
Subject: cvs stats for %s
X-Mailer: twisted mailmail

%s
''' % (time.asctime(), msg)
    
    mm.sendmail('localhost', o, None)

INDENT = 15 
COLWIDTH = 4


class EST(tzinfo):
    UTC_DIFF = -5

    def __init__(self):
        pass

    def utcoffset(self, dt):
        # you know what? SCREW DST!
        return timedelta(hours=self.UTC_DIFF)
    

from pprint import pprint as pp

class Store(object):
    def __init__(self, pickle):
        self.pickle = pickle

    def loadHistory(self):
        try: 
            hist = cPickle.load(file(self.pickle, 'r'))
        except (PickleError, IOError), e:
            print "pickle file not found or PickleError raised, starting with fresh history"
            hist = History()
        
        return hist

    def saveHistory(self, hist):
        cPickle.dump(hist, file(self.pickle, 'w'))


class InvalidUserError(Exception):
    pass

class IStat(components.Interface):
    """a cvs commit statistic
    @ivar name: name of the cvs user
    @ivar date: date of the commit
    @ivar added: number of lines added in this commit
    @ivar removed: number of lines removed in this commit
    @ivar numCommits: when this class is used to accumulate stats
    for a number of commits, this is the number of commits this stat
    was generated from
    @ivar delta: net change in the number of lines
    """
    pass


class Stat(object):
    name, date = None, None
    reCleanWho = re.compile(r'(?P<name>^\w*)\b')

    def __init__(self, name=None, date=None, added=0, removed=0):
        """if date is not specified, then datetime.today() is used"""
        self.name = name
        if date == None:
            date = datetime.today()
        self.date = date
        self.added = added 
        self.removed = removed
        self.numCommits = 0

    def __cmp__(self, other):
        return self.uid == other.uid
    
    def __repr__(self):
        return "Stat object: %s" % str(self.uid)

    def _uid(self):
        return (self.name, self.added, self.removed, self.date)
    uid = property(_uid)

    def _getDelta(self):
        return self.added - self.removed
    delta = property(_getDelta)


class StatMessage(components.Adapter, Stat):
    def __init__(self, msg):
        name = self.reCleanWho.search(msg.get('from')).group('name')
        if 'MAILER' in name:
            raise InvalidUserError(name)

        added, removed = 0, 0
        for line in msg.fp.readlines():
            if line[0] == '+' and line[0:2] != '+++':
                added += 1
            if line[0] == '-' and line[0:2] != '---':
                removed += 1
        
        date = datetime.fromtimestamp(time.mktime(msg.getdate('date')))
        delta = added - removed
        Stat.__init__(self, name, date, added, removed)



components.registerAdapter(StatMessage, rfc822.Message, IStat)


class IRenderable(components.Interface):
    def render(self):
        pass

class StatRenderer(components.Adapter):
    __implements__ = IRenderable,
    indent, colwidth  = INDENT, COLWIDTH

    def render(self):
        o = self.original
        spacing = " " * (self.indent - len(o.name))
        return "%s%s%s\t%s\t%s\t%s\n" % (o.name, spacing, 
                                         str(o.numCommits).rjust(self.colwidth), 
                                         str(o.added).rjust(self.colwidth), 
                                         str(o.removed).rjust(self.colwidth), 
                                         str(o.delta).rjust(self.colwidth))

components.registerAdapter(StatRenderer, Stat, IRenderable)

class DuplicateStatError(Exception):
    pass

class History(object):
    _latestStat = None
    nameIdx = {}
    uidIdx = {}
    stats = []
    numDays = None

    def __getstate__(self):
        return {'nameIdx': self.nameIdx, 
                'uidIdx': self.uidIdx, 
                'stats': self.stats,
                '_latestStat': self._latestStat}

    def addStat(self, stat):
        if stat.uid in self.uidIdx:
            raise DuplicateStatError(stat)
        
        self.uidIdx[stat.uid] = stat
        self.stats.append(stat)

        if self._latestStat and stat.date > self._latestStat:
            self._latestStat = stat.date

        if stat.name not in self.nameIdx:
            self.nameIdx[stat.name] = [stat]
        else:
            self.nameIdx[stat.name].append(stat)

    def addStats(self, *args):
        for s in args:
            self.addStat(s)

    def totals(self):
        from itertools import ifilter
        from twisted.python import util
        
        def _(name):
            s = Stat(name=name)
            
            def f(st):
                a = st.name == name
                if self.numDays != None:
                    td = timedelta(days=self.numDays)
                    return a and datetime.today() - st.date < td                   
                return a

            for x in ifilter(f, self.stats):
                s.added += x.added
                s.removed += x.removed
                s.numCommits += 1
            return s

        t = util.dsu([_(name) for name in self.nameIdx.iterkeys()], lambda s: s.numCommits)
        t.reverse()
        return t


class HistoryRenderer(components.Adapter):
    """Converts a history object to IRenderable
    @cvar numDays: the number of days to calculate stats for, 
    if None, render all available stats
    """
    __implements__ = IRenderable,

    def render(self):
        sio = StringIO()
        w = sio.write
        w('stats for past %s days\n\n' % self.original.numDays)
        col1 = 'who'
        heading = "%s%scommits\tadded\tremoved\tdelta\n" % (col1, " " * (INDENT - len(col1)))
        w(heading)
        w("%s\n" % ('-' * (len(heading) + 4)))
        for stat in self.original.totals():
            w(IRenderable(stat).render())
        
        result = sio.getvalue()
        return result


components.registerAdapter(HistoryRenderer, History, IRenderable)


class StatMachine(object):
    def __init__(self):
        self.store = Store(PICKLE_PATH)
        self.hist = self.store.loadHistory()

    def getStatsReport(self, numDays):       
        sio = StringIO()
        w = sio.write
       
        self.hist.numDays = numDays
        w(IRenderable(self.hist).render())
        return sio.getvalue()

    def run(self):
        mbox = pmbox(file(COMMITS_LIST, 'r'))
        
        for msg in mbox:
            try:
                self.hist.addStat(IStat(msg))    
            except DuplicateStatError, e:
                continue

        sio = StringIO()
        w = sio.write
        w("%s\n\n" % time.asctime())
        w("(new files will not factor into stats (todo))\n\n")
 
        reports = [self.getStatsReport(numDays=nd) for nd in [1,7,30,90]]
        for report in reports:
            w(report + '\n\n')

        print sio.getvalue()
        #sendmail(sio.getvalue())

        self.store.saveHistory(self.hist)
 

if __name__ == "__main__":
    StatMachine().run()

