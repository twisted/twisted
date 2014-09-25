
from ._ithreads import AlreadyQuit

class Quit(object):
    """
    
    """

    def __init__(self):
        """
        
        """
        self._hasQuit = False


    def __bool__(self):
        """
        
        """
        return self._hasQuit


    def set(self):
        """
        
        """
        self.check()
        self._hasQuit = True


    def check(self):
        """
        
        """
        if self:
            raise AlreadyQuit()
