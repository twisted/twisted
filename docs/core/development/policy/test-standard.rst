
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Unit Tests in Twisted
=====================





Each *unit test* tests one bit of functionality in the
software.  Unit tests are entirely automated and complete quickly.
Unit tests for the entire system are gathered into one test suite,
and may all be run in a single batch.  The result of a unit test
is simple: either it passes, or it doesn't.  All this means you
can test the entire system at any time without inconvenience, and
quickly see what passes and what fails.

    



Unit Tests in the Twisted Philosophy
------------------------------------


    
The Twisted development team adheres to the practice of `Extreme Programming <http://c2.com/cgi/wiki?ExtremeProgramming>`_ (XP),
and the usage of unit tests is a cornerstone XP practice.  Unit tests are a
tool to give you increased confidence.  You changed an algorithm -- did you
break something?  Run the unit tests.  If a test fails, you know where to
look, because each test covers only a small amount of code, and you know it
has something to do with the changes you just made.  If all the tests pass,
you're good to go, and you don't need to second-guess yourself or worry that
you just accidentally broke someone else's program.

    



What to Test, What Not to Test
------------------------------


        
    
    You don't have to write a test for every single
    method you write, only production methods that could possibly break.
    
    
    
    
        
    
-- Kent Beck, Extreme Programming Explained

    



Running the Tests
-----------------


    

How
~~~


    
From the root of the Twisted source tree, run
`Trial <http://twistedmatrix.com/trac/wiki/TwistedTrial>`_ :


    



.. code-block:: console

    
    $ bin/trial twisted



    
You'll find that having something like this in your emacs init
files is quite handy:





::

    
    (defun runtests () (interactive)
      (compile "python /somepath/Twisted/bin/trial /somepath/Twisted"))
    
    (global-set-key [(alt t)] 'runtests)


    

When
~~~~


    
Always, always, *always* be sure `all the     tests pass <http://www.xprogramming.com/xpmag/expUnitTestsAt100.htm>`_ before committing any code.  If someone else
checks out code at the start of a development session and finds
failing tests, they will not be happy and may decide to *hunt you down* .

    


Since this is a geographically dispersed team, the person who can help
you get your code working probably isn't in the room with you.  You may want
to share your work in progress over the network, but you want to leave the
main Subversion tree in good working order.
So `use a branch <http://svnbook.red-bean.com/en/1.0/ch04.html>`_ ,
and merge your changes back in only after your problem is solved and all the
unit tests pass again.

    



Adding a Test
-------------


    
Please don't add new modules to Twisted without adding tests
for them too.  Otherwise we could change something which breaks
your module and not find out until later, making it hard to know
exactly what the change that broke it was, or until after a
release, and nobody wants broken code in a release.

    


Tests go into dedicated test packages such as
``twisted/test/`` or ``twisted/conch/test/`` ,
and are named ``test_foo.py`` , where ``foo`` is the name
of the module or package being tested. Extensive documentation on using
the PyUnit framework for writing unit tests can be found in the
:ref:`links section <core-development-policy-test-standard-links>` below.


    


One deviation from the standard PyUnit documentation: To ensure
that any variations in test results are due to variations in the
code or environment and not the test process itself, Twisted ships
with its own, compatible, testing framework.  That just
means that when you import the unittest module, you will ``from twisted.trial import unittest`` instead of the
standard ``import unittest`` .

    


As long as you have followed the module naming and placement
conventions, ``trial`` will be smart
enough to pick up any new tests you write.

    


PyUnit provides a large number of assertion methods to be used when
writing tests.  Many of these are redundant.  For consistency, Twisted
unit tests should use the ``assert`` forms rather than the
``fail`` forms.  Also, use ``assertEqual`` ,
``assertNotEqual`` , and ``assertAlmostEqual`` rather
than ``assertEquals`` , ``assertNotEquals`` , and
``assertAlmostEquals`` .  ``assertTrue`` is also
preferred over ``assert_`` .  You may notice this convention is
not followed everywhere in the Twisted codebase.  If you are changing
some test code and notice the wrong method being used in nearby code,
feel free to adjust it.

    


When you add a unit test, make sure all methods have docstrings
specifying at a high level the intent of the test. That is, a description
that users of the method would understand.

    



Test Implementation Guidelines
------------------------------


    
Here are some guidelines to follow when writing tests for the Twisted
test suite.  Many tests predate these guidelines and so do not follow them.
When in doubt, follow the guidelines given here, not the example of old unit
tests.

    


Naming Test Classes
~~~~~~~~~~~~~~~~~~~



When writing tests for the Twisted test suite, test classes are named
``FooTests``, where ``Foo`` is the name of the component being tested.
Here is an example:





.. code-block:: python


    class SSHClientTests(unittest.TestCase):
        def test_sshClient(self):
            foo() # the actual test





Real I/O
~~~~~~~~

Most unit tests should avoid performing real, platform-implemented I/O operations.
Real I/O is slow, unreliable, and unwieldy.

When implementing a protocol, :api:`twisted.test.proto_helpers.StringTransport` can be used instead of a real TCP transport.
``StringTransport`` is fast, deterministic, and can easily be used to exercise all possible network behaviors.

If you need pair a client to a server and have them talk to each other, use :api:`twisted.test.iosim.connect` with :api:`twisted.test.iosim.FakeTransport` transports.


Real Time
~~~~~~~~~

Most unit tests should also avoid waiting for real time to pass.
Unit tests which construct and advance a :api:`twisted.internet.task.Clock <twisted.internet.task.Clock>` are fast and deterministic.

When designing your code allow for the reactor to be injected during tests.

.. code-block:: python

    from twisted.internet.task import Clock

    def test_timeBasedFeature(self):
        """
        In this test a Clock scheduler is used.
        """
        clock = Clock()
        yourThing = SomeThing()
        yourThing._reactor = clock

        state = yourThing.getState()

        clock.advance(10)

        # Get state after 10 seconds.
        state = yourThing.getState()


Test Data
~~~~~~~~~

Keeping test data in the source tree should be avoided where possible.

In some cases it can not be avoided, but where it's obvious how to do so, do it.
Test data can be generated at run time or stored inside the test modules as constants.

When file system access is required, dumping data into a temporary path during the test run opens up more testing opportunities.
Inside the temporary path you can control various path properties or permissions.

You should design your code so that data can be read from arbitrary input streams.

Tests should be able to run even if they are run inside an installed copy of Twisted.

.. code-block:: python

    publicRSA_openssh = ("ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAGEArzJx8OYOnJmzf4tf"
    "vLi8DVPrJ3/c9k2I/Az64fxjHf9imyRJbixtQhlH9lfNjUIx+4LmrJH5QNRsFporcHDKOTwTT"
    "h5KmRpslkYHRivcJSkbh/C+BR3utDS555mV comment")

    def test_loadOpenSSHRSAPublic(self):
        """
        L{keys.Key.fromStrea} can load RSA keys serialized in OpenSSH format.
        """
        keys.Key.fromStream(StringIO(publicRSA_openssh))


The Global Reactor
~~~~~~~~~~~~~~~~~~

Since unit tests are avoiding real I/O and real time, they can usually avoid using a real reactor.
The only exceptions to this are unit tests for a real reactor implementation.
Unit tests for protocol implementations or other application code should not use a reactor.
Unit tests for real reactor implementations should not use the global reactor, but should
instead use :api:`twisted.internet.test.reactormixins.ReactorBuilder` so they can be applied to all of the reactor implementations automatically.
In no case should new unit tests use the global reactor.


Skipping Tests
--------------

Trial, the Twisted unit test framework, has some extensions which are
designed to encourage developers to add new tests. One common situation is
that a test exercises some optional functionality: maybe it depends upon
certain external libraries being available, maybe it only works on certain
operating systems. The important common factor is that nobody considers
these limitations to be a bug.




To make it easy to test as much as possible, some tests may be skipped in
certain situations. Individual test cases can raise the ``SkipTest`` exception to indicate that they should be skipped, and
the remainder of the test is not run. In the summary (the very last thing
printed, at the bottom of the test output) the test is counted as a"skip" instead of a "success" or "fail" . This should be used
inside a conditional which looks for the necessary prerequisites:





.. code-block:: python


    class SSHClientTests(unittest.TestCase):
        def test_sshClient(self):
            if not ssh_path:
                raise unittest.SkipTest("cannot find ssh, nothing to test")
            foo() # do actual test after the SkipTest




You can also set the ``.skip`` attribute on the method, with a
string to indicate why the test is being skipped. This is convenient for
temporarily turning off a test case, but it can also be set conditionally (by
manipulating the class attributes after they've been defined):





.. code-block:: python

    
    class SomeThingTests(unittest.TestCase):
        def test_thing(self):
            dotest()
        test_thing.skip = "disabled locally"





.. code-block:: python

    
    class MyTests(unittest.TestCase):
        def test_one(self):
            ...
        def test_thing(self):
            dotest()
    
    if not haveThing:
        MyTests.test_thing.im_func.skip = "cannot test without Thing"
        # but test_one() will still run




Finally, you can turn off an entire TestCase at once by setting the .skip
attribute on the class. If you organize your tests by the functionality they
depend upon, this is a convenient way to disable just the tests which cannot
be run.





.. code-block:: python

    
    class TCPTests(unittest.TestCase):
        ...
    class SSLTests(unittest.TestCase):
        if not haveSSL:
            skip = "cannot test without SSL support"
        # but TCPTests will still run
        ...


Testing New Functionality
-------------------------

Two good practices which arise from the "XP" development process are
sometimes at odds with each other:






- Unit tests are a good thing. Good developers recoil in horror when
  they see a failing unit test. They should drop everything until the test
  has been fixed.
- Good developers write the unit tests first. Once tests are done, they
  write implementation code until the unit tests pass. Then they stop.





These two goals will sometimes conflict. The unit tests that are written
first, before any implementation has been done, are certain to fail. We want
developers to commit their code frequently, for reliability and to improve
coordination between multiple people working on the same problem together.
While the code is being written, other developers (those not involved in the
new feature) should not have to pay attention to failures in the new code.
We should not dilute our well-indoctrinated Failing Test Horror Syndrome by
crying wolf when an incomplete module has not yet started passing its unit
tests. To do so would either teach the module author to put off writing or
committing their unit tests until *after* all the functionality is
working, or it would teach the other developers to ignore failing test
cases. Both are bad things.




".todo" is intended to solve this problem. When a developer first
starts writing the unit tests for functionality that has not yet been
implemented, they can set the ``.todo`` attribute on the test
methods that are expected to fail. These methods will still be run, but
their failure will not be counted the same as normal failures: they will go
into an "expected failures" category. Developers should learn to treat
this category as a second-priority queue, behind actual test failures.




As the developer implements the feature, the tests will eventually start
passing. This is surprising: after all those tests are marked as being
expected to fail. The .todo tests which nevertheless pass are put into a"unexpected success" category. The developer should remove the .todo
tag from these tests. At that point, they become normal tests, and their
failure is once again cause for immediate action by the entire development
team.




The life cycle of a test is thus:

#. Test is created, marked ``.todo`` . Test fails: "expected failure" .
#. Code is written, test starts to pass. "unexpected success" .
#. ``.todo`` tag is removed. Test passes. "success" .
#. Code is broken, test starts to fail. "failure" . Developers spring
   into action.
#. Code is fixed, test passes once more. "success" .

``.todo`` may be of use while you are developing a feature, but by the time you are ready to commit anything all the tests you have written should be passing.
In other words **never** commit to trunk tests marked as ``.todo``.
For unfinished tests you should create a follow up ticket and add the tests to the ticket's description.

You can also ignore the ``.todo`` marker and just make sure you write test first to see them failing before starting to work on the fix.


Line Coverage Information
-------------------------

Trial provides line coverage information, which is very useful to ensure
old code has decent coverage. Passing the ``--coverage`` option to Trial will generate the coverage information in a file called ``coverage`` which can be found in the ``_trial_temp`` 
folder.





Associating Test Cases With Source Files
----------------------------------------



Please add a ``test-case-name`` tag to the source file that is
covered by your new test. This is a comment at the beginning of the file
which looks like one of the following:





.. code-block:: python

    
    # -*- test-case-name: twisted.test.test_defer -*-




or





.. code-block:: python

    
    #!/usr/bin/env python
    # -*- test-case-name: twisted.test.test_defer -*-




This format is understood by emacs to mark "File Variables" . The
intention is to accept ``test-case-name`` anywhere emacs would on
the first or second line of the file (but not in the ``File Variables:`` block that emacs accepts at the end of the file). If you
need to define other emacs file variables, you can either put them in the ``File Variables:`` block or use a semicolon-separated list of
variable definitions:





.. code-block:: python

    
    # -*- test-case-name: twisted.test.test_defer; fill-column: 75; -*-




If the code is exercised by multiple test cases, those may be marked by
using a comma-separated list of tests, as follows: (NOTE: not all tools can
handle this yet.. ``trial --testmodule`` does, though)





.. code-block:: python

    
    # -*- test-case-name: twisted.test.test_defer,twisted.test.test_tcp -*-




The ``test-case-name`` tag will allow ``trial --testmodule twisted/dir/myfile.py`` to determine which test cases need
to be run to exercise the code in ``myfile.py`` . Several tools (as
well as http://launchpad.net/twisted-emacs's ``twisted-dev.el`` 's F9 command) use this to automatically
run the right tests.





Links
-----
.. _core-development-policy-test-standard-links:










- A chapter on `Unit Testing <http://www.diveintopython3.net/unit-testing.html>`_ 
  in Mark Pilgrim's `Dive Into      Python <http://www.diveintopython3.net/>`_ .
- `unittest <http://docs.python.org/library/unittest.html>`_ module documentation, in the `Python Library      Reference <http://docs.python.org/library>`_ .
- `UnitTest <http://c2.com/cgi/wiki?UnitTest>`__ on
  the `PortlandPatternRepository      Wiki <http://c2.com/cgi/wiki>`_ , where all the cool `ExtremeProgramming <http://c2.com/cgi/wiki?ExtremeProgramming>`_ kids hang out.
- `Unit      Tests <http://www.extremeprogramming.org/rules/unittests.html>`_ in `Extreme Programming: A Gentle Introduction <http://www.extremeprogramming.org>`_ .
- Ron Jeffries expounds on the importance of `Unit      Tests at 100% <http://www.xprogramming.com/xpmag/expUnitTestsAt100.htm>`_ .
- Ron Jeffries writes about the `Unit      Test <http://www.xprogramming.com/Practices/PracUnitTest.html>`_ in the `Extreme      Programming practices of C3 <http://www.xprogramming.com/Practices/xpractices.htm>`_ .
- `PyUnit's homepage <http://pyunit.sourceforge.net>`_ .
- The top-level tests directory, `twisted/test <http://twistedmatrix.com/trac/browser/trunk/twisted/test>`_ , in Subversion.


  


See also :doc:`Tips for writing tests for Twisted code <../../howto/testing>` .

  

