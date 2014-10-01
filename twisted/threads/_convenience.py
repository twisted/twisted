
from ._ithreads import AlreadyQuit

class Quit(object):
    """
    A flag representing whether a worker has been quit.

    Private; not exposed in a public interface anywhere.

    @ivar isSet: Whether this flag is set.
    @type isSet: L{bool}
    """

    def __init__(self):
        """
        Create a L{Quit} un-set.
        """
        self.isSet = False


    def set(self):
        """
        Set the flag if it has not been set.

        @raise AlreadyQuit: If it has been set.
        """
        self.check()
        self.isSet = True


    def check(self):
        """
        @raise AlreadyQuit: If it has been set.
        """
        if self.isSet:
            raise AlreadyQuit()
