#!/usr/bin/env python
import os, sys, shutil, time, string

def cmd(st):
    c = os.path.join(twistedBinDir,'') + st
    print "Running Command: %s" % repr(c)
    return os.system(c)

def browse(url):
    scmd(webbrowser+" "+url)
    if block:
        print "Hit enter to continue:"
        raw_input()

def scmd(st):
    print 'Running System Command: %s' % repr(st)
    return os.system(st)

def message(*m):
    print '/------'
    print '|####'
    for line in m:
        print '|####', line
    print '|####'
    print '\------'

def twistdf(f, p=None):
    if p:
        cmd("twistd --file %s.tap --rundir %s" % (f, p))
    else:
        cmd("twistd -f %s.tap" % (f,))
    time.sleep(0.5)

def twistdg(g):
    cmd("twistd -g %s" %g)
    time.sleep(0.5)

def twistdy(y):
    cmd("twistd -y %s" % (y,))
    time.sleep(0.5)

def killit(path=None):
    if path:
        scmd("kill `cat %s/twistd.pid`" % (path,))
    else:
        scmd("kill `cat twistd.pid`")
    # Give it a sec to come down.
    time.sleep(0.5)

def pause():
    print "Hit enter to continue."
    raw_input()

def GUITest():
    os.environ['PYTHONPATH'] = '%s:%s' % (os.environ.get('PYTHONPATH') or '',
                                          examplesDir)
    message("Running Qt app.")
    scmd("python %s/qtdemo.py" % examplesDir)
    message("Running wxPython app.")
    scmd("python %s/wxdemo.py" % examplesDir)
    
def basicToolTest():
    message("You will now be connected to an echo server")
    twistdy(twistedBinDir+"/../admin/echo.py")
    try:
        time.sleep(0.5)
        scmd("telnet localhost 18899")
    finally:
        killit()

def basicWebTest():
    message("Running Basic Web Test")
    cmd("mktap web --port 18080")
    try:
        twistdf("web")
        try:
            message("You should see a rather complex bunch of widgetry now.")
            browse("http://localhost:18080/")
        finally:
            killit()
    finally:
        scmd("rm web.tap")

def staticWebTest():
    cmd("mktap web --port 18080 --path %s/../static" % twistedBinDir)
    try:
        twistdf("web")
        try:
            message("You should see an 'it worked' page now.",
                    "(depending on your browser, you may need to reload)")
            browse("http://localhost:18080/")
            message("This is Python CGI test output.")
            browse("http://localhost:18080/test.cgi")
            message("This is RPY test output.")
            browse("http://localhost:18080/test.rpy")
        finally:
            killit()
    finally:
        scmd("rm web.tap")

def sslWebTest():
    cmdfmt = ("mktap web --port 18080 --https=18443 -k "
             "%s/../doc/examples/server.pem "
              "-c %s/../doc/examples/server.pem --path %s/../static")
    message("Running SSL Web Test")
    cmd(cmdfmt % (twistedBinDir, twistedBinDir, twistedBinDir))
    try:
        twistdf("web")
        try:
            browse("https://localhost:18443/")
        finally:
            killit()
    finally:
        scmd("rm web.tap")

def distWebTest():
    message("Running Distributed Web Test")

    # make directories to stage the test
    scmd("mkdir Personal");    scmd("mkdir User")

    # make & start servers
    cmd("mktap --append Personal/web.tap web --personal --port 18080")
    twistdf("Personal/web", "Personal")

    cmd("mktap --append User/web.tap web --user --port 18080")
    twistdf("User/web", "User")

    try:
        # browse a dead web page
        message("This should say 'Unable to connect to distributed server'",
                "If it doesn't finish loading, it's broken.  Reload a few times..")
        browse("http://localhost:18080/nobody.twistd")

        # browse a live web page
        message("This should be a bunch-of-widgets test page.")
        browse("http://localhost:18080/%s.twistd" % username)
    finally:
        killit("User")
        killit("Personal")
        
        shutil.rmtree("User")
        shutil.rmtree("Personal")

def runTelnetTest():
    message("Running Telnet Test")
    cmd("mktap telnet -p 18023 -u username -w password")
    try:
        twistdf("telnet")
        try:
            message("Log in with the username 'username', password 'password'.",
                    "You should be able to execute python code.",
                    "Log out with '^]close'")
            scmd("telnet localhost 18023")
        finally:
            killit()
    finally:
        scmd("rm telnet.tap")

def runManholeTest():
    message("Running Manhole Test")
    cmd("mktap manhole --port 12943 -u username -w password")
    try:
        twistdf("manhole")
        try:
            message("Log in with the username 'username', password 'password'.",
                    "and bask in the l33tness of direct manipulation.")
            cmd("manhole --port 12943")
        finally:
            killit()
    finally:
        scmd("rm manhole.tap")

def runWordsTest():
    message("Running Words Test")
    cmd("mktap words --irc 16767 --port 18787 --web 18080")
    try:
        twistdf("words")
        try:
            message("Create yourself an account, username 'test' password 'testing'.")
            browse("http://localhost:18080/create")
            message("You will have to '/msg *login* testing' to log in.")
            scmd(ircclient+" test localhost:16767")
            block and pause()
            message("Now let's test the 'im' interface.")
            cmd("im")
        finally:
            killit()
    finally:
        scmd("rm words.tap")

def runRealityTest():
    message("Running Reality Test")
    for mapname, loginname, password in [('TRDemo', 'guest', 'guest'),
                                         ('Inheritance', 'Damien', 'admin'),
                                         ('Divunal', 'guest', 'guest')]:
        if os.path.exists(mapname):
            twistdg(mapname)
            message("Log in now, username %s password %s" %
                    (repr(loginname), repr(password)))
            cmd("faucet")
            message("Now again, with the TK interface.")
            cmd("faucet --toolkit tk")
            message("Log in again on the telnet interface.")
            scmd("telnet localhost 14040")
            message("Now take a look at the website, after logging in")
            browse("http://localhost:18080/")
            killit()
        else:
            message("reality map %s not found, skipping" % mapname)

def runExampleTest():
    os.environ['PYTHONPATH'] = '%s:%s' % (os.environ.get('PYTHONPATH') or '',
                                          examplesDir)
    scmd("python %s/pbecho.py" % examplesDir)
    twistdf("pbecho-start")
    try:
        message("You should see a 'hello world'")
        scmd("python %s/pbechoclient.py" % examplesDir)
        pause()
    finally:
        killit()

def runMailTest():
    message("Starting mail test. ",
            "Output should be one email (postmaster@foo.bar) ",
            "and one bounce (postmaster@no.such.domain).",)
    for p in ('dump', 'dump2'):
        if os.path.exists(p):
            scmd('rm -rf %s' % p)
        os.mkdir(p)
    cmd("mktap mail --domain foo.bar=dump --user postmaster=postmaster "
        " --pop3 18110")
    cmd("mktap --append mail.tap mail --relay 127.0.0.1,8025=dump2"
         "      --smtp 18026 --pop3 18111")
    twistdf("mail")
    try:
        time.sleep(1.0)
        import smtplib, poplib
        s = smtplib.SMTP('127.0.0.1', 18026)
        s.sendmail("m@moshez.org", ['postmaster@foo.bar'], '''\
Subject: How are you gentlemen?

All your base are belong to us
''')
        s.quit()
        time.sleep(5)
        p = poplib.POP3('127.0.0.1', 18110)
        p.apop('postmaster@foo.bar', 'postmaster')
        s = p.retr(1)
        print s
        print string.join(s[1], '\n')
        p.dele(1)
        p.quit()

        s = smtplib.SMTP('127.0.0.1', 18026)
        s.sendmail("postmaster@foo.bar", ['moshez@no.such.domain'], '''\
Subject: How are you ladies?

All your dependents are belong to us
''')
        s.quit()
        time.sleep(10)
        p = poplib.POP3('127.0.0.1', 18110)
        p.apop('postmaster@foo.bar', 'postmaster')
        print string.join(p.retr(1)[1], '\n')
        p.dele(1)
        p.quit()
    finally:
        killit()
        scmd('rm -rf dump dump2')


def runAllTests():
    message("Starting test.")
    GUITest()
    basicToolTest()
    basicWebTest()
    staticWebTest()
    sslWebTest()
    distWebTest()
    runManholeTest()
    runTelnetTest()
    runWordsTest()
    runRealityTest()
    runExampleTest()
    runMailTest()
    message('All tests run.')


twistedBinDir = os.path.join(os.path.dirname(sys.argv[0]), '..', 'bin')
examplesDir = twistedBinDir+'/../doc/examples'

def main():
    global webbrowser, username, ircclient, block
    try:
        block = sys.argv[1] == "-b"
    except IndexError:
        block = None
    try:
        webbrowser = os.environ['WEBBROWSER']
        username = os.environ['USER']
        ircclient = os.environ['IRCCLIENT']
    except KeyError:
        message("Required Environment Variables:",
                "  * WEBBROWSER: a command which will run a web browser.",
                "                (If this doesn't block until the window is closed,",
                "                 pass '-b' as an argument to the script.)",
                "  * IRCCLIENT: an IRC client in the style of ircii (use -b in the",
                "               same situation as above)",
                "  * USER: your UNIX username.")
    else:
        runAllTests()

if __name__ == '__main__':
    main()
