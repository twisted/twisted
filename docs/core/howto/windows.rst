:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Developing Twisted on Windows
=============================

Overview
--------

Getting your development environment setup on Windows is fairly straight forward once you have the right packages installed. At the end of this guide, you should have the source for twisted downloaded be able to run the unittests on your box.
This was tested on Windows 7, but should work on any version where you can get the needed packages.

What you need
-------------

#. Python 2.7 for Windows https://www.python.org/downloads/
#. Visual C++ express 2008 http://go.microsoft.com/?linkid=7729279
#. pywin32 http://sourceforge.net/projects/pywin32/
#. pip https://pip.pypa.io/en/latest/installing.html
#. pyopenssl (availiable via pip)
#. pycrpyto (availiable via pip)
#. service_identity (availiable via pip)

Install Python and Visual Studio
--------------------------------

Installing these packages is mostly a clicking next operation. You can download them from the links above.
Microsoft changes their links sometimes, so you may need to Google for the download.

Install pywin32
---------------

From the download page for pywin32, there are several options for which package to install. The latest build should be fine, but the package you install has to match the version and architecture of your installed python interpreter. To see what you have you can start python and look at the first couple lines. They should look something like this::

    Python 2.7.7 (default, Jun  1 2014, 14:17:13) [MSC v.1500 32 bit (Intel)] on win32

You're interested in the Python 2.7.7 part which means you need 27 and the 32 bit just before the (Intel) means you want win32. If you have 64 bit there, you'll want the amd64 version.

The installer will find your Python interpreter and install the addon.

Install everything else
-----------------------

Pip is an easy way to get the rest of your dependencies, and it will also install setuptools which you need to install twisted. If you follow the above link, you will get to the install guide for pip on Windows. At this time, you download the get-pip.py file and run it with python, and it should install pip.

The pip installer will put an executable in the Scripts directory of your interpreter, probably c:\python27\Scripts. To run these commands you can add that directory to your path environment variable, or specify the full path::

    PATH=%PATH%;c:\python27\scripts
    pip install pyopenssl
    pip install pycrypto
    pip install service_identity

Get the twisted source and build
--------------------------------

You can get the twisted source just like you do on linux, as long as you have the right version control tool installed for windows. get it and then go to the root directory for your checkout.

Then issue this command::

    python setup.py develop

This will build twisted for Windows using Visual Studio and install any other dependencies you need.

Try out the tests
-----------------

If the above worked, you should be ready to run the tests. Testing in Twisted is done with the trial tool. This tool is in the bin subdirectory of the source tree. It is called twisted with no extension, but it's actually a python file. To run the entire suite, run this from the bin subdirectory::

    python trial twisted

This should run the tests. All of them except 10 or 20 should pass. There should also be a couple thousand that are skipped.

You're ready to go
------------------

If your tests run, you should be ready to start contributing to twisted!

References
----------

* cyli's blog post http://blog.ying.li/2012/03/twisted-development-on-windows-v2.html
* Pip install guide https://pip.pypa.io/en/latest/installing.html
