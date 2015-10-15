
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: pluggable backends
===========================================






Introduction
------------



This is the fifth part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




In this part we will add new several new backends to our finger service using
the component-based architecture developed in :doc:`The Evolution of Finger: moving to a component based architecture <components>` . This will
show just how convenient it is to implement new back-ends when we move to a
component based architecture. Note that here we also use an interface we
previously wrote, ``FingerSetterFactory`` , by supporting one single
method. We manage to preserve the service's ignorance of the network.





Another Back-end
----------------




:download:`finger19b_changes.py <listings/finger/finger19b_changes.py>`

.. literalinclude:: listings/finger/finger19b_changes.py



Full source code here: 

:download:`finger19b.tac <listings/finger/finger19b.tac>`

.. literalinclude:: listings/finger/finger19b.tac






We've already written this, but now we get more for less work:
the network code is completely separate from the back-end.






Yet Another Back-end: Doing the Standard Thing
----------------------------------------------




:download:`finger19c_changes.py <listings/finger/finger19c_changes.py>`

.. literalinclude:: listings/finger/finger19c_changes.py



Full source code here: 

:download:`finger19c.tac <listings/finger/finger19c.tac>`

.. literalinclude:: listings/finger/finger19c.tac






Not much to say except that now we can be churn out backends like crazy. Feel
like doing a back-end for `Advogato <http://www.advogato.org/>`_ , for
example? Dig out the XML-RPC client support Twisted has, and get to work!



