class CoverageTracker:

    def __init__(self, modules):
        self.checked = {}
        for m in modules:
            fn = __import__(m).__file__
            if fn.endswith('.pyc'):
                fn = fn[:-1]
            self.checked[fn] = {}

    def __call__(self, frame, event, arg):
        if event in ['call', 'line']:
            if frame.f_code.co_filename in self.checked.keys():
                self.checked[frame.f_code.co_filename][frame.f_lineno] = 1
        return self

    def start(self):
        import sys
        sys.settrace(self)

    def finish(self):
        import sys
        sys.settrace(None)
        cov = []
        for fn in self.checked.keys():
            cov.append(Coverage(fn, self.checked[fn].keys()))
        return cov

class Coverage:
    def __init__(self, filename, checked):
        self.filename = filename
        f = open(filename, 'r')
        self.checkedLines = []
        self.uncheckedLines = []
        self.fileLines = 0
        lineno = 0
        for l in f.xreadlines():
            lineno += 1
            ls = l.strip()
            if ls != '' and ls[0] != '#':
                # functional line
                self.fileLines += 1
                if lineno in checked:
                    self.checkedLines.append(lineno)
                else:
                    self.uncheckedLines.append(lineno)

    def __repr__(self):
        return """Coverage of file %s:
Number of Checked Lines: %i
Number of Unchecked Lines: %i
Percentage of file covered: %2f""" % (self.filename, len(self.checkedLines),
                                    len(self.uncheckedLines),
                                    100 * len(self.checkedLines) / self.fileLines)

ct = CoverageTracker(['coverage_tester'])
import sys
import coverage_tester
ct.start()
coverage_tester.test()
print ct.finish()
