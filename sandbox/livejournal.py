from __future__ import nested_scopes

from twisted.protocols import http
from twisted.internet import protocol, defer
from twisted.python.util import println
from urllib import urlencode
import md5, time, re, os, stat, rfc822

class BadHTTP(Exception):
    pass

class BadLJ(Exception):
    pass

class FailLJ(Exception):
    pass


class LJClient(http.HTTPClient):

    def connectionMade(self):
        self.sendCommand('POST', self.factory.url)
        self.sendHeader('Host', self.factory.host)
        self.sendHeader('User-Agent', self.factory.agent)
        self.sendHeader('Content-Type', 'application/www-urlencoded')
        self.sendHeader('Content-Length', str(len(self.factory.data)))
        self.endHeaders()
        self.transport.write(self.factory.data)

    def handleStatus(self, version, status, message):
	if status != '200':
	    self.factory.error(BadHTTP(status, message))
            self.transport.loseConnection()

    def handleResponse(self, resp):
        lines = resp.splitlines()
        if len(lines)%2:
            self.factory.error(BadLJ("non-even number of lines", resp))
            return
        keys = range(0,len(lines),2)
        values = range(1,len(lines),2)
        ret = {}
        for (key, value) in zip(keys, values):
            ret[lines[key]] = lines[value]
        if ret.get("success", 'FAIL') == 'FAIL':
            self.factory.error(FailLJ(ret))
        else:
            self.factory.success(ret)


class LJFactory(protocol.ClientFactory):

    protocol = LJClient

    def __init__(self, host, url, data, agent):
        self.url = url
        self.host = host
        self.agent = agent
        self.data = data
        self.deferred = defer.Deferred()
        self.fired = 0

    def clientConnectionFailed(self, _, reason):
        self.error(reason)

    def error(self, e):
        if not self.fired:
            self.deferred.errback(e)
            self.fired = 1

    def success(self, r):
        if not self.fired:
            self.deferred.callback(r)
            self.fired = 1



class LiveJournal:

    getMoods = 0
    getpickws = 0

    def __init__(self, host, port, url, user, passwd):
        self.url = url
        self.host = host
        self.port = port
        self.user = user
        hash = md5.new()
        hash.update(passwd)
        self.passwd = hash.hexdigest()
        self.refreshLogin()
        self.onLogin = []

    def refreshLogin(self):
        self.loggedIn = 0
        self.moods = {}
        d = self._callRemote("login", getmoods=self.getMoods,
                             getpickws=self.getpickws)
        def _(d):
            self.loginInfo = d
            return d
        d.addCallback(_)
        d.addCallback(self.parseMoods)
        def _(d):
            self.loggedIn = 1
            return d
        def _(d):
            for f in self.onLogin:
                f[0](self)
            self.onLogin = []
        d.addCallback(_)
        def _(e):
            for f in self.onLogin:
                f[1](e)
            self.onLogin = []
        d.addErrback(_)

    def callRemote(self, name, **kw):
        if self.loggedIn:
            return self._callRemote(name, **kw)
        f = self._makeFactory(name, **kw)
        self.onLogin((lambda _: reactor.connectTCP(self.host, self.port, f),
                      lambda e: f.deferred.errback(e)))
        return f.deferred

    def _makeFactory(self, name, **kw):
        d = {'mode': name, 'user': self.user, 'hpassword': self.passwd}
        d.update(kw)
        data = urlencode(d)
        factory = LJFactory(self.host, self.url, data, 'TwistedLJ/0.1')
        return factory

    def _callRemote(self, name, **kw):
        from twisted.internet import reactor
        factory = self._makeFactory(name, **kw)
        reactor.connectTCP(self.host, self.port, factory)
        return factory.deferred

    def getMoods(self):
        if self.loggedIn:
            return defer.success(self.moods)
        d = defer.Deferred()
        self.onLogin.append((lambda self: d.callback(self.moods),
                             lambda e: d.errback(e)))
        return d

    def parseMoods(self, d):
        idRe = re.compile("mood_(\d+)_id$")
        for (key, value) in d.items():
            m = idRe.match(key)
            if m:
                n = m.group(1)
                self.moods[value] = d["mood_%s_name" % n]
        return d


def postFile(lj, fp, t=None):
    if t is None:
        t = os.fstat(fp.fileno())[stat.ST_MTIME]
    t = time.localtime(t)
    mess = rfc822.Message(fp)
    event = fp.read()
    subject = mess.get('subject')
    mood = mess.get('mood').split('#', 1)[0]
    year = time.strftime("%Y", timetuple)
    mon = time.strftime("%m", timetuple)
    day = time.strftime("%d", timetuple)
    hour = time.strftime("%H", timetuple)
    min = time.strftime("%M", timetuple)
    d = lj.callRemote("postevent", event=event, subject=subject, mood=mood,
                      year=year, mon=mon, day=day, hour=hour, min=min)
    return d


class SimpleProcessRunner(protocol.ProcessProtocol):

    def __init__(self):
        self.d = defer.Deferred()

    def processEnded(self, reason):
        self.d.callback(reason)

def prepareFile(lj, fname):
    d = lj.getMoods()
    d.addErrback(println, "error")
    def _(moods):
        fp = open(fname, 'w')
        fp.write('Subject: \n')
        fp.write('Comment: delete all but (maybe) one of the moods below\n')
        for (key, value) in moods.items():
            fp.write('Mood: %s# -- %s\n' % (key, value))
        fp.write('Comment: write message below blank line\n')
        fp.write('\n')
        p = SimpleProcessRunner()
        from twisted.internet import reactor
        reactor.spawnProcess(p, "/usr/bin/sensible-editor",
                             ["/usr/bin/sensible-editor", fname])
        p.d.addCallback(lambda r: finish_this)
    d.addCallback(

    )


if __name__ == '__main__':
    from twisted.internet import reactor
    import getpass, sys
    passw = getpass.getpass()
    user = sys.argv[1]
    host = 'www.livejournal.com'
    url = '/interface/flat'
    port = 80
    lj = LiveJournal(host, port, url, user, passw)
    d = lj.getMoods()
    d.addCallback(lambda d: (println(d),reactor.stop()))
    d.addErrback(lambda e: (println('error', e), reactor.stop()))
    reactor.run()
