import slides

class Lecture(slides.Lecture):

    def getHeader(self):
        header = slides.Lecture.getHeader(self)
        header += '<div align="right"><img src="smalltwisted.png" /></div><hr />'
        return header

    def getFooter(self):
        footer = slides.Lecture.getFooter(self)
        footer = '<hr /><a href="http://twistedmatrix.com"><img src="twistedlogo.png" /><br />Twisted '\
                 'Presentation</a>'+footer
        return footer
