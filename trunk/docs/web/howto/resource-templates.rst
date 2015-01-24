
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Light Weight Templating With Resource Templates
===============================================






Overview
--------



While high-level templating systems can be used with Twisted (for
example, `DivmodNevow <https://launchpad.net/nevow>`_ , sometimes one needs a less file-heavy system which lets one
directly write HTML. While :api:`twisted.web.script.ResourceScript <ResourceScript>` is
available, it has a high coding overhead, and requires some boring string
arithmetic. :api:`twisted.web.script.ResourceTemplate <ResourceTemplate>` fills the
space between Nevow and ResourceScript using Quixote's PTL (Python Templating
Language).




ResourceTemplates need Quixote
installed. In `Debian <http://www.debian.org>`_ , that means
installing the ``python-quixote`` package
(``apt-get install python-quixote`` ). Other operating systems
require other ways to install Quixote, or it can be done manually.





Configuring Twisted Web
-----------------------



The easiest way to get Twisted Web to support ResourceTemplates is to
bind them to some extension using the web tap's ``--processor`` 
flag. Here is an example:





::

    
    % twistd web --path=/var/www \
            --processor=.rtl=twisted.web.script.ResourceTemplate




The above command line binds the ``rtl`` extension to use the 
ResourceTemplate processor. Other ways are possible, but would require
more Python coding and are outside the scope of this HOWTO.





Using ResourceTemplate
----------------------



ResourceTemplates are coded in an extension of Python called the"Python Templating Language" . Complete documentation of the PTL
is available
at `the quixote web site <http://quixote.python.ca/quixote.dev/doc/PTL.html>`_ . The web server will expect the PTL source file
to define a variable named ``resource`` .  This should be
a :api:`twisted.web.resource.Resource <twisted.web.resource.Resource>` ,
whose ``.render`` method be called. Usually, you would want
to define ``render`` using the keyword ``template`` 
rather than ``def`` .




Here is a simple example for a resource template.





:download:`webquote.rtl <listings/webquote.rtl>`

.. literalinclude:: listings/webquote.rtl
   :language: py3

