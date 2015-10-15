
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Generating Deferreds
====================






..  status of document: INCOMPLETE, DRAFT 


:api:`twisted.internet.defer.Deferred <Deferred>` objects are
signals that a function you have called does not yet have the data you want
available. When a function returns a Deferred object, your calling function
attaches callbacks to it to handle the data when available.




This document addresses the other half of the question: writing functions
that return Deferreds, that is, constructing Deferred objects, arranging for
them to be returned immediately without blocking until data is available, and
firing their callbacks when the data is available.




This document assumes that you are familiar with the asynchronous model used
by Twisted, and with :doc:`using deferreds returned by functions <defer>` 
.



.. _core-howto-gendefer-class:









Class overview
--------------



This is an overview API reference for Deferred from the point of creating a
Deferred and firing its callbacks and errbacks.  It is not meant to be a
substitute for the docstrings in the Deferred class, but can provide
guidelines for its use.




There is a parallel overview of functions used by calling function which
the Deferred is returned to at :ref:`Using Deferreds <core-howto-defer-class>` .





Basic Callback Functions
~~~~~~~~~~~~~~~~~~~~~~~~





- 
  ``callback(result)`` 
  
  
  Run success callbacks with the given result. *This can only be run once.* Later calls to this or
  ``errback`` will raise :api:`twisted.internet.defer.AlreadyCalledError <twisted.internet.defer.AlreadyCalledError>` .
  If further callbacks or errbacks are added after this
  point, addCallbacks will run the callbacks immediately.
  
  
- 
  ``errback(failure)`` 
  
  
  Run error callbacks with the given failure. *This can only be run once.* Later calls to this or
  ``callback`` will raise :api:`twisted.internet.defer.AlreadyCalledError <twisted.internet.defer.AlreadyCalledError>` .
  If further callbacks or errbacks are added after this
  point, addCallbacks will run the callbacks immediately.
  
  






What Deferreds don't do: make your code asynchronous
----------------------------------------------------



*Deferreds do not make the code magically not block.* 




Let's take this function as an example:





.. code-block:: python

    
    from twisted.internet import defer
    
    TARGET = 10000
    
    def largeFibonnaciNumber():
        # create a Deferred object to return:
        d = defer.Deferred()
    
        # calculate the ten thousandth Fibonnaci number
    
        first = 0
        second = 1
    
        for i in xrange(TARGET - 1):
            new = first + second
            first = second
            second = new
            if i % 100 == 0:
                print "Progress: calculating the %dth Fibonnaci number" % i
    
        # give the Deferred the answer to pass to the callbacks:
        d.callback(second)
    
        # return the Deferred with the answer:
        return d
    
    import time
    
    timeBefore = time.time()
    
    # call the function and get our Deferred
    d = largeFibonnaciNumber()
    
    timeAfter = time.time()
    
    print "Total time taken for largeFibonnaciNumber call: %0.3f seconds" % \
          (timeAfter - timeBefore)
    
    # add a callback to it to print the number
    
    def printNumber(number):
        print "The %dth Fibonacci number is %d" % (TARGET, number)
    
    print "Adding the callback now."
    
    d.addCallback(printNumber)




You will notice that despite creating a Deferred in the  ``largeFibonnaciNumber`` function, these things happened:




- the "Total time taken for largeFibonnaciNumber call" output
  shows that the function did not return immediately as asynchronous functions
  are expected to do; and
- rather than the callback being added before the result was available and
  called after the result is available, it isn't even added until after the
  calculation has been completed.





The function completed its calculation before returning, blocking the
process until it had finished, which is exactly what asynchronous functions
are not meant to do.  Deferreds are not a non-blocking talisman: they are a
signal for asynchronous functions to *use* to pass results onto
callbacks, but using them does not guarantee that you have an asynchronous
function.






Advanced Processing Chain Control
---------------------------------





- 
  ``pause()`` 
  
  
  Cease calling any methods as they are added, and do not
  respond to ``callback`` , until
  ``self.unpause()`` is called.
  
  
- 
  ``unpause()`` 
  
  
  If ``callback`` has been called on this
  Deferred already, call all the callbacks that have been
  added to this Deferred since ``pause`` was
  called.
  
  
  
  
  Whether it was called or not, this will put this
  Deferred in a state where further calls to
  ``addCallbacks`` or ``callback`` will
  work as normal.
  
  






Returning Deferreds from synchronous functions
----------------------------------------------



Sometimes you might wish to return a Deferred from a synchronous function.
There are several reasons why, the major two are maintaining API compatibility
with another version of your function which returns a Deferred, or allowing
for the possibility that in the future your function might need to be
asynchronous.




In the :doc:`Using Deferreds <defer>` reference, we gave the
following example of a synchronous function:





:download:`synch-validation.py <listings/deferred/synch-validation.py>`

.. literalinclude:: listings/deferred/synch-validation.py


While we can require that callers of our function wrap our synchronous
result in a Deferred using :api:`twisted.internet.defer.maybeDeferred <maybeDeferred>` , for the sake of API
compatibility it is better to return a Deferred ourselves using  :api:`twisted.internet.defer.succeed <defer.succeed>` :





.. code-block:: python

    
    from twisted.internet import defer
    
    def immediateIsValidUser(user):
        '''
        Returns a Deferred resulting in true if user is a valid user, false
        otherwise
        '''
    
        result = user in ["Alice", "Angus", "Agnes"]
    
        # return a Deferred object already called back with the value of result
        return defer.succeed(result)




There is an equivalent :api:`twisted.internet.defer.fail <defer.fail>` method to return a Deferred with the
errback chain already fired.





Integrating blocking code with Twisted
--------------------------------------



At some point, you are likely to need to call a blocking function: many
functions in third party libraries will have long running blocking functions.
There is no way to 'force' a function to be asynchronous: it must be written
that way specifically. When using Twisted, your own code should be
asynchronous, but there is no way to make third party functions asynchronous
other than rewriting them.




In this case, Twisted provides the ability to run the blocking code in a
separate thread rather than letting it block your application. The :api:`twisted.internet.threads.deferToThread <twisted.internet.threads.deferToThread>` function will set up
a thread to run your blocking function, return a Deferred and later fire that
Deferred when the thread completes.




Let's assume our ``largeFibonnaciNumber`` function
from above is in a third party library (returning the result of the
calculation, not a Deferred) and is not easily modifiable to be finished in
discrete blocks. This example shows it being called in a thread, unlike in the
earlier section we'll see that the operation does not block our entire
program:





.. code-block:: python

    
    def largeFibonnaciNumber():
        """
        Represent a long running blocking function by calculating
        the TARGETth Fibonnaci number
        """
        TARGET = 10000
    
        first = 0
        second = 1
    
        for i in xrange(TARGET - 1):
            new = first + second
            first = second
            second = new
    
        return second
    
    from twisted.internet import threads, reactor
    
    def fibonacciCallback(result):
        """
        Callback which manages the largeFibonnaciNumber result by
        printing it out
        """
        print "largeFibonnaciNumber result =", result
        # make sure the reactor stops after the callback chain finishes,
        # just so that this example terminates
        reactor.stop()
    
    def run():
        """
        Run a series of operations, deferring the largeFibonnaciNumber
        operation to a thread and performing some other operations after
        adding the callback
        """
        # get our Deferred which will be called with the largeFibonnaciNumber result
        d = threads.deferToThread(largeFibonnaciNumber)
        # add our callback to print it out
        d.addCallback(fibonacciCallback)
        print "1st line after the addition of the callback"
        print "2nd line after the addition of the callback"
    
    if __name__ == '__main__':
        run()
        reactor.run()





Possible sources of error
-------------------------



Deferreds greatly simplify the process of writing asynchronous code by
providing a standard for registering callbacks, but there are some subtle and
sometimes confusing rules that you need to follow if you are going to use
them. This mostly applies to people who are writing new systems that use
Deferreds internally, and not writers of applications that just add callbacks
to Deferreds produced and processed by other systems. Nevertheless, it is good
to know.





Firing Deferreds more than once is impossible
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



Deferreds are one-shot. You can only call ``Deferred.callback`` or ``Deferred.errback`` once. The processing chain continues each time
you add new callbacks to an already-called-back-to Deferred.





Synchronous callback execution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



If a Deferred already has a result available, ``addCallback`` **may** call the callback synchronously: that is, immediately
after it's been added.  In situations where callbacks modify state, it is
might be desirable for the chain of processing to halt until all callbacks are
added. For this, it is possible to ``pause`` and ``unpause`` 
a Deferred's processing chain while you are adding lots of callbacks.




Be careful when you use these methods! If you ``pause`` a
Deferred, it is *your* responsibility to make sure that you unpause it.
The function adding the callbacks must unpause a paused Deferred, it should *never* be the responsibility of the code that actually fires the
callback chain by calling ``callback`` or ``errback`` as
this would negate its usefulness!



