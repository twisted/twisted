#!/usr/bin/python -u

# this version of py2html carelessly modified by Glyph Lefkowitz
# if it breaks, you can keep both pieces

""" Python Highlighter                                    Version: 0.7

    py2html.py [options] files...

    options:
     -h             print help
     -              read from stdin, write to stdout
     -stdout        read from files, write to stdout
     -files         read from files, write to filename+'.html' (default)
     -format:
       html         output XHTML page (default)
       rawhtml      output pure XHTML (without headers, titles, etc.)
     -mode:
       color        output in color (default)
       mono         output b/w (for printing)
     -title:Title   use 'Title' as title of the generated page
     -bgcolor:color use color as background-color for page
     -header:file   use contents of file as header
     -footer:file   use contents of file as footer
     -URL           replace all occurances of 'URL: link' with
                    '<a href="link">link</a>'; this is always enabled
                    in CGI mode
     -v             verbose

    Takes the input, assuming it is Python code and formats it into
    colored XHTML. When called without parameters the script tries to
    work in CGI mode. It looks for a field 'script=URL' and tries to
    use that URL as input file. If it can't find this field, the path
    info (the part of the URL following the CGI script name) is
    tried. In case no host is given, the host where the CGI script
    lives and HTTP are used.
 
    * Uses Just van Rossum's PyFontify version 0.3 to tag Python scripts.
      You can get it via his homepage on starship:
        URL: http://starship.python.net/crew/just
"""
__comments__ = """

    The following snippet is a small shell script I use for viewing
    Python scripts per less on Unix:
#!/bin/sh
# Browse pretty printed Python code using ANSI codes for highlighting
py2html -stdout -format:ansi -mode:mono $* | less -r

    History:
        
    0.7: Added patch by Ville Skyttä to make py2html.py output
         valid XHTML.
    0.6: Fixed a bug in .escape_html(); thanks to Vespe Savikko for
         finding this one.
    0.5: Added a few suggestions by Kevin Ng to make the CGI version
         a little more robust.

"""
__copyright__ = """\
    Copyright (c) 1998-2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2002, eGenix.com Software GmbH; mailto:info@egenix.com
    Distributed under the terms and conditions of the eGenix.com Public
    License. See http://www.egenix.com/files/python/mxLicense.html for 
    details, or contact the author. All Rights Reserved.\
"""

__version__ = '0.7'

__cgifooter__ = ('\n<pre># code highlighted using <a href='
                 '"http://www.lemburg.com/files/python/">py2html.py</a> '
                 'version %s</pre>\n' % __version__)

import sys,string,re

# Adjust path so that PyFontify is found...
sys.path.append('.')

### Constants

# URL of the input form the user is redirected to in case no script=xxx
# form field is given. The URL *must* be absolute. Leave blank to
# have the script issue an error instead.
INPUT_FORM = 'http://www.lemburg.com/files/python/SoftwareDescriptions.html#py2html.py'

# HTML DOCTYPE and XML namespace
HTML_DOCTYPE = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">'
HTML_XMLNS = ' xmlns="http://www.w3.org/1999/xhtml"'

### Helpers

def fileio(file, mode='rb', data=None, close=0):

    if type(file) == type(''):
        f = open(file,mode)
        close = 1
    else:
        f = file
    if data:
        f.write(data)
    else:
        data = f.read()
    if close: f.close()
    return data

### Converter class

class PrettyPrint:

    """ generic Pretty Printer class

        * supports tagging Python scripts in the following ways: 

          # format/mode |  color  mono
          # --------------------------
          # rawhtml     |    x     x   (HTML without headers, etc.)
          # html        |    x     x   (a HTML page with HEAD&BODY:)
          # ansi        |    x     x   (with Ansi-escape sequences)

        * interfaces:

           file_filter -- takes two files: input & output (may be stdin/stdout)
           filter -- takes a string and returns the highlighted version
        
        * to create an instance use:

          c = PrettyPrint(tagfct,format,mode)

          where format and mode must be strings according to the
          above table if you plan to use PyFontify.fontify as
          tagfct

        * the tagfct has to take one argument, text, and return a taglist
          (format: [(id,left,right,sublist),...], where id is the
          "name" given to the slice left:right in text and sublist is a
          taglist for tags inside the slice or None)

    """

    # misc settings
    title = ''
    bgcolor = '#FFFFFF'
    header = ''
    footer = ''
    replace_URLs = 0
    # formats to be used
    formats = {}

    def __init__(self,tagfct=None,format='html',mode='color'):

        self.tag = tagfct
        self.set_mode = getattr(self,'set_mode_'+format+'_'+mode)
        self.filter = getattr(self,'filter_'+format)
        self.set_mode()

    def file_filter(self,infile,outfile):

        text = fileio(infile,'r')
        if type(infile) == type('') and self.title == '':
            self.title = infile
        fileio(outfile,'w',self.filter(text))

    ### set pre- and postfixes for formats & modes
    #
    # These methods must set self.formats to a dictionary having
    # an entry for every tag returned by the tagging function.
    #
    # The format used is simple:
    #  tag:(prefix,postfix)
    # where prefix and postfix are either strings or callable objects,
    # that return a string (they are called with the matching tag text
    # as only parameter). prefix is inserted in front of the tag, postfix
    # is inserted right after the tag.

    def set_mode_html_color(self):

        self.formats = {
            'all':('<pre>','</pre>'),
            'comment':('<span style="color: #1111CC">','</span>'),
            'keyword':('<span style="color: #3333CC"><b>','</b></span>'),
            'parameter':('<span style="color: #000066">','</span>'),
            'identifier':( lambda x,strip=string.strip:
                           '<a name="%s"><span style="color: #CC0000"><b>' % (strip(x)),
                           '</b></span></a>'),
            'string':('<span style="color: #115511">','</span>')
            }

    def set_mode_rawhtml_color(self):
        # this is where most of the modifications went...
        # --glyph
        self.formats = {
            'all':('<pre class="python">','</pre>'),
            'comment':('<span class="py-src-comment">','</span>'),
            'keyword':('<span class="py-src-keyword">','</span>'),
            'parameter':('<span class="py-src-parameter">','</span>'),
            'identifier':( lambda x,strip=string.strip:
                           '<a name="%s"><span class="py-src-identifier">'
                           % (strip(x)),
                           '</span></a>'),
            'string':('<span class="py-src-string">','</span>')
            }

    def set_mode_html_mono(self):

        self.formats = {
            'all':('<pre>','</pre>'),
            'comment':('',''),
            'keyword':( '<span style="text-decoration: underline">','</span>'),
            'parameter':('',''),
            'identifier':( lambda x,strip=string.strip:
                           '<a name="%s"><b>' % (strip(x)),
                           '</b></a>'),
            'string':('','')
            }

    set_mode_rawhtml_mono = set_mode_html_mono

    def set_mode_ansi_mono(self):

        self.formats = {
            'all':('',''),
            'comment':('\033[2m','\033[m'),
            'keyword':('\033[4m','\033[m'),
            'parameter':('',''),
            'identifier':('\033[1m','\033[m'),
            'string':('','')
            }

    def set_mode_ansi_color(self):

        self.formats = {
            'all':('',''),
            'comment':('\033[34;2m','\033[m'),
            'keyword':('\033[1;34m','\033[m'),
            'parameter':('',''),
            'identifier':('\033[1;31m','\033[m'),
            'string':('\033[32;2m','\033[m')
            }

    ### filter for Python scripts given as string

    def escape_html(self,text):

        t = (('&','&amp;'),('<','&lt;'),('>','&gt;'))
        for x,y in t:
            text = string.join(string.split(text,x),y)
        return text

    def filter_html(self,text):

        output = self.fontify(self.escape_html(text))
        if self.replace_URLs: 
            output = re.sub('URL:([ \t]+)([^ \n\r<]+)',
                            'URL:\\1<a href="\\2">\\2</a>',output)
        html = """%s<html%s><head><title>%s</title></head>
                  <body style="background-color: %s">
                  <!--header-->
                  %s
                  <!--script-->
                  %s
                  <!--footer-->
                  %s
                  </body></html>\n"""%(HTML_DOCTYPE,HTML_XMLNS,self.title,self.bgcolor,self.header,output,self.footer)
        return html

    def filter_rawhtml(self,text):

        output = self.fontify(self.escape_html(text))
        if self.replace_URLs: 
            output = re.sub('URL:([ \t]+)([^ \n\r<]+)',
                            'URL:\\1<a href="\\2">\\2</a>',output)
        return self.header+output+self.footer

    def filter_ansi(self,text):

        output = self.fontify(text)
        return self.header+output+self.footer

    ### fontify engine

    def fontify(self,pytext):

        # parse
        taglist = self.tag(pytext)

        # prepend special 'all' tag:
        taglist[:0] = [('all',0,len(pytext),None)]

        # prepare splitting
        splits = []
        addsplits(splits,pytext,self.formats,taglist)

        # do splitting & inserting
        splits.sort()
        l = []
        li = 0
        for ri,dummy,insert in splits:
            if ri > li: l.append(pytext[li:ri])
            l.append(insert)
            li = ri
        if li < len(pytext): l.append(pytext[li:])
        
        return string.join(l,'')

def addsplits(splits,text,formats,taglist):
    # helper for fontify()
    for id,left,right,sublist in taglist:
        try:
            pre,post = formats[id]
        except KeyError:
            # sys.stderr.write('Warning: no format for %s specified\n'%repr(id))
            pre,post = '',''
        if type(pre) != type(''):
            pre = pre(text[left:right])
        if type(post) != type(''):
            post = post(text[left:right])
        # len(splits) is a dummy used to make sorting stable
        splits.append((left,len(splits),pre))
        if sublist:
            addsplits(splits,text,formats,sublist)
        splits.append((right,len(splits),post))

def write_html_error(titel,text):

    print """\
%s<html%s><head><title>%s</title></head>
<body>
<h2>%s</h2>
%s
</body></html>
""" % (HTML_DOCTYPE,HTML_XMLNS,titel,titel,text)

def redirect_to(url):

    sys.stdout.write('Content-Type: text/html\r\n')
    sys.stdout.write('Status: 302\r\n')
    sys.stdout.write('Location: %s\r\n\r\n' % url)
    print """
%s<html%s><head>
<title>302 Moved Temporarily</title>
</head><body>
<h1>302 Moved Temporarily</h1>
The document has moved to <a href="%s">%s</a>.<p></p>
</body></html>
""" % (HTML_DOCTYPE,HTML_XMLNS,url,url)

def main(cmdline):

    """ main(cmdline) -- process cmdline as if it were sys.argv 
    """
    # parse options/files
    options = []
    optvalues = {}
    for o in cmdline[1:]:
        if o[0] == '-':
            if ':' in o:
                k,v = tuple(string.split(o,':'))
                optvalues[k] = v
                options.append(k)
            else:
                options.append(o)
        else:
            break
    files = cmdline[len(options)+1:]

    # create converting object  

    # load fontifier
    if '-marcs' in options:
        # use mxTextTool's tagging engine
        from mxTextTools import tag
        from mxTextTools.Examples.Python import python_script
        tagfct = lambda text,tag=tag,pytable=python_script: \
                 tag(text,pytable)[1]
        print "Py2HTML: using Marc's tagging engine"
    else:
        # load Just's
        try:
            import PyFontify
            if PyFontify.__version__ < '0.3': raise ValueError
            tagfct = PyFontify.fontify
        except:
            print """
    Sorry, but this script needs the PyFontify.py module version 0.3;
    You can download it from Just's homepage at

       URL: http://starship.python.net/crew/just
"""
            sys.exit()
        

    if '-format' in options:
        format = optvalues['-format']
    else:
        # use default
        format = 'html'

    if '-mode' in options:
        mode = optvalues['-mode']
    else:
        # use default
        mode = 'color'

    c = PrettyPrint(tagfct,format,mode)
    convert = c.file_filter

    # start working

    if '-title' in options:
        c.title = optvalues['-title']

    if '-bgcolor' in options:
        c.bgcolor = optvalues['-bgcolor']

    if '-header' in options:
        try:
            f = open(optvalues['-header'])
            c.header = f.read()
            f.close()
        except IOError:
            if verbose: print 'IOError: header file not found'
            
    if '-footer' in options:
        try:
            f = open(optvalues['-footer'])
            c.footer = f.read()
            f.close()
        except IOError:
            if verbose: print 'IOError: footer file not found'

    if '-URL' in options:
        c.replace_URLs = 1

    if '-' in options:
        convert(sys.stdin,sys.stdout)
        sys.exit()

    if '-h' in options:
        print __doc__
        sys.exit()

    if len(files) == 0:
        # Turn URL processing on
        c.replace_URLs = 1
        # Try CGI processing...
        import cgi,urllib,urlparse,os
        form = cgi.FieldStorage()
        if not form.has_key('script'):
            # Ok, then try pathinfo
            if not os.environ.has_key('PATH_INFO'):
                if INPUT_FORM:
                    redirect_to(INPUT_FORM)
                else:
                    sys.stdout.write('Content-Type: text/html\r\n\r\n')
                    write_html_error('Missing Parameter',
                                     'Missing script=URL field in request')
                sys.exit(1)
            url = os.environ['PATH_INFO'][1:] # skip the leading slash
        else:
            url = form['script'].value
        sys.stdout.write('Content-Type: text/html\r\n\r\n')
        scheme, host, path, params, query, frag = urlparse.urlparse(url)
        if not host:
            scheme = 'http'
            if os.environ.has_key('HTTP_HOST'):
                host = os.environ['HTTP_HOST']
            else:
                host = 'localhost'
            url = urlparse.urlunparse((scheme, host, path, params, query, frag))
        #print url; sys.exit()
        network = urllib.URLopener()
        try:
            tempfile,headers = network.retrieve(url)
        except IOError,reason:
            write_html_error('Error opening "%s"' % url,
                             'The given URL could not be opened. Reason: %s' %\
                             str(reason))
            sys.exit(1)
        f = open(tempfile,'rb')
        c.title = url
        c.footer = __cgifooter__
        convert(f,sys.stdout)
        f.close()
        network.close()
        sys.exit()

    if '-stdout' in options:
        filebreak = '-'*72
        for f in files:
            try:
                if len(files) > 1:
                    print filebreak
                    print 'File:',f
                    print filebreak
                convert(f,sys.stdout)
            except IOError:
                pass
    else:
        verbose = ('-v' in options)
        if verbose:
            print 'Py2HTML: working on',
        for f in files:
            try:
                if verbose: print f,
                convert(f,f+'.html')
            except IOError:
                if verbose: print '(IOError!)',
        if verbose:
            print
            print 'Done.'

if __name__=='__main__':
    main(sys.argv)


