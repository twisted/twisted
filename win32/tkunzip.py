import sys
import zipfile
# wx
import Tkinter
from Tkinter import *
# twisted
from twisted.internet import tksupport, reactor, defer, threads
from twisted.python import failure, log, zipstream
# local


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

    def destroy(self):
        reactor.stop()

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



class Unzipness:
    """I am the procedure of unzipping a file.  When unzipping starts,
    I unzip the filename I am initialized with and show progress
    in the progress frame I am initialized with.

    """
    
    def __init__(self, filename, bar):
#        self.unzipper=zipstream.unzipIterChunky(filename)
        self.unzipper=zipstream.unzipIter(filename)
        bar.updateProgress(0, zipstream.countZipFileEntries(filename))
        self.bar=bar
        self.stopping=0
        self.remaining=-1

    def unzipAll(self):
        d=defer.Deferred()
        reactor.callLater(0.1, self.unzipOne, d)
        return d        

    def unzipOne(self, deferred):
        if self.stopping:
            return deferred.callback(self.remaining)
        try:
            self.remaining=self.unzipper.next()
        except StopIteration:
            return deferred.callback(deferred)
        if self.remaining%10==0:
            reactor.callLater(0, self.updateBar)
        reactor.callLater(0, self.unzipOne, deferred)

    def updateBar(self):
        b=self.bar
        try:
            b.updateProgress(b.max - self.remaining)
        except TclError:
            self.stopping=1
    

def run(argv=sys.argv):
    if len(argv)<=1:
        log.err("Need a filename")
        return
    root=Tkinter.Tk()
    root.title('Unzipping...')
    root.withdraw()
    tksupport.install(root)
    
    prog=ProgressBar(root, value=0, labelColor="black", width=200)    
    prog.pack()

    uz=Unzipness(argv[1], prog)

    reactor.callLater(0, root.deiconify)
    d=uz.unzipAll()
    d.addCallback(lambda _: reactor.stop()).addErrback(lambda _: reactor.crash())
    
    reactor.run()


if __name__=='__main__':
    run()

