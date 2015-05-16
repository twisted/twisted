
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Working from Twisted's Subversion repository
============================================





If you're going to be doing development on Twisted itself, or if you want
to take advantage of bleeding-edge features (or bug fixes) that are not yet
available in a numbered release, you'll probably want to check out a tree from
the Twisted Subversion repository. The Trunk is where all current development
takes place.




This document lists some useful tips for working on this cutting
edge.





Checkout
--------



Subversion tutorials can be found elsewhere, see in particular `the Subversion homepage <http://subversion.apache.org/>`_ . The
relevant data you need to check out a copy of the Twisted tree is available on
the `development page <http://twistedmatrix.com/trac/wiki/TwistedDevelopment>`_ , and is as follows:





.. code-block:: console

    
    $ svn co svn://svn.twistedmatrix.com/svn/Twisted/trunk Twisted





Alternate tree names
--------------------



By using ``svn co svn://svn.twistedmatrix.com/svn/Twisted/trunk otherdir`` , you can put the workspace tree in a directory other than "Twisted" . I do this (with a name like "Twisted-Subversion" ) to
remind myself that this tree comes from Subversion and not from a released
version (like "Twisted-1.0.5" ). This practice can cause a few problems,
because there are a few places in the Twisted tree that need to know where
the tree starts, so they can add it to ``sys.path`` without
requiring the user manually set their PYTHONPATH. These functions walk the
current directory up to the root, looking for a directory named "Twisted" (sometimes exactly that, sometimes with a ``.startswith`` test). Generally these are test scripts or other
administrative tools which expect to be launched from somewhere inside the
tree (but not necessarily from the top).




If you rename the tree to something other than ``Twisted`` , these
tools may wind up trying to use Twisted source files from /usr/lib/python2.5
or elsewhere on the default ``sys.path`` .  Normally this won't
matter, but it is good to be aware of the issue in case you run into
problems.




``twisted/test/process_twisted.py`` is one of these programs.





Combinator
----------



In order to simplify the use of Subversion, we typically use `Divmod Combinator <http://twistedmatrix.com/trac/wiki/Combinator>`_ .
You may find it to be useful, too.  In particular, because Twisted uses
branches for almost all feature development, if you plan to contribute to
Twisted you will probably find Combinator very useful.  For more details,
see the Combinator website, as well as the `UQDS <http://twistedmatrix.com/trac/wiki/UltimateQualityDevelopmentSystem>`_ page.





Compiling C extensions
----------------------




There are currently several C extension modules in Twisted: ``twisted.internet.cfsupport`` , ``twisted.internet.iocpreactor._iocp`` , 
and ``twisted.python._epoll`` .  These modules
are optional, but you'll have to compile them if you want to experience their
features, performance improvements, or bugs. There are two approaches.




The first is to do a regular distutils ``./setup.py build`` , which
will create a directory under ``build/`` to hold both the generated ``.so`` files as well as a copy of the 600-odd ``.py`` files
that make up Twisted. If you do this, you will need to set your PYTHONPATH to
something like ``MyDir/Twisted/build/lib.linux-i686-2.5`` in order to
run code against the Subversion twisted (as opposed to whatever's installed in ``/usr/lib/python2.5`` or wherever python usually looks). In
addition, you will need to re-run the ``build`` command *every time* you change a ``.py`` file. The ``build/lib.foo`` 
directory is a copy of the main tree, and that copy is only updated when you
re-run ``setup.py build`` . It is easy to forget this and then wonder
why your code changes aren't being expressed.




The second technique is to build the C modules in place, and point your
PYTHONPATH at the top of the tree, like ``MyDir/Twisted`` . This way
you're using the .py files in place too, removing the confusion a forgotten
rebuild could cause with the separate build/ directory above. To build the C
modules in place, do ``./setup.py build_ext -i`` . You only need to
re-run this command when you change the C files. Note that ``setup.py`` is not Make, it does not always get the dependencies
right (``.h`` files in particular), so if you are hacking on the
cReactor you may need to manually delete the ``.o`` files before
doing a rebuild. Also note that doing a ``setup.py clean`` will
remove the ``.o`` files but not the final ``.so`` files,
they must be deleted by hand.






Running tests
-------------



To run the full unit-test suite, do:





.. code-block:: console

    ./bin/trial twisted




To run a single test file (like ``twisted/test/test_defer.py`` ),
do one of:





.. code-block:: console

    ./bin/trial twisted.test.test_defer




or





.. code-block:: console

    ./bin/trial twisted/test/test_defer.py




To run any tests that are related to a code file, like ``twisted/protocols/imap4.py`` , do:





.. code-block:: console

    ./bin/trial --testmodule twisted/mail/imap4.py




This depends upon the ``.py`` file having an appropriate "test-case-name" tag that indicates which test cases provide coverage.
See the :doc:`Test Standards <test-standard>` document for
details about using "test-case-name" . In this example, the ``twisted.mail.test.test_imap`` test will be run.




Many tests create temporary files in /tmp or ./_trial_temp, but
everything in /tmp should be deleted when the test finishes. Sometimes these
cleanup calls are commented out by mistake, so if you see a stray ``/tmp/@12345.1`` directory, it is probably from ``test_dirdbm`` or ``test_popsicle`` .
Look for an ``rmtree`` that has been commented out and complain to
the last developer who touched that file.





Building docs
-------------

Twisted documentation (not including the automatically-generated API docs) is generated by `Sphinx <http://sphinx-doc.org/>`_ .
The docs are written in Restructured Text (``.rst``) and translated into ``.html`` files by the ``bin/admin/build-docs`` script.

To build the HTML form of the docs into the ``doc/`` directory, do the following:

.. code-block:: console

    ./bin/admin/build-docs .


Committing and Post-commit Hooks
--------------------------------



Twisted uses a customized `trac-post-commit-hook <http://bazaar.launchpad.net/~exarkun/twisted-trac-integration/trunk/annotate/head%3A/trac-hooks/trac-post-commit-hook>`_ to enable ticket updates based on svn commit
logs. When making a branch for a ticket, the branch name should end
in ``-<ticket number>`` , for
example ``my-branch-9999`` . This will add a ticket comment containing a
changeset link and branch name. To make your commit message show up as a comment
on a Trac ticket, add a ``refs #<ticket number>`` line at the
bottom of your commit message. To automatically close a ticket on Trac
as ``Fixed`` and add a comment with the closing commit message, add
a ``Fixes: #<ticket number>`` line to your commit message. In
general, a commit message closing a ticket looks like this:





::

    
    Merge my-branch-9999: A single-line summary.
    
    Author: jesstess
    Reviewers: exarkun, glyph
    Fixes: #9999
    
    My longer description of the changes made.




The :doc:`Twisted Coding Standard <coding-standard>` 
elaborates on commit messages and source control.





Emacs
-----



A minor mode for development with Twisted using Emacs is available.  See ``twisted-dev.el`` , provided by `twisted-emacs <http://launchpad.net/twisted-emacs>`_ ,
for several utility functions which make it easier to grep for methods, run test cases, etc.





Building Debian packages
------------------------



Our support for building Debian packages has fallen into disrepair.  We
would very much like to restore this functionality, but until we do so, if
you are interested in this, you are on your own.  See `stdeb <http://github.com/astraw/stdeb>`_ for one possible approach to
this.



