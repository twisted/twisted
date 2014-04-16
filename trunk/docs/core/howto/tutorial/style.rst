
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: cleaning up the finger code
====================================================






Introduction
------------



This is the third part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




In this section of the tutorial, we'll clean up our code so that it is
closer to a readable and extensible style.





Write Readable Code
-------------------



The last version of the application had a lot of hacks. We avoided
sub-classing, didn't support things like user listings over the web, 
and removed all blank lines -- all in the interest of code
which is shorter. Here we take a step back, subclass what is more
naturally a subclass, make things which should take multiple lines
take them, etc. This shows a much better style of developing Twisted
applications, though the hacks in the previous stages are sometimes
used in throw-away prototypes.





:download:`finger18.tac <listings/finger/finger18.tac>`

.. literalinclude:: listings/finger/finger18.tac

