from __future__ import generators

import sys
import zipfile
import py_compile
# wx
import Tkinter
from Tkinter import *
# twisted
from twisted.internet import tksupport, reactor, defer
from twisted.python import failure, log, zipstream, util, usage
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
    
    def updateBar(self):
        b=self.bar
        try:
            b.updateProgress(b.max - self.remaining)
        except TclError:
            self.stopping=1

    def processAll(self, root):
        assert self.bar and self.iterator, "must setBar and setIterator"
        self.root=root
        root.title(self.title)
        d = defer.Deferred()
        reactor.callLater(0.1, self.processOne, d)
        return d

    def processOne(self, deferred):
        if self.stopping:
            return deferred.callback(self.root)
        
        try:
            self.remaining = self.iterator.next()
        except StopIteration:
            self.stopping = 1
        except:
            return deferred.errback(failure.Failure())
        
        if self.remaining%10 == 0:
            reactor.callLater(0, self.updateBar)
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

class TksetupOptions(usage.Options):
    optParameters=[["zipfile", "z", "", "a zipfile"],
                   ["ziptargetdir", "t", ".", "where to extract zipfile"],
                   ["compiledir", "c", "", "a directory to compile"],
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
    opt=TksetupOptions()
    try:
        opt.parseOptions(argv[1:])
    except usage.UsageError, e:
        print str(opt)
        print str(e)
        sys.exit(1)
    
    root=Tkinter.Tk()
    root.title('One Moment.')
    root.withdraw()
    root.protocol('WM_DELETE_WINDOW', reactor.stop)
    tksupport.install(root)
    
    prog=ProgressBar(root, value=0, labelColor="black", width=200)    
    prog.pack()
    root.deiconify()

    # callback immediately
    d=defer.succeed(root)
    
    if opt['zipfile']:
        uz=Progressor('Unzipping...')
        uz.setBar(prog, zipstream.countZipFileChunks(opt['zipfile'],
                                                     4096))
        uz.setIterator(zipstream.unzipIterChunky(opt['zipfile'],
                                                 opt['ziptargetdir']))
        d.addCallback(uz.processAll)

    if opt['compiledir']:
        comp=Progressor('Compiling to pyc...')
        comp.setBar(prog, countPysRecursive(opt['compiledir']))
        comp.setIterator(compiler(opt['compiledir']))
        d.addCallback(comp.processAll)

    d.addCallback(lambda _: reactor.stop())

    reactor.run()


if __name__=='__main__':
    run()

