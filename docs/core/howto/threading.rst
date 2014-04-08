
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Using Threads in Twisted
========================

Running code in a thread-safe manner
------------------------------------

Most code in Twisted is not thread-safe.
For example, writing data to a transport from a protocol is not thread-safe.
Therefore, we want a way to schedule methods to be run in the main event loop.
This can be done using the function :api:`twisted.internet.interfaces.IReactorThreads.callFromThread <callFromThread>`::

    from twisted.internet import reactor

    def notThreadSafe(x):
         """do something that isn't thread-safe"""
         # ...

    def threadSafeScheduler():
        """Run in thread-safe manner."""
        reactor.callFromThread(notThreadSafe, 3) # will run 'notThreadSafe(3)'
                                                 # in the event loop
    reactor.run()


Running code in threads
-----------------------

Sometimes we may want to run methods in threads.
For example, in order to access blocking APIs.
Twisted provides methods for doing so using the :api:`twisted.internet.interfaces.IReactorThreads <IReactorThreads>` API.
Additional utility functions are provided in :api:`twisted.internet.threads <twisted.internet.threads>`.
Basically, these methods allow us to queue methods to be run by a thread pool.

For example, to run a method in a thread we can do::

    from twisted.internet import reactor

    def aSillyBlockingMethod(x):
        import time
        time.sleep(2)
        print x

    # run method in thread
    reactor.callInThread(aSillyBlockingMethod, "2 seconds have passed")
    reactor.run()


Utility Methods
---------------

The utility methods are not part of the :api:`twisted.internet.reactor <reactor>` APIs, but are implemented in :api:`twisted.internet.threads <threads>`.

If we have multiple methods to run sequentially within a thread, we can do::

    from twisted.internet import reactor, threads

    def aSillyBlockingMethodOne(x):
        import time
        time.sleep(2)
        print x

    def aSillyBlockingMethodTwo(x):
        print x

    # run both methods sequentially in a thread
    commands = [(aSillyBlockingMethodOne, ["Calling First"], {})]
    commands.append((aSillyBlockingMethodTwo, ["And the second"], {}))
    threads.callMultipleInThread(commands)
    reactor.run()

For functions whose results we wish to get, we can have the result returned as a Deferred::

    from twisted.internet import reactor, threads

    def doLongCalculation():
        # .... do long calculation here ...
        return 3

    def printResult(x):
        print x

    # run method in thread and get result as defer.Deferred
    d = threads.deferToThread(doLongCalculation)
    d.addCallback(printResult)
    reactor.run()

If you wish to call a method in the reactor thread and get its result, you can use :api:`twisted.internet.threads.blockingCallFromThread <blockingCallFromThread>`::

    from twisted.internet import threads, reactor, defer
    from twisted.web.client import getPage
    from twisted.web.error import Error

    def inThread():
        try:
            result = threads.blockingCallFromThread(
                reactor, getPage, "http://twistedmatrix.com/")
        except Error, exc:
            print exc
        else:
            print result
        reactor.callFromThread(reactor.stop)

    reactor.callInThread(inThread)
    reactor.run()

``blockingCallFromThread`` will return the object or raise the exception returned or raised by the function passed to it.
If the function passed to it returns a Deferred, it will return the value the Deferred is called back with or raise the exception it is errbacked with.


Managing the Thread Pool
------------------------

The thread pool is implemented by :api:`twisted.python.threadpool.ThreadPool <ThreadPool>`.

We may want to modify the size of the thread pool, increasing or decreasing the number of threads in use.
We can do this do this quite easily::

    from twisted.internet import reactor

    reactor.suggestThreadPoolSize(30)

The default size of the thread pool depends on the reactor being used; the default reactor uses a minimum size of 5 and a maximum size of 10.
Be careful that you understand threads and their resource usage before drastically altering the thread pool sizes.
