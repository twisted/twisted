# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Interface documentation."""

from twisted.python import components


class IProducer(components.Interface):
    """A producer produces data for a consumer.
    
    If this is a streaming producer, it will only be
    asked to resume producing if it has been previously asked to pause.
    Also, if this is a streaming producer, it will ask the producer to
    pause when the buffer has reached a certain size.

    In other words, a streaming producer is expected to produce (write to
    this consumer) data in the main IO thread of some process as the result
    of a read operation, whereas a non-streaming producer is expected to
    produce data each time resumeProducing() is called.
    
    If this is a non-streaming producer, resumeProducing will be called
    immediately, to start the flow of data.  Otherwise it is assumed that
    the producer starts out life unpaused.
    """
    
    def resumeProducing(self):
        """Resume producing data.
        
        This tells a producer to re-add itself to the main loop and produce
        more data for its consumer.
        """
        raise NotImplementedError

    def pauseProducing(self):
        """Pause producing data.
        
        Tells a producer that it has produced too much data to process for
        the time being, and to stop until resumeProducing() is called.
        """
        raise NotImplementedError

    def stopProducing(self):
        """Stop producing data.
        
        This tells a producer that its consumer has died, so it must stop
        producing data for good.
        """
        raise NotImplementedError


class ISelectable(components.Interface):
    """An object that can be registered with the networking event loop.
    
    Selectables more or less correspond to object that can be passed to select().
    This is platform dependant, and not totally accurate, since the main event loop
    may not be using select().
    
    Selectables may be registered as readable by passing them to t.i.main.addReader(),
    and they may be registered as writable by passing them to t.i.main.addWriter().
    
    In general, selectables are expected to inherit from twisted.python.log.Logger.
    """
    
    def doWrite(self):
        """Called when data is available for writing.
        
        This will only be called if this object has been registered as a writer in
        the event loop.
        """
        raise NotImplementedError
    
    def doRead(self):
        """Called when data is available for reading.
        
        This will only be called if this object has been registered as a reader in
        the event loop.
        """
        raise NotImplementedError
    
    def fileno(self):
        """Return a file descriptor number for select().

        This method must return an integer, the object's file descriptor.
        """
        raise NotImplementedError
    
    def connectionLost(self):
        """Called if an error has occured or the object's connection was closed.
        
        This may be called even if the connection was never opened in the first place.
        """
        raise NotImplementedError


__all__ = ["IProducer", "ISelectable"]
