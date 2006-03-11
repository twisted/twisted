## FIXME: put this config in a better place
apidocRoot = "http://twistedmatrix.com/documents/current/api/"
apidocDefaultPackage = "twisted.web2"

import os
from StringIO import StringIO


from docutils.parsers import rst
from docutils import nodes, utils, io

from txt2html import error
try:
    from twisted.python import htmlizer
except ImportError:
    error("Error during import: twisted.python.htmlizer is required", 99)

def python(name, arguments, options, content, lineno,
           content_offset, block_text, state, state_machine):
    inp = StringIO('\n'.join(content))
    outp = StringIO()
    htmlizer.filter(inp, outp, writer=htmlizer.SmallerHTMLWriter)
    html = outp.getvalue()
    return [nodes.raw('', html, format='html')]
python.content = 1

def pythonfile(name, arguments, options, content, lineno,
               content_offset, block_text, state, state_machine):
    fname = arguments[0]
    source_dir = os.path.dirname(
        os.path.abspath(state.document.current_source))
    path = os.path.normpath(os.path.join(source_dir, arguments[0]))
    path = utils.relative_path(None, path)
    state.document.settings.record_dependencies.add(path)
    encoding = options.get('encoding', state.document.settings.input_encoding)
    raw_file = io.FileInput(
        source_path=path, encoding=encoding,
        error_handler=state.document.settings.input_encoding_error_handler,
        handle_io_errors=None)
    content = raw_file.read()
    formatted_code = python(name, None, None, [content], None, None, None, None, None)
    return formatted_code

pythonfile.arguments = (1, 0, 1)
rst.directives.register_directive('python', python)
rst.directives.register_directive('pythonfile', pythonfile)

def apidoc_reference_role(role, rawtext, text, lineno, inliner,
                          options={}, content=[]):
    refuri = "%s%s.html" % (apidocRoot, text)
    node = nodes.reference(rawtext, text, refuri=refuri, **options)
    return [node], []

def pkgapidoc_reference_role(role, rawtext, text, lineno, inliner,
                          options={}, content=[]):
    if text:
        ref = apidocDefaultPackage + "." + text
    else:
        ref = apidocDefaultPackage
    refuri = "%s%s.html" % (apidocRoot, ref)
    node = nodes.reference(rawtext, text, refuri=refuri, **options)
    return [node], []


rst.roles.register_canonical_role('apidoc', apidoc_reference_role)
rst.roles.register_canonical_role('pkgapidoc', pkgapidoc_reference_role)
