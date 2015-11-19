
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Deferred Reference
==================





This document is a guide to the behaviour of the :api:`twisted.internet.defer.Deferred <twisted.internet.defer.Deferred>` object, and to various
ways you can use them when they are returned by functions.




This document assumes that you are familiar with the basic principle that
the Twisted framework is structured around: asynchronous, callback-based
programming, where instead of having blocking code in your program or using
threads to run blocking code, you have functions that return immediately and
then begin a callback chain when data is available.





After reading this document, the reader should expect to be able to
deal with most simple APIs in Twisted and Twisted-using code that
return Deferreds.





- what sorts of things you can do when you get a Deferred from a
  function call; and
- how you can write your code to robustly handle errors in Deferred
  code.




.. _core-howto-defer-deferreds:








Deferreds
---------



Twisted uses the :api:`twisted.internet.defer.Deferred <Deferred>` object to manage the callback
sequence. The client application attaches a series of functions to the
deferred to be called in order when the results of the asynchronous request are
available (this series of functions is known as a series of **callbacks** , or a **callback chain** ), together
with a series of functions to be called if there is an error in the
asynchronous request (known as a series of **errbacks** or an**errback chain** ). The asynchronous library code calls the first
callback when the result is available, or the first errback when an error
occurs, and the ``Deferred`` object then hands the results of each
callback or errback function to the next function in the chain. 





Callbacks
---------



A :api:`twisted.internet.defer.Deferred <twisted.internet.defer.Deferred>` is a promise that
a function will at some point have a result.  We can attach callback functions
to a Deferred, and once it gets a result these callbacks will be called. In
addition Deferreds allow the developer to register a callback for an error,
with the default behavior of logging the error.  The deferred mechanism 
standardizes the application programmer's interface with all sorts of 
blocking or delayed operations.

.. code-block:: python


    from twisted.internet import reactor, defer

    def getDummyData(inputData):
        """
        This function is a dummy which simulates a delayed result and
        returns a Deferred which will fire with that result. Don't try too
        hard to understand this.
        """
        print('getDummyData called')
        deferred = defer.Deferred()
        # simulate a delayed result by asking the reactor to fire the
        # Deferred in 2 seconds time with the result inputData * 3
        reactor.callLater(2, deferred.callback, inputData * 3)
        return deferred

    def cbPrintData(result):
        """
        Data handling function to be added as a callback: handles the
        data by printing the result
        """
        print('Result received: {}'.format(result))

    deferred = getDummyData(3)
    deferred.addCallback(cbPrintData)

    # manually set up the end of the process by asking the reactor to
    # stop itself in 4 seconds time
    reactor.callLater(4, reactor.stop)
    # start up the Twisted reactor (event loop handler) manually
    print('Starting the reactor')
    reactor.run()


Multiple callbacks
~~~~~~~~~~~~~~~~~~



Multiple callbacks can be added to a Deferred.  The first callback in the
Deferred's callback chain will be called with the result, the second with the
result of the first callback, and so on. Why do we need this?  Well, consider
a Deferred returned by twisted.enterprise.adbapi - the result of a SQL query.
A web widget might add a callback that converts this result into HTML, and
pass the Deferred onwards, where the callback will be used by twisted to
return the result to the HTTP client. The callback chain will be bypassed in
case of errors or exceptions.

.. code-block:: python

    
    from twisted.internet import reactor, defer
    
    class Getter:
        def gotResults(self, x):
            """
            The Deferred mechanism provides a mechanism to signal error
            conditions.  In this case, odd numbers are bad.

            This function demonstrates a more complex way of starting
            the callback chain by checking for expected results and
            choosing whether to fire the callback or errback chain
            """
            if self.d is None:
                print("Nowhere to put results")
                return

            d = self.d
            self.d = None
            if x % 2 == 0:
                d.callback(x*3)
            else:
                d.errback(ValueError("You used an odd number!"))

        def _toHTML(self, r):
            """
            This function converts r to HTML.

            It is added to the callback chain by getDummyData in
            order to demonstrate how a callback passes its own result
            to the next callback
            """
            return "Result: %s" % r

        def getDummyData(self, x):
            """
            The Deferred mechanism allows for chained callbacks.
            In this example, the output of gotResults is first
            passed through _toHTML on its way to printData.

            Again this function is a dummy, simulating a delayed result
            using callLater, rather than using a real asynchronous
            setup.
            """
            self.d = defer.Deferred()
            # simulate a delayed result by asking the reactor to schedule
            # gotResults in 2 seconds time
            reactor.callLater(2, self.gotResults, x)
            self.d.addCallback(self._toHTML)
            return self.d

    def cbPrintData(result):
        print(result)

    def ebPrintError(failure):
        import sys
        sys.stderr.write(str(failure))

    # this series of callbacks and errbacks will print an error message
    g = Getter()
    d = g.getDummyData(3)
    d.addCallback(cbPrintData)
    d.addErrback(ebPrintError)

    # this series of callbacks and errbacks will print "Result: 12"
    g = Getter()
    d = g.getDummyData(4)
    d.addCallback(cbPrintData)
    d.addErrback(ebPrintError)

    reactor.callLater(4, reactor.stop)
    reactor.run()

.. note::
   Pay particular attention to the handling of
     ``self.d``  in the ``gotResults``  method.  Before the
     ``Deferred``  is fired with a result or an error, the attribute is
     set to ``None``  so that the ``Getter``  instance no longer
     has a reference to the ``Deferred``  about to be fired.  This has
     several benefits.  First, it avoids any chance ``Getter.gotResults`` 
     will accidentally fire the same ``Deferred``  more than once (which
     would result in an ``AlreadyCalledError``  exception).  Second, it
     allows a callback on that ``Deferred``  to call
     ``Getter.getDummyData``  (which sets a new value for the
     ``d``  attribute) without causing problems.  Third, it makes the
     Python garbage collector's job easier by eliminating a reference cycle.


Visual Explanation
~~~~~~~~~~~~~~~~~~

.. image:: ../img/deferred-attach.png

#. Requesting method (data sink) requests data, gets
   Deferred object.
#. Requesting method attaches callbacks to Deferred
   object.

.. image:: ../img/deferred-process.png 

#. When the result is ready, give it to the Deferred
   object. ``.callback(result)`` if the operation succeeded,
   ``.errback(failure)`` if it failed. Note that
   ``failure`` is typically an instance of a :api:`twisted.python.failure.Failure <twisted.python.failure.Failure>` 
   instance.
#. Deferred object triggers previously-added (call/err)back
   with the ``result`` or ``failure`` .
   Execution then follows the following rules, going down the
   chain of callbacks to be processed. 
   
   
   
   
   - Result of the callback is always passed as the first
     argument to the next callback, creating a chain of
     processors.
   - If a callback raises an exception, switch to
     errback.
   - An unhandled failure gets passed down the line of
     errbacks, this creating an asynchronous analog to a
     series to a series of ``except:`` 
     statements.
   - If an errback doesn't raise an exception or return a
     :api:`twisted.python.failure.Failure <twisted.python.failure.Failure>` 
     instance, switch to callback.
   
   







Errbacks
--------



Deferred's error handling is modeled after Python's
exception handling. In the case that no errors occur, all the
callbacks run, one after the other, as described above.




If the errback is called instead of the callback (e.g.  because a DB query
raised an error), then a :api:`twisted.python.failure.Failure <twisted.python.failure.Failure>` is passed into the first
errback (you can add multiple errbacks, just like with callbacks). You can
think of your errbacks as being like ``except`` blocks
of ordinary Python code.




Unless you explicitly ``raise`` an error in an except
block, the ``Exception`` is caught and stops
propagating, and normal execution continues. The same thing happens with
errbacks: unless you explicitly ``return`` a ``Failure`` or (re-)raise an exception, the error stops
propagating, and normal callbacks continue executing from that point (using the
value returned from the errback). If the errback does return a ``Failure`` or raise an exception, then that is passed to the
next errback, and so on.




*Note:* If an errback doesn't return anything, then it effectively
returns ``None`` , meaning that callbacks will continue
to be executed after this errback.  This may not be what you expect to happen,
so be careful. Make sure your errbacks return a ``Failure`` (probably the one that was passed to it), or a
meaningful return value for the next callback.




Also, :api:`twisted.python.failure.Failure <twisted.python.failure.Failure>` instances have
a useful method called trap, allowing you to effectively do the equivalent
of:





.. code-block:: python

    
    try:
        # code that may throw an exception
        cookSpamAndEggs()
    except (SpamException, EggException):
        # Handle SpamExceptions and EggExceptions
        ...




You do this by:




.. code-block:: python

    
    def errorHandler(failure):
        failure.trap(SpamException, EggException)
        # Handle SpamExceptions and EggExceptions
    
    d.addCallback(cookSpamAndEggs)
    d.addErrback(errorHandler)




If none of arguments passed to ``failure.trap`` 
match the error encapsulated in that ``Failure`` , then
it re-raises the error.




There's another potential "gotcha" here.  There's a
method :api:`twisted.internet.defer.Deferred.addCallbacks <twisted.internet.defer.Deferred.addCallbacks>` 
which is similar to, but not exactly the same as, ``addCallback`` followed by ``addErrback`` . In particular, consider these two cases:





.. code-block:: python

    
    # Case 1
    d = getDeferredFromSomewhere()
    d.addCallback(callback1)       # A
    d.addErrback(errback1)         # B
    d.addCallback(callback2)       
    d.addErrback(errback2)        
    
    # Case 2
    d = getDeferredFromSomewhere()
    d.addCallbacks(callback1, errback1)  # C
    d.addCallbacks(callback2, errback2)  




If an error occurs in ``callback1`` , then for Case 1 ``errback1`` will be called with the failure. For Case
2, ``errback2`` will be called. Be careful with your
callbacks and errbacks.




What this means in a practical sense is in Case 1, the callback in line
A will handle a success condition from ``getDeferredFromSomewhere`` ,
and the errback in line B will handle any errors that occur *from either the upstream source, or that occur in A* .  In Case 2, the errback in line C  *will  only handle an error condition raised by* ``getDeferredFromSomewhere`` , 
it will not do any handling of errors
raised in ``callback1`` .






Unhandled Errors
~~~~~~~~~~~~~~~~



If a Deferred is garbage-collected with an unhandled error (i.e. it would
call the next errback if there was one), then Twisted will write the error's
traceback to the log file.  This means that you can typically get away with not
adding errbacks and still get errors logged.  Be careful though; if you keep a
reference to the Deferred around, preventing it from being garbage-collected,
then you may never see the error (and your callbacks will mysteriously seem to
have never been called).  If unsure, you should explicitly add an errback after
your callbacks, even if all you do is:





.. code-block:: python

    
    # Make sure errors get logged
    from twisted.python import log
    d.addErrback(log.err)





Handling either synchronous or asynchronous results
---------------------------------------------------



In some applications, there are functions that might be either asynchronous or
synchronous. For example, a user authentication function might be able to
check in memory whether a user is authenticated, allowing the authentication
function to return an immediate result, or it may need to wait on
network data, in which case it should return a Deferred to be fired
when that data arrives. However, a function that wants to check if a user is
authenticated will then need to accept both immediate results *and* 
Deferreds.

In this example, the library function ``authenticateUser`` uses the application function ``isValidUser`` to authenticate a user:

.. code-block:: python

    def authenticateUser(isValidUser, user):
        if isValidUser(user):
            print("User is authenticated")
        else:
            print("User is not authenticated")

However, it assumes that ``isValidUser`` returns immediately,
whereas ``isValidUser`` may actually authenticate the user
asynchronously and return a Deferred. It is possible to adapt this
trivial user authentication code to accept either a
synchronous ``isValidUser`` or an
asynchronous ``isValidUser`` , allowing the library to handle
either type of function. It is, however, also possible to adapt
synchronous functions to return Deferreds. This section describes both
alternatives: handling functions that might be synchronous or
asynchronous in the library function (``authenticateUser`` )
or in the application code.





Handling possible Deferreds in the library code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~




Here is an example of a synchronous user authentication function that might be
passed to ``authenticateUser`` :





:download:`synch-validation.py <listings/deferred/synch-validation.py>`

.. literalinclude:: listings/deferred/synch-validation.py



However, here's an ``asynchronousIsValidUser`` function that returns
a Deferred:





.. code-block:: python

    
    from twisted.internet import reactor, defer
    
    def asynchronousIsValidUser(user):
        d = defer.Deferred()
        reactor.callLater(2, d.callback, user in ["Alice", "Angus", "Agnes"])
        return d




Our original implementation of ``authenticateUser`` expected  ``isValidUser`` to be synchronous, but now we need to change it to handle both
synchronous and asynchronous implementations of ``isValidUser`` . For this, we
use :api:`twisted.internet.defer.maybeDeferred <maybeDeferred>` to
call ``isValidUser`` , ensuring that the result of ``isValidUser`` is a Deferred,
even if ``isValidUser`` is a synchronous function:

.. code-block:: python

    from twisted.internet import defer
    
    def printResult(result):
        if result:
            print("User is authenticated")
        else:
            print("User is not authenticated")

    def authenticateUser(isValidUser, user):
        d = defer.maybeDeferred(isValidUser, user)
        d.addCallback(printResult)

Now ``isValidUser`` could be either ``synchronousIsValidUser`` or ``asynchronousIsValidUser`` .

It is also possible to modify ``synchronousIsValidUser`` to return a Deferred, see :doc:`Generating Deferreds <gendefer>` for more information.


Cancellation
------------




Motivation
~~~~~~~~~~



A Deferred may take any amount of time to be called back; in fact, it may
never be called back.  Your users may not be that patient.  Since all actions
taken when the Deferred completes are in your application or library's callback
code, you always have the option of simply disregarding the result when you
receive it, if it's been too long.  However, while you're ignoring it, the
underlying operation represented by that Deferred is still chugging along in the
background, possibly consuming resources such as CPU time, memory, network
bandwidth and maybe even disk space.  So, when the user has closed the window,
hit the cancel button, disconnected from your server or sent a "stop" network
message, you will want to announce your indifference to the result of that
operation so that the originator of the Deferred can clean everything up and
free those resources to be put to better use.




Cancellation for Applications which Consume Deferreds
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



Here's a simple example.  You're connecting to an external host with an :doc:`endpoint <endpoints>` , but that host is really slow.  You want to
put a "cancel" button into your application to terminate the connection attempt,
so the user can try connecting to a different host instead.  Here's a simple
sketch of such an application, with the actual user interface left as an
exercise for the reader:





.. code-block:: python

    
    def startConnecting(someEndpoint):
        def connected(it):
            "Do something useful when connected."
        return someEndpoint.connect(myFactory).addCallback(connected)
    # ...
    connectionAttempt = startConnecting(endpoint)
    def cancelClicked():
        connectionAttempt.cancel()




Obviously (I hope), startConnecting is meant to be called by some UI element
that lets the user choose what host to connect to and then constructs an
appropriate endpoint (perhaps using ``twisted.internet.endpoints.clientFromString`` ).  Then, a cancel
button, or similar, is hooked up to the ``cancelClicked`` .




When ``connectionAttempt.cancel`` is invoked, that will:




#. cause the underlying connection operation to be terminated, if it is still ongoing
#. cause the connectionAttempt Deferred to be completed, one way or another, in a timely manner
#. *likely* cause the connectionAttempt Deferred to be errbacked with :api:`CancelledError <CancelledError>` 



You may notice that that set of consequences is very heavily qualified.
Although cancellation indicates the calling API's *desire* for the
underlying operation to be stopped, the underlying operation cannot necessarily
react immediately.  Even in this very simple example, there is already one thing
that might not be interruptible: platform-native name resolution blocks, and
therefore needs to be executed in a thread; the connection operation can't be
cancelled if it's stuck waiting for a name to be resolved in this manner.  So,
the Deferred that you are cancelling may not callback or errback right away.




A Deferred may wait upon another Deferred at any point in its callback chain
(see "Handling...asynchronous results", above).  There's no way for a particular
point in the callback chain to know if everything is finished.  Since multiple
layers of the callback chain may wish to cancel the same Deferred, any layer may
call ``.cancel()`` at any time. The ``.cancel()`` method never
raises any exception or returns any value; you may call it repeatedly, even on a
Deferred which has already fired, or which has no remaining callbacks.




The main reason for all these qualifications, aside from specific examples,
is that anyone who instantiates a Deferred may supply it with a cancellation
function; that function can do absolutely anything that it wants to.  Ideally,
anything it does will be in the service of stopping the operation your
requested, but there's no way to guarantee any exact behavior across all
Deferreds that might be cancelled. Cancellation of Deferreds is best effort. This may be the case for a number of
reasons:




#. The ``Deferred`` doesn't know how to cancel the underlying
   operation.
#. The underlying operation may have reached an uncancellable state,
   because some irreversible operation has been done.
#. The ``Deferred`` may already have a result, and so there's
   nothing to cancel.



Calling ``cancel()`` will always succeed without an error
regardless of whether or not cancellation was possible. In cases 1 and 2 the ``Deferred`` may well errback with a ``twisted.internet.defer.CancelledError`` while the underlying
operation continues. ``Deferred`` s that support cancellation should
document what they do when cancelled, if they are uncancellable in certain edge
cases, etc..




If the cancelled ``Deferred`` is waiting on another ``Deferred`` , the cancellation will be forwarded to the other ``Deferred`` .





Default Cancellation Behavior
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~




All Deferreds support cancellation.
However, by default, they support a very rudimentary form of cancellation which doesn't free any resources.




Consider this example of a Deferred which is ignorant of cancellation:




.. code-block:: python

    
    operation = Deferred()
    def x(result):
        print("Hooray, a result:" + repr(x))
    operation.addCallback(x)
    # ...
    def operationDone():
        operation.callback("completed")




A caller of an API that receives ``operation`` may call ``cancel`` on it.  Since ``operation`` does not have a
cancellation function, one of two things will happen.





#. If ``operationDone`` has been called, and the operation has
   completed, nothing much will change.  ``operation`` will still have a
   result, and there are no more callbacks, so there's no observable change in
   behavior.
#. If ``operationDone`` has *not* yet been invoked, then ``operation`` will be immediately errbacked with a ``CancelledError`` .
   
   However, once it's cancelled, there's no way to tell ``operationDone`` 
   not to run; it will eventually call ``operation.callback`` later.  In
   normal operation, issuing ``callback`` on a ``Deferred`` that
   has already called back results in an ``AlreadyCalledError`` , and this
   would cause an ugly traceback that could not be caught.  Therefore, ``.callback`` can be invoked exactly once, causing a no-op, on a ``Deferred`` which has been cancelled but has no canceller.  If you
   call it multiple times, you will still get an ``AlreadyCalledError`` 
   exception.




Creating Cancellable Deferreds: Custom Cancellation Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



Let's imagine you are implementing an HTTP client, which returns a Deferred
firing with the response from the server. Cancellation is best achieved by
closing the connection. In order to make cancellation do that, all you have to
do is pass a function to the constructor of the Deferred (it will get called
with the Deferred that is being cancelled):




.. code-block:: python

    
    class HTTPClient(Protocol):
        def request(self, method, path):
            self.resultDeferred = Deferred(
                lambda ignore: self.transport.abortConnection())
            request = b"%s %s HTTP/1.0\r\n\r\n" % (method, path)
            self.transport.write(request)
            return self.resultDeferred
    
        def dataReceived(self, data):
            # ... parse HTTP response ...
            # ... eventually call self.resultDeferred.callback() ...



Now if someone calls ``cancel()`` on the ``Deferred`` 
returned from ``HTTPClient.request()`` , the HTTP request will be
cancelled (assuming it's not too late to do so). Care should be taken not to ``callback()`` a Deferred that has already been cancelled.



.. _core-howto-defer-deferredlist:








DeferredList
------------



Sometimes you want to be notified after several different events have all
happened, rather than waiting for each one individually.  For example, you may
want to wait for all the connections in a list to close.  :api:`twisted.internet.defer.DeferredList <twisted.internet.defer.DeferredList>` is the way to do
this.




To create a DeferredList from multiple Deferreds, you simply pass a list of
the Deferreds you want it to wait for:




.. code-block:: python

    
    # Creates a DeferredList
    dl = defer.DeferredList([deferred1, deferred2, deferred3])




You can now treat the DeferredList like an ordinary Deferred; you can call  ``addCallbacks`` and so on.  The DeferredList will call its callback
when all the deferreds have completed.  The callback will be called with a list
of the results of the Deferreds it contains, like so:

.. code-block:: python

    # A callback that unpacks and prints the results of a DeferredList
    def printResult(result):
        for (success, value) in result:
            if success:
                print('Success:', value)
            else:
                print('Failure:', value.getErrorMessage())

    # Create three deferreds.
    deferred1 = defer.Deferred()
    deferred2 = defer.Deferred()
    deferred3 = defer.Deferred()
    
    # Pack them into a DeferredList
    dl = defer.DeferredList([deferred1, deferred2, deferred3], consumeErrors=True)
    
    # Add our callback
    dl.addCallback(printResult)
    
    # Fire our three deferreds with various values.
    deferred1.callback('one')
    deferred2.errback(Exception('bang!'))
    deferred3.callback('three')
    
    # At this point, dl will fire its callback, printing:
    #    Success: one
    #    Failure: bang!
    #    Success: three
    # (note that defer.SUCCESS == True, and defer.FAILURE == False)

A standard DeferredList will never call errback, but failures in Deferreds
passed to a DeferredList will still errback unless ``consumeErrors`` 
is passed ``True`` .  See below for more details about this and other
flags which modify the behavior of DeferredList.



.. note::
   
   
   If you want to apply callbacks to the individual Deferreds that
   go into the DeferredList, you should be careful about when those callbacks
   are added. The act of adding a Deferred to a DeferredList inserts a callback
   into that Deferred (when that callback is run, it checks to see if the
   DeferredList has been completed yet). The important thing to remember is
   that it is *this callback* which records the value that goes into the
   result list handed to the DeferredList's callback.
   
   
   
   
   
   ..  TODO: add picture here: three columns of callback chains, with a value   being snarfed out of the middle of each and handed off to the DeferredList
   
   
   Therefore, if you add a callback to the Deferred *after* adding the
   Deferred to the DeferredList, the value returned by that callback will not
   be given to the DeferredList's callback.  To avoid confusion, we recommend not
   adding callbacks to a Deferred once it has been used in a DeferredList.

.. code-block:: python

    def printResult(result):
        print(result)

    def addTen(result):
        return result + " ten"

    # Deferred gets callback before DeferredList is created
    deferred1 = defer.Deferred()
    deferred2 = defer.Deferred()
    deferred1.addCallback(addTen)
    dl = defer.DeferredList([deferred1, deferred2])
    dl.addCallback(printResult)
    deferred1.callback("one") # fires addTen, checks DeferredList, stores "one ten"
    deferred2.callback("two")
    # At this point, dl will fire its callback, printing:
    #     [(1, 'one ten'), (1, 'two')]

    # Deferred gets callback after DeferredList is created
    deferred1 = defer.Deferred()
    deferred2 = defer.Deferred()
    dl = defer.DeferredList([deferred1, deferred2])
    deferred1.addCallback(addTen) # will run *after* DeferredList gets its value
    dl.addCallback(printResult)
    deferred1.callback("one") # checks DeferredList, stores "one", fires addTen
    deferred2.callback("two")
    # At this point, dl will fire its callback, printing:
    #     [(1, 'one), (1, 'two')]


Other behaviours
~~~~~~~~~~~~~~~~



DeferredList accepts three keyword arguments that modify its behaviour:``fireOnOneCallback`` , ``fireOnOneErrback`` and ``consumeErrors`` .  If ``fireOnOneCallback`` is set, the
DeferredList will immediately call its callback as soon as any of its Deferreds
call their callback.  Similarly, ``fireOnOneErrback`` will call errback
as soon as any of the Deferreds call their errback.  Note that DeferredList is
still one-shot, like ordinary Deferreds, so after a callback or errback has been
called the DeferredList will do nothing further (it will just silently ignore
any other results from its Deferreds).




The ``fireOnOneErrback`` option is particularly useful when you
want to wait for all the results if everything succeeds, but also want to know
immediately if something fails.




The ``consumeErrors`` argument will stop the DeferredList from
propagating any errors along the callback chains of any Deferreds it contains
(usually creating a DeferredList has no effect on the results passed along the
callbacks and errbacks of their Deferreds).  Stopping errors at the DeferredList
with this option will prevent "Unhandled error in Deferred" warnings from
the Deferreds it contains without needing to add extra errbacks [#]_ .  Passing a true value
for the ``consumeErrors`` parameter will not change the behavior of ``fireOnOneCallback`` or ``fireOnOneErrback`` .





gatherResults
~~~~~~~~~~~~~



A common use for DeferredList is to "join" a number of parallel asynchronous
operations, finishing successfully if all of the operations were successful, or
failing if any one of the operations fails.  In this case, :api:`twisted.internet.defer.gatherResults <twisted.internet.defer.gatherResults>` is a useful
shortcut:

.. code-block:: python

    from twisted.internet import defer
    d1 = defer.Deferred()
    d2 = defer.Deferred()
    d = defer.gatherResults([d1, d2], consumeErrors=True)

    def cbPrintResult(result):
        print(result)

    d.addCallback(cbPrintResult)

    d1.callback("one")
    # nothing is printed yet; d is still awaiting completion of d2
    d2.callback("two")
    # printResult prints ["one", "two"]

The ``consumeErrors`` argument has the same meaning as it does
for :ref:`NEEDS A TITLE <core-howto-defer-deferredlist>` : if true, it causes ``gatherResults`` to consume any errors in the passed-in Deferreds.
Always use this argument unless you are adding further callbacks or errbacks to
the passed-in Deferreds, or unless you know that they will not fail.
Otherwise, a failure will result in an unhandled error being logged by Twisted.
This argument is available since Twisted 11.1.0.



.. _core-howto-defer-class:









Class Overview
--------------



This is an overview API reference for Deferred from the point of using a
Deferred returned by a function. It is not meant to be a
substitute for the docstrings in the Deferred class, but can provide guidelines
for its use.




There is a parallel overview of functions used by the Deferred's  *creator* in :ref:`Generating Deferreds <core-howto-gendefer-class>` .





Basic Callback Functions
~~~~~~~~~~~~~~~~~~~~~~~~





- 
  ``addCallbacks(self, callback[, errback, callbackArgs, callbackKeywords, errbackArgs, errbackKeywords])`` 
  
  
  This is the method you will use to interact
  with Deferred. It adds a pair of callbacks "parallel" to
  each other (see diagram above) in the list of callbacks
  made when the Deferred is called back to. The signature of
  a method added using addCallbacks should be
  ``myMethod(result, *methodArgs, **methodKeywords)`` . If your method is passed in the
  callback slot, for example, all arguments in the tuple
  ``callbackArgs`` will be passed as
  ``*methodArgs`` to your method.
  
  
  
  
  There are various convenience methods that are
  derivative of addCallbacks. I will not cover them in detail
  here, but it is important to know about them in order to
  create concise code.
  
  
  
  
  
  
  - 
    ``addCallback(callback, *callbackArgs, **callbackKeywords)`` 
  
  
    Adds your callback at the next point in the
    processing chain, while adding an errback that will
    re-raise its first argument, not affecting further
    processing in the error case.
  
  
  
  
    Note that, while addCallbacks (plural) requires the arguments to be
    passed in a tuple, addCallback (singular) takes all its remaining
    arguments as things to be passed to the callback function. The reason is
    obvious: addCallbacks (plural) cannot tell whether the arguments are
    meant for the callback or the errback, so they must be specifically
    marked by putting them into a tuple. addCallback (singular) knows that
    everything is destined to go to the callback, so it can use Python's
    "*" and "**" syntax to collect the remaining arguments.
  
  
  
  - 
    ``addErrback(errback, *errbackArgs, **errbackKeywords)`` 
  
  
    Adds your errback at the next point in the
    processing chain, while adding a callback that will
    return its first argument, not affecting further
    processing in the success case.
  
  
  - 
    ``addBoth(callbackOrErrback, *callbackOrErrbackArgs, **callbackOrErrbackKeywords)`` 
  
  
    This method adds the same callback into both sides
    of the processing chain at both points. Keep in mind
    that the type of the first argument is indeterminate if
    you use this method! Use it for ``finally:`` 
    style blocks.
  
  
  
  







Chaining Deferreds
~~~~~~~~~~~~~~~~~~



If you need one Deferred to wait on another, all you need to do is return a
Deferred from a method added to addCallbacks.  Specifically, if you return
Deferred B from a method added to Deferred A using A.addCallbacks, Deferred A's
processing chain will stop until Deferred B's .callback() method is called; at
that point, the next callback in A will be passed the result of the last
callback in Deferred B's processing chain at the time.



.. note::
   If a Deferred is somehow returned from its *own* 
   callbacks (directly or indirectly), the behavior is undefined. The Deferred
   code will make an attempt to detect this situation and produce a warning. In
   the future, this will become an exception.




If this seems confusing, don't worry about it right now -- when you run into
a situation where you need this behavior, you will probably recognize it
immediately and realize why this happens.  If you want to chain deferreds
manually, there is also a convenience method to help you.






- 
  ``chainDeferred(otherDeferred)`` 
  
  
  Add ``otherDeferred`` to the end of this
  Deferred's processing chain. When self.callback is called,
  the result of my processing chain up to this point will be
  passed to ``otherDeferred.callback`` . Further
  additions to my callback chain do not affect
  ``otherDeferred`` 
  
  
  
  This is the same as ``self.addCallbacks(otherDeferred.callback, otherDeferred.errback)`` 
  
  

    




See also
--------




#. :doc:`Generating Deferreds <gendefer>` , an introduction to
   writing asynchronous functions that return Deferreds.




.. rubric:: Footnotes

.. [#] Unless of course a later callback starts a fresh error —
       but as we've already noted, adding callbacks to a Deferred after its used in a
       DeferredList is confusing and usually avoided.
