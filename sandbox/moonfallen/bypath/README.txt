________________

ByPath
________________

Modify and transform XML documents using Python code and XPath expressions.

Each .byp file defines a transformation for an XML document.  Each block in
the .byp is either the keyword "node" followed by an xpath expression, which
selects nodes from a document, or the keyword "python".  Inside each block is
Python code.

Each "python" block is executed once as it is encountered, and code there
runs in the global namespace for that .byp file.  Each "node" block is
executed once for each node that the xpath expression matches.  In these
blocks the 'node' and 'document' magical variables are available, which are
DOM nodes, so you can create children for them, delete them, etc.


Installation
------------
You need pyxml 0.8.3 installed.  The only module in this package is bypath.py.


Usage
-----
python bypath.py <byp-file> <xml-file>


TODO
----
A simpler generation/deletion/mutation API than DOM would be highly desirable.


Examples
--------
See tests/ directory.
