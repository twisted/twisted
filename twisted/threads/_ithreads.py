from zope.interface import Interface


class AlreadyQuit(Exception):
    """
    This worker worker is dead and cannot execute more instructions.
    """


class IWorker(Interface):
    """
    
    """

    def do(task):
        """
        
        """


    def quit():
        """
        
        """


