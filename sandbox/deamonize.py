#
# Twisted, the Framework of Your Internet
# Copyright (C) 2003 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General
# Public License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307
# USA
#

'''
    Useful if you don't want to use taps.  Basically, you
    use this via the following code snippet:

        if '__main__' == __name__:
            from deamonize import startstop
            startstop(stdout='/tmp/your.log',
                      pidfile='/tmp/your.pid')
            # setup resources
            reactor.run()

    Then, to run the server 'interactively', just do 

      $ python server.py

    in this case, startstop is a noop.  However, what is more
    useful is stop/start/restarting the process, in which case
    stdin/stdout is redirected, etc.

      $ python server.py start|stop|restart

'''
import sys, os, time
from signal import SIGTERM

def deamonize(stdout='/dev/null', stderr=None, stdin='/dev/null',
              pidfile=None, startmsg = None, chdir=None):
    '''
        This module is used to fork the current process into a daemon.
        This forks the current process into a daemon.  The stdin, stdout, 
        and stderr arguments are file names that will be opened and be 
        used to replace the standard file descriptors in sys.stdin, 
        sys.stdout, and sys.stderr.  These io arguments are optional 
        and default to /dev/null.  Note that stderr is opened unbuffered,
        so if it shares a file with stdout then interleaved output may 
        not appear in the order that you expect.

        References:
            UNIX Programming FAQ
                1.7 How do I get my program to act like a daemon?
                    http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
            Advanced Programming in the Unix Environment
                W. Richard Stevens, 1992, Addison-Wesley, ISBN 0-201-56317-7.
    '''
    # Do first fork.
    try: 
        pid = os.fork() 
        if pid > 0: sys.exit(0) # Exit first parent.
    except OSError, e: 
        sys.stderr.write("fork #1 failed: (%d) %s\n" % (e.errno, e.strerror))
        sys.exit(1)
        
    # Decouple from parent environment.
    if chdir: os.chdir(chdir)
    os.umask(0) 
    os.setsid() 
    
    # Do second fork.
    try: 
        pid = os.fork() 
        if pid > 0: sys.exit(0) # Exit second parent.
    except OSError, e: 
        sys.stderr.write("fork #2 failed: (%d) %s\n" % (e.errno, e.strerror))
        sys.exit(1)
    
    # Open file descriptors and print start message
    if not stderr: stderr = stdout
    si = file(stdin, 'r')
    so = file(stdout, 'a+')
    se = file(stderr, 'a+', 0)
    pid = str(os.getpid())
    if startmsg:
        sys.stderr.write("\n%s\n" % startmsg % pid)
        sys.stderr.flush()
    if pidfile: file(pidfile,'w+').write("%s\n" % pid)
    
    # Redirect standard file descriptors.
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

def startstop(stdout='/dev/null', stderr=None, stdin='/dev/null',
              pidfile='/tmp/pid.txt', startmsg = 'started with pid %s',
              chdir = None):
    if len(sys.argv) > 1:
        action = sys.argv[1]
        try:
            pf  = file(pidfile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        if 'stop' == action or 'restart' == action:
            if not pid:
                mess = "Could not stop, pid file '%s' missing.\n"
                sys.stderr.write(mess % pidfile)
                sys.exit(1)
            try:
               while 1:
                   os.kill(pid,SIGTERM)
                   time.sleep(1)
            except OSError, err:
               err = str(err)
               if err.find("No such process") > 0:
                   os.remove(pidfile)
                   if 'stop' == action:
                       sys.exit(0)
                   action = 'start'
                   pid = None
               else:
                   print str(err)
                   sys.exit(1)
        if 'start' == action:
            if pid:
                mess = "Start aborded since pid file '%s' exists.\n"
                sys.stderr.write(mess % pidfile)
                sys.exit(1)
            deamonize(stdout,stderr,stdin,pidfile,startmsg,chdir)
            return
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)

def test():
    '''
        This is an example main function run by the daemon.
        This prints a count and timestamp once per second.
    '''
    sys.stdout.write ('\nMessage to stdout...\n')
    sys.stderr.write ('\nMessage to stderr...\n')
    c = 0
    while 1:
        sys.stdout.write ('%d: %s\n' % (c, time.ctime(time.time())) )
        sys.stdout.flush()
        c = c + 1
        time.sleep(1)

if __name__ == "__main__":
    startstop(stdout='/tmp/deamonize.log',
              pidfile='/tmp/deamonize.pid',
              chdir="/")
    test()
