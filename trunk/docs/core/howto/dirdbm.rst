
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

DirDBM: Directory-based Storage
===============================






dirdbm.DirDBM
-------------



:api:`twisted.persisted.dirdbm.DirDBM <twisted.persisted.dirdbm.DirDBM>` is a DBM-like storage system. 
That is, it stores mappings between keys
and values, like a Python dictionary, except that it stores the values in files
in a directory - each entry is a different file. The keys must always be strings,
as are the values. Other than that, :api:`twisted.persisted.dirdbm.DirDBM <DirDBM>` 
objects act just like Python dictionaries.




:api:`twisted.persisted.dirdbm.DirDBM <DirDBM>` is useful for cases
when you want to store small amounts of data in an organized fashion, without having
to deal with the complexity of a RDBMS or other sophisticated database. It is simple,
easy to use, cross-platform, and doesn't require any external C libraries, unlike
Python's built-in DBM modules.





.. code-block:: pycon

    
    >>> from twisted.persisted import dirdbm
    >>> d = dirdbm.DirDBM("/tmp/dir")
    >>> d["librarian"] = "ook"
    >>> d["librarian"]        
    'ook'
    >>> d.keys()
    ['librarian']
    >>> del d["librarian"]
    >>> d.items()
    []





dirdbm.Shelf
------------



Sometimes it is neccessary to persist more complicated objects than strings.
With some care, :api:`twisted.persisted.dirdbm.Shelf <dirdbm.Shelf>` 
can transparently persist
them. ``Shelf`` works exactly like ``DirDBM`` , except that
the values (but not the keys) can be arbitrary picklable objects. However,
notice that mutating an object after it has been stored in the  ``Shelf`` has no effect on the Shelf.
When mutating objects, it is neccessary to explicitly store them back in the ``Shelf``
afterwards:





.. code-block:: pycon

    
    >>> from twisted.persisted import dirdbm
    >>> d = dirdbm.Shelf("/tmp/dir2")
    >>> d["key"] = [1, 2]
    >>> d["key"]
    [1, 2]
    >>> l = d["key"]
    >>> l.append(3)
    >>> d["key"]
    [1, 2]
    >>> d["key"] = l
    >>> d["key"]
    [1, 2, 3]







  
