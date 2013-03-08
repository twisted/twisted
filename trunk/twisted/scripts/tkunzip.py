# -*- test-case-name: twisted.scripts.test.test_scripts -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Post-install GUI to compile to pyc and unpack twisted doco.
"""

import sys
import zipfile
import py_compile

# we're going to ignore failures to import tkinter and fall back
# to using the console if the required dll is not found

# Scary kludge to work around tk84.dll bug:
# https://sourceforge.net/tracker/index.php?func=detail&aid=814654&group_id=5470&atid=105470
# Without which(): you get a windows missing-dll popup message
from twisted.python.procutils import which
tkdll='tk84.dll'
if which(tkdll) or which('DLLs/%s' % tkdll):
    try:
        import Tkinter
        from Tkinter import *
        from twisted.internet import tksupport
    except ImportError:
        pass

# twisted
from twisted.internet import reactor, defer
from twisted.python import failure, log, zipstream, util, usage, log
# local
import os.path

class ProgressBar:
    def __init__(self, master=None, orientation="horizontal",
                 min=0, max=100, width=100, height=18,
                 doLabel=1, appearance="sunken",
                 fillColor="blue", background="gray",
                 labelColor="yellow", labelFont="Arial",
                 labelText="", labelFormat="%d%%",
                 value=0, bd=2):
        # preserve various values
        self.master=master
        self.orientation=orientation
        self.min=min
        self.max=max
        self.width=width
        self.height=height
        self.doLabel=doLabel
        self.fillColor=fillColor
        self.labelFont= labelFont
        self.labelColor=labelColor
        self.background=background
        self.labelText=labelText
        self.labelFormat=labelFormat
        self.value=value
        self.frame=Frame(master, relief=appearance, bd=bd)
        self.canvas=Canvas(self.frame, height=height, width=width, bd=0,
                           highlightthickness=0, background=background)
        self.scale=self.canvas.create_rectangle(0, 0, width, height,
                                                fill=fillColor)
        self.label=self.canvas.create_text(self.canvas.winfo_reqwidth() / 2,
                                           height / 2, text=labelText,
                                           anchor="c", fill=labelColor,
                                           font=self.labelFont)
        self.update()
        self.canvas.pack(side='top', fill='x', expand='no')

    def pack(self, *args, **kwargs):
        self.frame.pack(*args, **kwargs)

    def updateProgress(self, newValue, newMax=None):
        if newMax:
            self.max = newMax
        self.value = newValue
        self.update()

    def update(self):
        # Trim the values to be between min and max
        value=self.value
        if value > self.max:
            value = self.max
        if value < self.min:
            value = self.min
        # Adjust the rectangle
        if self.orientation == "horizontal":
            self.canvas.coords(self.scale, 0, 0,
              float(value) / self.max * self.width, self.height)
        else:
            self.canvas.coords(self.scale, 0,
                               self.height - (float(value) /
                                              self.max*self.height),
                               self.width, self.height)
        # Now update the colors
        self.canvas.itemconfig(self.scale, fill=self.fillColor)
        self.canvas.itemconfig(self.label, fill=self.labelColor)
        # And update the label
        if self.doLabel:
            if value:
                if value >= 0:
                    pvalue = int((float(value) / float(self.max)) *
                                   100.0)
                else:
                    pvalue = 0
                self.canvas.itemconfig(self.label, text=self.labelFormat
                                         % pvalue)
            else:
                self.canvas.itemconfig(self.label, text='')
        else:
            self.canvas.itemconfig(self.label, text=self.labelFormat %
                                   self.labelText)
        self.canvas.update_idletasks()


class Progressor:
    """A base class to make it simple to hook a progress bar up to a process.
    """
    def __init__(self, title, *args, **kwargs):
        self.title=title
        self.stopping=0
        self.bar=None
        self.iterator=None
        self.remaining=1000

    def setBar(self, bar, max):
        self.bar=bar
        bar.updateProgress(0, max)
        return self

    def setIterator(self, iterator):
        self.iterator=iterator
        return self

    def updateBar(self, deferred):
        b=self.bar
        try:
            b.updateProgress(b.max - self.remaining)
        except TclError:
            self.stopping=1
        except:
            deferred.errback(failure.Failure())

    def processAll(self, root):
        assert self.bar and self.iterator, "must setBar and setIterator"
        self.root=root
        root.title(self.title)
        d=defer.Deferred()
        d.addErrback(log.err)
        reactor.callLater(0.1, self.processOne, d)
        return d

    def processOne(self, deferred):
        if self.stopping:
            deferred.callback(self.root)
            return

        try:
            self.remaining=self.iterator.next()
        except StopIteration:
            self.stopping=1
        except:
            deferred.errback(failure.Failure())

        if self.remaining%10==0:
            reactor.callLater(0, self.updateBar, deferred)
        if self.remaining%100==0:
            log.msg(self.remaining)
        reactor.callLater(0, self.processOne, deferred)

def compiler(path):
    """A generator for compiling files to .pyc"""
    def justlist(arg, directory, names):
        pynames=[os.path.join(directory, n) for n in names
                 if n.endswith('.py')]
        arg.extend(pynames)
    all=[]
    os.path.walk(path, justlist, all)

    remaining=len(all)
    i=zip(all, range(remaining-1, -1, -1))
    for f, remaining in i:
        py_compile.compile(f)
        yield remaining

class TkunzipOptions(usage.Options):
    optParameters=[["zipfile", "z", "", "a zipfile"],
                   ["ziptargetdir", "t", ".", "where to extract zipfile"],
                   ["compiledir", "c", "", "a directory to compile"],
                   ]
    optFlags=[["use-console", "C", "show in the console, not graphically"],
              ["shell-exec", "x", """\
spawn a new console to show output (implies -C)"""],
              ]

def countPys(countl, directory, names):
    sofar=countl[0]
    sofar=sofar+len([f for f in names if f.endswith('.py')])
    countl[0]=sofar
    return sofar

def countPysRecursive(path):
    countl=[0]
    os.path.walk(path, countPys, countl)
    return countl[0]

def run(argv=sys.argv):
    log.startLogging(file('tkunzip.log', 'w'))
    opt=TkunzipOptions()
    try:
        opt.parseOptions(argv[1:])
    except usage.UsageError, e:
        print str(opt)
        print str(e)
        sys.exit(1)

    if opt['use-console']:
        # this should come before shell-exec to prevent infinite loop
        return doItConsolicious(opt)
    if opt['shell-exec'] or not 'Tkinter' in sys.modules:
        from distutils import sysconfig
        from twisted.scripts import tkunzip
        myfile=tkunzip.__file__
        exe=os.path.join(sysconfig.get_config_var('prefix'), 'python.exe')
        return os.system('%s %s --use-console %s' % (exe, myfile,
                                                     ' '.join(argv[1:])))
    return doItTkinterly(opt)

def doItConsolicious(opt):
    # reclaim stdout/stderr from log
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    if opt['zipfile']:
        print 'Unpacking documentation...'
        for n in zipstream.unzipIter(opt['zipfile'], opt['ziptargetdir']):
            if n % 100 == 0:
                print n,
            if n % 1000 == 0:
                print
        print 'Done unpacking.'

    if opt['compiledir']:
        print 'Compiling to pyc...'
        import compileall
        compileall.compile_dir(opt["compiledir"])
        print 'Done compiling.'

def doItTkinterly(opt):
    root=Tkinter.Tk()
    root.withdraw()
    root.title('One Moment.')
    root.protocol('WM_DELETE_WINDOW', reactor.stop)
    tksupport.install(root)

    prog=ProgressBar(root, value=0, labelColor="black", width=200)
    prog.pack()

    # callback immediately
    d=defer.succeed(root).addErrback(log.err)

    def deiconify(root):
        root.deiconify()
        return root

    d.addCallback(deiconify)

    if opt['zipfile']:
        uz=Progressor('Unpacking documentation...')
        max=zipstream.countZipFileChunks(opt['zipfile'], 4096)
        uz.setBar(prog, max)
        uz.setIterator(zipstream.unzipIterChunky(opt['zipfile'],
                                                 opt['ziptargetdir']))
        d.addCallback(uz.processAll)

    if opt['compiledir']:
        comp=Progressor('Compiling to pyc...')
        comp.setBar(prog, countPysRecursive(opt['compiledir']))
        comp.setIterator(compiler(opt['compiledir']))
        d.addCallback(comp.processAll)

    def stop(ignore):
        reactor.stop()
        root.destroy()
    d.addCallback(stop)

    reactor.run()


if __name__=='__main__':
    run()
