import sys
import zipfile
# wx
from wxPython.wx import *
from wxPython.xrc import *
# twisted
from twisted.internet import wxsupport, reactor, defer
from twisted.python import failure, log
# local
from PASS_unzip import unzipiter

class ProgressFrame:
    def __init__(self):
        self._frm=xml.LoadFrame(None, 'FRAME1')
        EVT_CLOSE(self._frm, self.on_close)
        self.gauge=XRCCTRL(self, "GAUGE")

    def __getattr__(self, name):
        return getattr(self._frm, name)

    def on_close(self, evt):
        self._frm.Destroy()


class Unzipness:
    """I am the procedure of unzipping a file.  When unzipping starts,
    I unzip the filename I am initialized with and show progress
    in the progress frame I am initialized with.

    """
    
    def __init__(self, filename, frame):
        self.unzipper=unzipiter(filename)
        zf=zipfile.ZipFile(filename)
        frame.gauge.SetRange(len(zf.namelist()))
        self.frame=frame

    def onUnzipError(self):
        try:
            self.frame.Close()
        except wxPyDeadObjectError:
            pass
        reactor.stop()

    def unzipNext(self):
        try:
            remaining=self.unzipper.next()
        except StopIteration:
            return self.onUnzipError()

        self.updateBar(remaining)

        reactor.callLater(0, self.unzipNext) # should I use chainDeferred
                                             # instead?

    def updateBar(self, remaining):
        bar=self.frame.gauge
        try:
            bar.SetValue(bar.GetRange()-remaining)
        except wxPyDeadObjectError:
            self.onUnzipError()
    

def run(argv=sys.argv):
    app=wxPySimpleApp()
    wxsupport.install(app)
    frame=ProgressFrame()
    if len(argv)<=1:
        log.err("Need a filename")
        frame.Close()
        return
    uz=Unzipness(argv[1], frame)
    reactor.callLater(0, frame.Show)
    reactor.callLater(0, uz.unzipNext)
    reactor.run(installSignalHandlers=0)

thexml="""<?xml version="1.0" ?>
<resource>
  <object class=\"wxFrame\" name=\"FRAME1\">
    <title>Unzipping...</title>
    <object class=\"wxBoxSizer\">
      <orient>wxVERTICAL</orient>
      <object class=\"sizeritem\">
        <object class=\"wxGauge\" name=\"GAUGE\">
          <size>200,23</size>
          <style>wxGA_SMOOTH</style>
          <shadow>1</shadow>
          <bg>#C0C0C0</bg>
        </object>
        <flag>wxALL|wxEXPAND</flag>
        <border>3</border>
      </object>
    </object>
  </object>
</resource>
"""
thexmlfile=file('blah.xrc', 'w')
thexmlfile.write(thexml)
thexmlfile.close()
xml=wxXmlResource('blah.xrc')




if __name__=='__main__':
    run()

