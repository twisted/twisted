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
                 labelColor="yellow", labelFont="Verdana",
                 labelText="", labelFormat="%d%%",
                 value=50, bd=2):
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


class Processor:
    """A base class to allow ...
    Children must implement processOne
    """
    def __init__(self, bar, *args, **kwargs):
        self.bar=bar
        self.stopping=0
        self.remaining=-1
    
    def updateBar(self):
        b=self.bar
        try:
            b.updateProgress(b.max - self.remaining)
        except TclError:
            self.stopping=1
            
class Unzipness(Processor):
    """I am the procedure of unzipping a file.  When unzipping starts,
    I unzip the filename I am initialized with and show progress
    in the progress frame I am initialized with.

    """
    
    def __init__(self, bar, filename, whereto):
        Processor.__init__(self, bar)
        self.unzipper=zipstream.unzipIterChunky(filename, whereto)
        bar.updateProgress(0, zipstream.countZipFileChunks(filename, 4096))

    def processAll(self):
        d=defer.Deferred()
        reactor.callLater(0.1, self.processOne, d)
        return d

    def processOne(self, deferred):
        if self.stopping:
            return deferred.callback(self.remaining)
        
        try:
            self.remaining=self.unzipper.next()
        except StopIteration:
            return deferred.callback(0)
        
        if self.remaining%10==0:
            reactor.callLater(0, self.updateBar)
        reactor.callLater(0, self.processOne, deferred)


def countPys(countl, directory, names):
    sofar=countl[0]
    sofar=sofar+len([f for f in names if f.endswith('.py')])
    countl[0]=sofar
    return sofar

def countPysRecursive(path):
    countl=[0]
    os.path.walk(path, countPys, countl)
    return countl[0]

def compiler(path):
    remaining=countPysRecursive(path)
    def justlist(all, directory, names):
        pynames=[os.path.join(directory, n) for n in names if n.endswith('.py')]
        all.extend(pynames)
    all=[]
    os.path.walk(path, justlist, all)
    
    i=zip(all, xrange(remaining-1, -1, -1))
    for f, remaining in i:
        py_compile.compile(f)
        yield remaining

class Compileness(Processor):
    def __init__(self, bar, directory):
        Processor.__init__(self, bar)
        self.directory=directory
        self.compiler=compiler(directory)
        bar.updateProgress(0, countPysRecursive(directory))

    def processAll(self):
        d=defer.Deferred()
        reactor.callLater(0.1, self.processOne, d)
        return d

    def processOne(self, deferred):
        if self.stopping:
            return deferred.callback(self.remaining)
        
        try:
            self.remaining=self.compiler.next()
        except StopIteration:
            return deferred.callback(0)
        
        if self.remaining%10==0:
            reactor.callLater(0, self.updateBar)
        reactor.callLater(0, self.processOne, deferred)    

def _switchToCompiling(root, bar, directory):
    root.title('Compiling to pyc...')
    comp=Compileness(bar, os.path.join(directory, 'twisted'))
    d=comp.processAll()
    d.addCallback(lambda _: reactor.stop())
    d.addErrback(util.println)
    return d

class TksetupOptions(usage.Options):
    optParameters=[["zipfile", "z", "", "a zipfile"],
                   ["ziptargetdir", "t", ".", "where to extract zipfile"],
                   ["compiledir", "c", ".", "a directory to compile"],
                   ]

def run(argv=sys.argv):
    options=TksetupOptions()
    try:
        options.parseOptions(argv)
    except usage.UsageError, e:
        print str(options)
        print str(e)
        sys.exit(1)
    
    root=Tkinter.Tk()
    root.title('Unzipping...')
    root.withdraw()
    root.protocol('WM_DELETE_WINDOW', reactor.stop)
    tksupport.install(root)
    
    prog=ProgressBar(root, value=0, labelColor="black", width=200)    
    prog.pack()

    uz=Unzipness(prog, argv[1], options['ziptargetdir'])

    reactor.callLater(0, root.deiconify)
    d=uz.processAll()
    d.addErrback(util.println)
    d.addCallback(lambda _: _switchToCompiling(root, prog,
                                               options['compiledir']))
    reactor.run()


if __name__=='__main__':
    run()

