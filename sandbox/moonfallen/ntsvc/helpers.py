"""Helpers is a dict that maps module names to importHooks.
Keys are the names of modules that might be imported by an app being packaged
with ntsvc.  Values are lists of (name, list_of_attrs) tuples.  Anything in
list_of_attrs will be added as an import node.
"""
helpers = {
     'nevow': [('nevow', ['*']),
               ('nevow.flat', ['*'])],
     'formless': [('formless', ['*'])],
     }
