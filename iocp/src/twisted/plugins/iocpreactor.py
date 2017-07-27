from twisted.application.reactors import Reactor

iocpreactor = Reactor(
    'iocpreactor', 'iocpreactor',
    'Win32 I/O Completion Ports-based reactor.')

__all__ = ["iocpreactor"]
