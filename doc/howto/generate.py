# The Simplest Thing that could Possibly Work, part two. 
# Yeah. It's inefficient. But hey, it's only run at "compile"-time.

import os, time, sgmllib, re, string, sys, cgi, cStringIO

import sgmlfilter


cssclassmap =  {'services': 'serv-text',
                'documents': 'doc-text',
                'developers': 'dev-text',
                'products': 'prod-text'}
 

class TemplateFilter(sgmlfilter.SGMLFilter):
    def __init__(self, file):
        self.io = cStringIO.StringIO()
        self.titleMode = 1
        self.title = []
        sgmlfilter.SGMLFilter.__init__(self, self.io, file)

    def handle_data(self, data):
        if self.titleMode:
            self.title.append(data)
        sgmlfilter.SGMLFilter.handle_data(self, data)
    
    def start(self, tag, attrs):
        if tag == 'title':
            self.titleMode = 1
        if tag == 'a':
            #If it's a relative link, we have to replace '.html' with ''.
            for i in range(len(attrs)):
                attr = attrs[i]
                if attr[0] == 'href':
                    if ((not attr[1].find(":") >= 0) and
                    (not attr[1].startswith('..')) and
                    (not attr[1].startswith('/'))):
                        print "relative!", attrs,
                        attrs[i] = ('href', attr[1].replace('.html', ''))
                        print "returning", attrs
        return tag, attrs

    def end(self, tag):
        self.titleMode = 0
        #print "end",tag
        if tag == 'title':
            self.title = string.join(self.title, "")
            #print "got title", self.title
        return tag

    def get_title(self):
        assert type(self.title) is not type([]), "Hmm. Something's wrong with the <title> of this document."
        return self.title

class Walker:
    def __init__(self, templ):
        self.shwackBeginning = re.compile('.*<body>', re.MULTILINE | re.I)
        self.shwackEnd = re.compile('</body>.*', re.MULTILINE | re.I)
        self.templ = templ

    def walk(self, ig, d, names):
        linkrel = '../' * d.count('/')
        for name in names:
            fname, fext = os.path.splitext(os.path.join(d, name))

            # begin .htc processing
            if fext == '.html':
                print fname + fext
                inFile = open(fname+fext)
                filt = TemplateFilter(inFile)
                title = filt.get_title()
                data = filt.io.getvalue()
                data = self.shwackBeginning.sub('', data)
                data = self.shwackEnd.sub('', data)
                outFile = open(fname,'wb')
                p = d.split('/')
                cssclass = (len(p) > 1 and cssclassmap.get(p[1])) or 'content'
                #perform translations and interpolations
                data = (self.templ
                        .replace('@@',linkrel)
                        .replace(',@title', title)
                        .replace(',@class', cssclass)
                        .replace(',@content', data)
                        .replace(',@hhmts', time.ctime(os.path.getmtime(fname+fext))))
                outFile.write(data)
                
                outFile.flush()
                outFile.close()

def main():
    if len(sys.argv) > 1:
        templ = open(sys.argv[1]).read()
    else:
        templ = open('template.html').read()

    os.path.walk('.', Walker(templ).walk, None)

if __name__=='__main__': main()
