from twisted.trial import unittest
from twisted.python import win32



class QuotingTests(unittest.TestCase):
    def test_cmdLineQuote(self):
        """
        Quoting a single string results in cmd.exe-style quoting.
        """
        self.assertEquals(
            win32.cmdLineQuote('hello'),
            'hello')

        self.assertEquals(
            win32.cmdLineQuote('"'),
            '"\\""')

        for ch in ' \t|':
            self.assertEquals(
                win32.cmdLineQuote(ch),
                '"%s"' % (ch,))

        self.assertEquals(
            win32.cmdLineQuote(r'"\\"hello\\"'),
            '"\\"\\\\\\\\\\"hello\\\\\\\\\\""')

        self.assertEquals(
            win32.cmdLineQuote(r'"foo\ bar baz\""'),
            '"\\"foo\\ bar baz\\\\\\"\\""')


    def test_quoteArguments(self):
        """
        Quoting an iterable of arguments results in a single string delimited
        by single-spaces of quoted arguments.
        """
        args = ['meep', '"hello"', 'foo|bar', r'"\\"hello\\"']
        quotedArgs = win32.quoteArguments(args).split(' ')
        self.assertEquals(len(args), len(quotedArgs))
        for original, quoted in zip(args, quotedArgs):
            self.assertEquals(win32.cmdLineQuote(original), quoted)
