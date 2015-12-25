
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Scheduling tasks for the future
===============================





Let's say we want to run a task X seconds in the future.
The way to do that is defined in the reactor interface :api:`twisted.internet.interfaces.IReactorTime <twisted.internet.interfaces.IReactorTime>` :




.. code-block:: python

    
    from twisted.internet import reactor
    
    def f(s):
        print "this will run 3.5 seconds after it was scheduled: %s" % s
    
    reactor.callLater(3.5, f, "hello, world")
    
    # f() will only be called if the event loop is started.
    reactor.run()



    
If the result of the function is important or if it may be necessary
to handle exceptions it raises, then the :api:`twisted.internet.task.deferLater <twisted.internet.task.deferLater>` utility conveniently
takes care of creating a :api:`twisted.internet.defer.Deferred <Deferred>` and setting up a delayed
call:




.. code-block:: python

    from twisted.internet import task
    from twisted.internet import reactor

    def f(s):
        return "This will run 3.5 seconds after it was scheduled: %s" % s

    d = task.deferLater(reactor, 3.5, f, "hello, world")
    def called(result):
        print result
    d.addCallback(called)

    # f() will only be called if the event loop is started.
    reactor.run()

If we want a task to run every X seconds repeatedly, we can use :api:`twisted.internet.task.LoopingCall <twisted.internet.task.LoopingCall>`:

.. code-block:: python

    from twisted.internet import task
    from twisted.internet import reactor

    loopTimes = 3
    failInTheEnd = False
    _loopCounter = 0

    def runEverySecond():
        """
        Called at ever loop interval.
        """
        global _loopCounter

        if _loopCounter < loopTimes:
            _loopCounter += 1
            print 'A new second has passed.'
            return

        if failInTheEnd:
            raise Exception('Failure during loop execution.')

        # We looped enough times.
        loop.stop()
        return


    def cbLoopDone(result):
        """
        Called when loop was stopped with success.
        """
        print "Loop done."
        reactor.stop()


    def ebLoopFailed(failure):
        """
        Called when loop execution failed.
        """
        print failure.getBriefTraceback()
        reactor.stop()


    loop = task.LoopingCall(runEverySecond)

    # Start looping every 1 second.
    loopDeferred = loop.start(1.0)

    # Add callbacks for stop and failure.
    loopDeferred.addCallback(cbLoopDone)
    loopDeferred.addErrback(ebLoopFailed)

    reactor.run()

If we want to cancel a task that we've scheduled:

.. code-block:: python

    from twisted.internet import reactor

    def f():
        print "I'll never run."

    callID = reactor.callLater(5, f)
    callID.cancel()
    reactor.run()

As with all reactor-based code, in order for scheduling to work the reactor must be started using ``reactor.run()`` .
