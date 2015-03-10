
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: making a finger library
================================================






Introduction
------------



This is the tenth part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




In this part, we separate the application code that launches a finger service
from the library code which defines a finger service, placing the application in
a Twisted Application Configuration (.tac) file. We also move configuration
(such as HTML templates) into separate files. Configuration and deployment with
.tac and twistd are introduced in :doc:`Using the Twisted Application Framework <../application>` .





Organization
------------



Now this code, while quite modular and well-designed, isn't
properly organized. Everything above the ``application=`` belongs in a
module, and the HTML templates all belong in separate files.




We can use the ``templateFile`` and ``templateDirectory`` 
attributes to indicate what HTML template file to use for each Page, and where
to look for it.





:download:`organized-finger.tac <listings/finger/organized-finger.tac>`

.. literalinclude:: listings/finger/organized-finger.tac



Note that our program is now quite separated. We have:


- Code (in the module)
- Configuration (file above)
- Presentation (templates)
- Content (``/etc/users`` )
- Deployment (twistd)


Prototypes don't need this level of separation, so our earlier examples all
bunched together. However, real applications do. Thankfully, if we write our
code correctly, it is easy to achieve a good separation of parts.








Easy Configuration
------------------

We can also supply easy configuration for common cases with a ``makeService`` method that will also help build .tap files later:


:download:`finger_config.py <listings/finger/finger_config.py>`

.. literalinclude:: listings/finger/finger_config.py


And we can write simpler files now:


:download:`simple-finger.tac <listings/finger/simple-finger.tac>`

.. literalinclude:: listings/finger/simple-finger.tac

.. code-block:: console

    
    % twistd -ny simple-finger.tac


Note: the finger *user* still has ultimate power: they can use ``makeService``, or they can use the lower-level interface if they have specific needs (maybe an IRC server on some other port? Maybe we want the non-SSL webserver to listen only locally? etc. etc.).
This is an important design principle: never *force* a layer of abstraction; *allow* usage of layers of abstractions instead.

The pasta theory of design:

Spaghetti
   Each piece of code interacts with every other piece of code (can be implemented with GOTO, functions, objects).
Lasagna
   Code has carefully designed layers.
   Each layer is, in theory independent.
   However low-level layers usually cannot be used easily, and high-level layers depend on low-level layers.
Ravioli
   Each part of the code is useful by itself.
   There is a thin layer of interfaces between various parts (the sauce).
   Each part can be usefully be used elsewhere.

...but sometimes, the user just wants to order "Ravioli", so one coarse-grain easily definable layer of abstraction on top of it all can be useful.
