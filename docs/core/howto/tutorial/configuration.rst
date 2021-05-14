
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: configuration of the finger service
============================================================






Introduction
------------



This is the eleventh part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




In this part, we make it easier for non-programmers to configure a finger server.
Plugins are discussed further in the :doc:`Twisted Plugin System <../plugin>` howto.
Writing twistd plugins is covered in :doc:`Writing a twistd Plugin <../tap>`, and .tac applications are covered in :doc:`Using the Twisted Application Framework <../application>`.





Plugins
-------



So far, the user had to be somewhat of a programmer to be able to configure
stuff. Maybe we can eliminate even that? Move old code
to ``finger/__init__.py`` and...




Full source code for finger module here:

:download:`finger.py <listings/finger/finger/finger.py>`

.. literalinclude:: listings/finger/finger/finger.py







:download:`tap.py <listings/finger/finger/tap.py>`

.. literalinclude:: listings/finger/finger/tap.py


And register it all:





:download:`finger_tutorial.py <listings/finger/twisted/plugins/finger_tutorial.py>`

.. literalinclude:: listings/finger/twisted/plugins/finger_tutorial.py


Note that the second argument to :py:class:`ServiceMaker <twisted.application.service.ServiceMaker>` ,``finger.tap`` , is a reference to a module
(``finger/tap.py`` ), not to a filename.




And now, the following works





.. code-block:: console


    % sudo twistd -n finger --file=/etc/users --ircnick=fingerbot





For more details about this, see the :doc:`twistd plugin documentation <../tap>` .
