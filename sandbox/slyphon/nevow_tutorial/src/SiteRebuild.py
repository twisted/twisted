from twisted.python.rebuild import rebuild
from twisted.web.woven.page import Page
import twisted.web.util as util
from glob import glob

class RebuildPage(Page):
    def initialize(self, *args, **kwargs):
        Page.initialize(self, *args, **kwargs)
        self.template = """
<html></html>
"""

        filelist = glob("*.py")
        try:
            filelist.remove("RunHome.py")
            filelist.remove("SiteRebuild.py")
        except ValueError, e:
            pass 

        for f in filelist:
            name, ext = f.split('.', 1)
            module = __import__(name)
            rebuild(module)


        storagelist = glob("storage/*.py")

        try:
            storagelist.remove("storage/__init__.py")
            # TODO: change this once PickleStorage is implemented
            storagelist.remove("storage/PickleStorage.py")
        except ValueError, e:
            pass 
    
        iter = enumerate(storagelist)
        while True:
            try:
                (index, value) = iter.next()
                storagelist[index] = value.replace('/', '.')
            except StopIteration:
                break

        filelist.extend(storagelist)

        
        return util.redirectTo("http://localhost:7000/edit",kwargs['request'])




