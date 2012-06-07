# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.protocols.irc}.
"""

import time

from twisted.trial import unittest
from twisted.trial.unittest import TestCase
from twisted.words.protocols import irc
from twisted.words.protocols.irc import IRCClient
from twisted.internet import protocol, task
from twisted.test.proto_helpers import StringTransport, StringIOWithoutClosing



class ModeParsingTests(unittest.TestCase):
    """
    Tests for L{twisted.words.protocols.irc.parseModes}.
    """
    paramModes = ('klb', 'b')


    def test_emptyModes(self):
        """
        Parsing an empty mode string raises L{irc.IRCBadModes}.
        """
        self.assertRaises(irc.IRCBadModes, irc.parseModes, '', [])


    def test_emptyModeSequence(self):
        """
        Parsing a mode string that contains an empty sequence (either a C{+} or
        C{-} followed directly by another C{+} or C{-}, or not followed by
        anything at all) raises L{irc.IRCBadModes}.
        """
        self.assertRaises(irc.IRCBadModes, irc.parseModes, '++k', [])
        self.assertRaises(irc.IRCBadModes, irc.parseModes, '-+k', [])
        self.assertRaises(irc.IRCBadModes, irc.parseModes, '+', [])
        self.assertRaises(irc.IRCBadModes, irc.parseModes, '-', [])


    def test_malformedModes(self):
        """
        Parsing a mode string that does not start with C{+} or C{-} raises
        L{irc.IRCBadModes}.
        """
        self.assertRaises(irc.IRCBadModes, irc.parseModes, 'foo', [])
        self.assertRaises(irc.IRCBadModes, irc.parseModes, '%', [])


    def test_nullModes(self):
        """
        Parsing a mode string that contains no mode characters raises
        L{irc.IRCBadModes}.
        """
        self.assertRaises(irc.IRCBadModes, irc.parseModes, '+', [])
        self.assertRaises(irc.IRCBadModes, irc.parseModes, '-', [])


    def test_singleMode(self):
        """
        Parsing a single mode setting with no parameters results in that mode,
        with no parameters, in the "added" direction and no modes in the
        "removed" direction.
        """
        added, removed = irc.parseModes('+s', [])
        self.assertEqual(added, [('s', None)])
        self.assertEqual(removed, [])

        added, removed = irc.parseModes('-s', [])
        self.assertEqual(added, [])
        self.assertEqual(removed, [('s', None)])


    def test_singleDirection(self):
        """
        Parsing a single-direction mode setting with multiple modes and no
        parameters, results in all modes falling into the same direction group.
        """
        added, removed = irc.parseModes('+stn', [])
        self.assertEqual(added, [('s', None),
                                  ('t', None),
                                  ('n', None)])
        self.assertEqual(removed, [])

        added, removed = irc.parseModes('-nt', [])
        self.assertEqual(added, [])
        self.assertEqual(removed, [('n', None),
                                    ('t', None)])


    def test_multiDirection(self):
        """
        Parsing a multi-direction mode setting with no parameters.
        """
        added, removed = irc.parseModes('+s-n+ti', [])
        self.assertEqual(added, [('s', None),
                                  ('t', None),
                                  ('i', None)])
        self.assertEqual(removed, [('n', None)])


    def test_consecutiveDirection(self):
        """
        Parsing a multi-direction mode setting containing two consecutive mode
        sequences with the same direction results in the same result as if
        there were only one mode sequence in the same direction.
        """
        added, removed = irc.parseModes('+sn+ti', [])
        self.assertEqual(added, [('s', None),
                                  ('n', None),
                                  ('t', None),
                                  ('i', None)])
        self.assertEqual(removed, [])


    def test_mismatchedParams(self):
        """
        If the number of mode parameters does not match the number of modes
        expecting parameters, L{irc.IRCBadModes} is raised.
        """
        self.assertRaises(irc.IRCBadModes,
                          irc.parseModes,
                          '+k', [],
                          self.paramModes)
        self.assertRaises(irc.IRCBadModes,
                          irc.parseModes,
                          '+kl', ['foo', '10', 'lulz_extra_param'],
                          self.paramModes)


    def test_parameters(self):
        """
        Modes which require parameters are parsed and paired with their relevant
        parameter, modes which do not require parameters do not consume any of
        the parameters.
        """
        added, removed = irc.parseModes(
            '+klbb',
            ['somekey', '42', 'nick!user@host', 'other!*@*'],
            self.paramModes)
        self.assertEqual(added, [('k', 'somekey'),
                                  ('l', '42'),
                                  ('b', 'nick!user@host'),
                                  ('b', 'other!*@*')])
        self.assertEqual(removed, [])

        added, removed = irc.parseModes(
            '-klbb',
            ['nick!user@host', 'other!*@*'],
            self.paramModes)
        self.assertEqual(added, [])
        self.assertEqual(removed, [('k', None),
                                    ('l', None),
                                    ('b', 'nick!user@host'),
                                    ('b', 'other!*@*')])

        # Mix a no-argument mode in with argument modes.
        added, removed = irc.parseModes(
            '+knbb',
            ['somekey', 'nick!user@host', 'other!*@*'],
            self.paramModes)
        self.assertEqual(added, [('k', 'somekey'),
                                  ('n', None),
                                  ('b', 'nick!user@host'),
                                  ('b', 'other!*@*')])
        self.assertEqual(removed, [])



stringSubjects = [
    "Hello, this is a nice string with no complications.",
    "xargs%(NUL)smight%(NUL)slike%(NUL)sthis" % {'NUL': irc.NUL },
    "embedded%(CR)snewline%(CR)s%(NL)sFUN%(NL)s" % {'CR': irc.CR,
                                                    'NL': irc.NL},
    "escape!%(X)s escape!%(M)s %(X)s%(X)sa %(M)s0" % {'X': irc.X_QUOTE,
                                                      'M': irc.M_QUOTE}
    ]


class QuotingTest(unittest.TestCase):
    def test_lowquoteSanity(self):
        """
        Testing client-server level quote/dequote.
        """
        for s in stringSubjects:
            self.assertEqual(s, irc.lowDequote(irc.lowQuote(s)))


    def test_ctcpquoteSanity(self):
        """
        Testing CTCP message level quote/dequote.
        """
        for s in stringSubjects:
            self.assertEqual(s, irc.ctcpDequote(irc.ctcpQuote(s)))



class Dispatcher(irc._CommandDispatcherMixin):
    """
    A dispatcher that exposes one known command and handles unknown commands.
    """
    prefix = 'disp'

    def disp_working(self, a, b):
        """
        A known command that returns its input.
        """
        return a, b


    def disp_unknown(self, name, a, b):
        """
        Handle unknown commands by returning their name and inputs.
        """
        return name, a, b



class DispatcherTests(unittest.TestCase):
    """
    Tests for L{irc._CommandDispatcherMixin}.
    """
    def test_dispatch(self):
        """
        Dispatching a command invokes the correct handler.
        """
        disp = Dispatcher()
        args = (1, 2)
        res = disp.dispatch('working', *args)
        self.assertEqual(res, args)


    def test_dispatchUnknown(self):
        """
        Dispatching an unknown command invokes the default handler.
        """
        disp = Dispatcher()
        name = 'missing'
        args = (1, 2)
        res = disp.dispatch(name, *args)
        self.assertEqual(res, (name,) + args)


    def test_dispatchMissingUnknown(self):
        """
        Dispatching an unknown command, when no default handler is present,
        results in an exception being raised.
        """
        disp = Dispatcher()
        disp.disp_unknown = None
        self.assertRaises(irc.UnhandledCommand, disp.dispatch, 'bar')



class ServerSupportedFeatureTests(unittest.TestCase):
    """
    Tests for L{ServerSupportedFeatures} and related functions.
    """
    def test_intOrDefault(self):
        """
        L{_intOrDefault} converts values to C{int} if possible, otherwise
        returns a default value.
        """
        self.assertEqual(irc._intOrDefault(None), None)
        self.assertEqual(irc._intOrDefault([]), None)
        self.assertEqual(irc._intOrDefault(''), None)
        self.assertEqual(irc._intOrDefault('hello', 5), 5)
        self.assertEqual(irc._intOrDefault('123'), 123)
        self.assertEqual(irc._intOrDefault(123), 123)


    def test_splitParam(self):
        """
        L{ServerSupportedFeatures._splitParam} splits ISUPPORT parameters
        into key and values. Parameters without a separator are split into a
        key and a list containing only the empty string. Escaped parameters
        are unescaped.
        """
        params = [('FOO',         ('FOO', [''])),
                  ('FOO=',        ('FOO', [''])),
                  ('FOO=1',       ('FOO', ['1'])),
                  ('FOO=1,2,3',   ('FOO', ['1', '2', '3'])),
                  ('FOO=A\\x20B', ('FOO', ['A B'])),
                  ('FOO=\\x5Cx',  ('FOO', ['\\x'])),
                  ('FOO=\\',      ('FOO', ['\\'])),
                  ('FOO=\\n',     ('FOO', ['\\n']))]

        _splitParam = irc.ServerSupportedFeatures._splitParam

        for param, expected in params:
            res = _splitParam(param)
            self.assertEqual(res, expected)

        self.assertRaises(ValueError, _splitParam, 'FOO=\\x')
        self.assertRaises(ValueError, _splitParam, 'FOO=\\xNN')
        self.assertRaises(ValueError, _splitParam, 'FOO=\\xN')
        self.assertRaises(ValueError, _splitParam, 'FOO=\\x20\\x')


    def test_splitParamArgs(self):
        """
        L{ServerSupportedFeatures._splitParamArgs} splits ISUPPORT parameter
        arguments into key and value.  Arguments without a separator are
        split into a key and an empty string.
        """
        res = irc.ServerSupportedFeatures._splitParamArgs(['A:1', 'B:2', 'C:', 'D'])
        self.assertEqual(res, [('A', '1'),
                                ('B', '2'),
                                ('C', ''),
                                ('D', '')])


    def test_splitParamArgsProcessor(self):
        """
        L{ServerSupportedFeatures._splitParamArgs} uses the argument processor
        passed to to convert ISUPPORT argument values to some more suitable
        form.
        """
        res = irc.ServerSupportedFeatures._splitParamArgs(['A:1', 'B:2', 'C'],
                                           irc._intOrDefault)
        self.assertEqual(res, [('A', 1),
                                ('B', 2),
                                ('C', None)])


    def test_parsePrefixParam(self):
        """
        L{ServerSupportedFeatures._parsePrefixParam} parses the ISUPPORT PREFIX
        parameter into a mapping from modes to prefix symbols, returns
        C{None} if there is no parseable prefix parameter or raises
        C{ValueError} if the prefix parameter is malformed.
        """
        _parsePrefixParam = irc.ServerSupportedFeatures._parsePrefixParam
        self.assertEqual(_parsePrefixParam(''), None)
        self.assertRaises(ValueError, _parsePrefixParam, 'hello')
        self.assertEqual(_parsePrefixParam('(ov)@+'),
                          {'o': ('@', 0),
                           'v': ('+', 1)})


    def test_parseChanModesParam(self):
        """
        L{ServerSupportedFeatures._parseChanModesParam} parses the ISUPPORT
        CHANMODES parameter into a mapping from mode categories to mode
        characters. Passing fewer than 4 parameters results in the empty string
        for the relevant categories. Passing more than 4 parameters raises
        C{ValueError}.
        """
        _parseChanModesParam = irc.ServerSupportedFeatures._parseChanModesParam
        self.assertEqual(
            _parseChanModesParam([]),
            {'addressModes': '',
             'param': '',
             'setParam': '',
             'noParam': ''})

        self.assertEqual(
            _parseChanModesParam(['b', 'k', 'l', 'imnpst']),
            {'addressModes': 'b',
             'param': 'k',
             'setParam': 'l',
             'noParam': 'imnpst'})

        self.assertEqual(
            _parseChanModesParam(['b', 'k', 'l']),
            {'addressModes': 'b',
             'param': 'k',
             'setParam': 'l',
             'noParam': ''})

        self.assertRaises(
            ValueError,
            _parseChanModesParam, ['a', 'b', 'c', 'd', 'e'])


    def test_parse(self):
        """
        L{ServerSupportedFeatures.parse} changes the internal state of the
        instance to reflect the features indicated by the parsed ISUPPORT
        parameters, including unknown parameters and unsetting previously set
        parameters.
        """
        supported = irc.ServerSupportedFeatures()
        supported.parse(['MODES=4',
                        'CHANLIMIT=#:20,&:10',
                        'INVEX',
                        'EXCEPTS=Z',
                        'UNKNOWN=A,B,C'])

        self.assertEqual(supported.getFeature('MODES'), 4)
        self.assertEqual(supported.getFeature('CHANLIMIT'),
                          [('#', 20),
                           ('&', 10)])
        self.assertEqual(supported.getFeature('INVEX'), 'I')
        self.assertEqual(supported.getFeature('EXCEPTS'), 'Z')
        self.assertEqual(supported.getFeature('UNKNOWN'), ('A', 'B', 'C'))

        self.assertTrue(supported.hasFeature('INVEX'))
        supported.parse(['-INVEX'])
        self.assertFalse(supported.hasFeature('INVEX'))
        # Unsetting a previously unset parameter should not be a problem.
        supported.parse(['-INVEX'])


    def _parse(self, features):
        """
        Parse all specified features according to the ISUPPORT specifications.

        @type features: C{list} of C{(featureName, value)}
        @param features: Feature names and values to parse

        @rtype: L{irc.ServerSupportedFeatures}
        """
        supported = irc.ServerSupportedFeatures()
        features = ['%s=%s' % (name, value or '')
                    for name, value in features]
        supported.parse(features)
        return supported


    def _parseFeature(self, name, value=None):
        """
        Parse a feature, with the given name and value, according to the
        ISUPPORT specifications and return the parsed value.
        """
        supported = self._parse([(name, value)])
        return supported.getFeature(name)


    def _testIntOrDefaultFeature(self, name, default=None):
        """
        Perform some common tests on a feature known to use L{_intOrDefault}.
        """
        self.assertEqual(
            self._parseFeature(name, None),
            default)
        self.assertEqual(
            self._parseFeature(name, 'notanint'),
            default)
        self.assertEqual(
            self._parseFeature(name, '42'),
            42)


    def _testFeatureDefault(self, name, features=None):
        """
        Features known to have default values are reported as being present by
        L{irc.ServerSupportedFeatures.hasFeature}, and their value defaults
        correctly, when they don't appear in an ISUPPORT message.
        """
        default = irc.ServerSupportedFeatures()._features[name]

        if features is None:
            features = [('DEFINITELY_NOT', 'a_feature')]

        supported = self._parse(features)
        self.assertTrue(supported.hasFeature(name))
        self.assertEqual(supported.getFeature(name), default)


    def test_support_CHANMODES(self):
        """
        The CHANMODES ISUPPORT parameter is parsed into a C{dict} giving the
        four mode categories, C{'addressModes'}, C{'param'}, C{'setParam'}, and
        C{'noParam'}.
        """
        self._testFeatureDefault('CHANMODES')
        self._testFeatureDefault('CHANMODES', [('CHANMODES', 'b,,lk,')])
        self._testFeatureDefault('CHANMODES', [('CHANMODES', 'b,,lk,ha,ha')])

        self.assertEqual(
            self._parseFeature('CHANMODES', ''),
            {'addressModes': '',
             'param': '',
             'setParam': '',
             'noParam': ''})

        self.assertEqual(
            self._parseFeature('CHANMODES', ',A'),
            {'addressModes': '',
             'param': 'A',
             'setParam': '',
             'noParam': ''})

        self.assertEqual(
            self._parseFeature('CHANMODES', 'A,Bc,Def,Ghij'),
            {'addressModes': 'A',
             'param': 'Bc',
             'setParam': 'Def',
             'noParam': 'Ghij'})


    def test_support_IDCHAN(self):
        """
        The IDCHAN support parameter is parsed into a sequence of two-tuples
        giving channel prefix and ID length pairs.
        """
        self.assertEqual(
            self._parseFeature('IDCHAN', '!:5'),
            [('!', '5')])


    def test_support_MAXLIST(self):
        """
        The MAXLIST support parameter is parsed into a sequence of two-tuples
        giving modes and their limits.
        """
        self.assertEqual(
            self._parseFeature('MAXLIST', 'b:25,eI:50'),
            [('b', 25), ('eI', 50)])
        # A non-integer parameter argument results in None.
        self.assertEqual(
            self._parseFeature('MAXLIST', 'b:25,eI:50,a:3.1415'),
            [('b', 25), ('eI', 50), ('a', None)])
        self.assertEqual(
            self._parseFeature('MAXLIST', 'b:25,eI:50,a:notanint'),
            [('b', 25), ('eI', 50), ('a', None)])


    def test_support_NETWORK(self):
        """
        The NETWORK support parameter is parsed as the network name, as
        specified by the server.
        """
        self.assertEqual(
            self._parseFeature('NETWORK', 'IRCNet'),
            'IRCNet')


    def test_support_SAFELIST(self):
        """
        The SAFELIST support parameter is parsed into a boolean indicating
        whether the safe "list" command is supported or not.
        """
        self.assertEqual(
            self._parseFeature('SAFELIST'),
            True)


    def test_support_STATUSMSG(self):
        """
        The STATUSMSG support parameter is parsed into a string of channel
        status that support the exclusive channel notice method.
        """
        self.assertEqual(
            self._parseFeature('STATUSMSG', '@+'),
            '@+')


    def test_support_TARGMAX(self):
        """
        The TARGMAX support parameter is parsed into a dictionary, mapping
        strings to integers, of the maximum number of targets for a particular
        command.
        """
        self.assertEqual(
            self._parseFeature('TARGMAX', 'PRIVMSG:4,NOTICE:3'),
            {'PRIVMSG': 4,
             'NOTICE': 3})
        # A non-integer parameter argument results in None.
        self.assertEqual(
            self._parseFeature('TARGMAX', 'PRIVMSG:4,NOTICE:3,KICK:3.1415'),
            {'PRIVMSG': 4,
             'NOTICE': 3,
             'KICK': None})
        self.assertEqual(
            self._parseFeature('TARGMAX', 'PRIVMSG:4,NOTICE:3,KICK:notanint'),
            {'PRIVMSG': 4,
             'NOTICE': 3,
             'KICK': None})


    def test_support_NICKLEN(self):
        """
        The NICKLEN support parameter is parsed into an integer value
        indicating the maximum length of a nickname the client may use,
        otherwise, if the parameter is missing or invalid, the default value
        (as specified by RFC 1459) is used.
        """
        default = irc.ServerSupportedFeatures()._features['NICKLEN']
        self._testIntOrDefaultFeature('NICKLEN', default)


    def test_support_CHANNELLEN(self):
        """
        The CHANNELLEN support parameter is parsed into an integer value
        indicating the maximum channel name length, otherwise, if the
        parameter is missing or invalid, the default value (as specified by
        RFC 1459) is used.
        """
        default = irc.ServerSupportedFeatures()._features['CHANNELLEN']
        self._testIntOrDefaultFeature('CHANNELLEN', default)


    def test_support_CHANTYPES(self):
        """
        The CHANTYPES support parameter is parsed into a tuple of
        valid channel prefix characters.
        """
        self._testFeatureDefault('CHANTYPES')

        self.assertEqual(
            self._parseFeature('CHANTYPES', '#&%'),
            ('#', '&', '%'))


    def test_support_KICKLEN(self):
        """
        The KICKLEN support parameter is parsed into an integer value
        indicating the maximum length of a kick message a client may use.
        """
        self._testIntOrDefaultFeature('KICKLEN')


    def test_support_PREFIX(self):
        """
        The PREFIX support parameter is parsed into a dictionary mapping
        modes to two-tuples of status symbol and priority.
        """
        self._testFeatureDefault('PREFIX')
        self._testFeatureDefault('PREFIX', [('PREFIX', 'hello')])

        self.assertEqual(
            self._parseFeature('PREFIX', None),
            None)
        self.assertEqual(
            self._parseFeature('PREFIX', '(ohv)@%+'),
            {'o': ('@', 0),
             'h': ('%', 1),
             'v': ('+', 2)})
        self.assertEqual(
            self._parseFeature('PREFIX', '(hov)@%+'),
            {'o': ('%', 1),
             'h': ('@', 0),
             'v': ('+', 2)})


    def test_support_TOPICLEN(self):
        """
        The TOPICLEN support parameter is parsed into an integer value
        indicating the maximum length of a topic a client may set.
        """
        self._testIntOrDefaultFeature('TOPICLEN')


    def test_support_MODES(self):
        """
        The MODES support parameter is parsed into an integer value
        indicating the maximum number of "variable" modes (defined as being
        modes from C{addressModes}, C{param} or C{setParam} categories for
        the C{CHANMODES} ISUPPORT parameter) which may by set on a channel
        by a single MODE command from a client.
        """
        self._testIntOrDefaultFeature('MODES')


    def test_support_EXCEPTS(self):
        """
        The EXCEPTS support parameter is parsed into the mode character
        to be used for "ban exception" modes. If no parameter is specified
        then the character C{e} is assumed.
        """
        self.assertEqual(
            self._parseFeature('EXCEPTS', 'Z'),
            'Z')
        self.assertEqual(
            self._parseFeature('EXCEPTS'),
            'e')


    def test_support_INVEX(self):
        """
        The INVEX support parameter is parsed into the mode character to be
        used for "invite exception" modes. If no parameter is specified then
        the character C{I} is assumed.
        """
        self.assertEqual(
            self._parseFeature('INVEX', 'Z'),
            'Z')
        self.assertEqual(
            self._parseFeature('INVEX'),
            'I')



class IRCClientWithoutLogin(irc.IRCClient):
    performLogin = 0



class CTCPTest(unittest.TestCase):
    """
    Tests for L{twisted.words.protocols.irc.IRCClient} CTCP handling.
    """
    def setUp(self):
        self.file = StringIOWithoutClosing()
        self.transport = protocol.FileWrapper(self.file)
        self.client = IRCClientWithoutLogin()
        self.client.makeConnection(self.transport)

        self.addCleanup(self.transport.loseConnection)
        self.addCleanup(self.client.connectionLost, None)


    def test_ERRMSG(self):
        """Testing CTCP query ERRMSG.

        Not because this is this is an especially important case in the
        field, but it does go through the entire dispatch/decode/encode
        process.
        """

        errQuery = (":nick!guy@over.there PRIVMSG #theChan :"
                    "%(X)cERRMSG t%(X)c%(EOL)s"
                    % {'X': irc.X_DELIM,
                       'EOL': irc.CR + irc.LF})

        errReply = ("NOTICE nick :%(X)cERRMSG t :"
                    "No error has occoured.%(X)c%(EOL)s"
                    % {'X': irc.X_DELIM,
                       'EOL': irc.CR + irc.LF})

        self.client.dataReceived(errQuery)
        reply = self.file.getvalue()

        self.assertEqual(errReply, reply)


    def test_noNumbersVERSION(self):
        """
        If attributes for version information on L{IRCClient} are set to
        C{None}, the parts of the CTCP VERSION response they correspond to
        are omitted.
        """
        self.client.versionName = "FrobozzIRC"
        self.client.ctcpQuery_VERSION("nick!guy@over.there", "#theChan", None)
        versionReply = ("NOTICE nick :%(X)cVERSION %(vname)s::"
                        "%(X)c%(EOL)s"
                        % {'X': irc.X_DELIM,
                           'EOL': irc.CR + irc.LF,
                           'vname': self.client.versionName})
        reply = self.file.getvalue()
        self.assertEqual(versionReply, reply)


    def test_fullVERSION(self):
        """
        The response to a CTCP VERSION query includes the version number and
        environment information, as specified by L{IRCClient.versionNum} and
        L{IRCClient.versionEnv}.
        """
        self.client.versionName = "FrobozzIRC"
        self.client.versionNum = "1.2g"
        self.client.versionEnv = "ZorkOS"
        self.client.ctcpQuery_VERSION("nick!guy@over.there", "#theChan", None)
        versionReply = ("NOTICE nick :%(X)cVERSION %(vname)s:%(vnum)s:%(venv)s"
                        "%(X)c%(EOL)s"
                        % {'X': irc.X_DELIM,
                           'EOL': irc.CR + irc.LF,
                           'vname': self.client.versionName,
                           'vnum': self.client.versionNum,
                           'venv': self.client.versionEnv})
        reply = self.file.getvalue()
        self.assertEqual(versionReply, reply)


    def test_noDuplicateCTCPDispatch(self):
        """
        Duplicated CTCP messages are ignored and no reply is made.
        """
        def testCTCP(user, channel, data):
            self.called += 1

        self.called = 0
        self.client.ctcpQuery_TESTTHIS = testCTCP

        self.client.irc_PRIVMSG(
            'foo!bar@baz.quux', [
                '#chan',
                '%(X)sTESTTHIS%(X)sfoo%(X)sTESTTHIS%(X)s' % {'X': irc.X_DELIM}])
        self.assertEqual(
            self.file.getvalue(),
            '')
        self.assertEqual(self.called, 1)


    def test_noDefaultDispatch(self):
        """
        The fallback handler is invoked for unrecognized CTCP messages.
        """
        def unknownQuery(user, channel, tag, data):
            self.calledWith = (user, channel, tag, data)
            self.called += 1

        self.called = 0
        self.patch(self.client, 'ctcpUnknownQuery', unknownQuery)
        self.client.irc_PRIVMSG(
            'foo!bar@baz.quux', [
                '#chan',
                '%(X)sNOTREAL%(X)s' % {'X': irc.X_DELIM}])
        self.assertEqual(
            self.file.getvalue(),
            '')
        self.assertEqual(
            self.calledWith,
            ('foo!bar@baz.quux', '#chan', 'NOTREAL', None))
        self.assertEqual(self.called, 1)

        # The fallback handler is not invoked for duplicate unknown CTCP
        # messages.
        self.client.irc_PRIVMSG(
            'foo!bar@baz.quux', [
                '#chan',
                '%(X)sNOTREAL%(X)sfoo%(X)sNOTREAL%(X)s' % {'X': irc.X_DELIM}])
        self.assertEqual(self.called, 2)



class NoticingClient(IRCClientWithoutLogin, object):
    methods = {
        'created': ('when',),
        'yourHost': ('info',),
        'myInfo': ('servername', 'version', 'umodes', 'cmodes'),
        'luserClient': ('info',),
        'bounce': ('info',),
        'isupport': ('options',),
        'luserChannels': ('channels',),
        'luserOp': ('ops',),
        'luserMe': ('info',),
        'receivedMOTD': ('motd',),

        'privmsg': ('user', 'channel', 'message'),
        'joined': ('channel',),
        'left': ('channel',),
        'noticed': ('user', 'channel', 'message'),
        'modeChanged': ('user', 'channel', 'set', 'modes', 'args'),
        'pong': ('user', 'secs'),
        'signedOn': (),
        'kickedFrom': ('channel', 'kicker', 'message'),
        'nickChanged': ('nick',),

        'userJoined': ('user', 'channel'),
        'userLeft': ('user', 'channel'),
        'userKicked': ('user', 'channel', 'kicker', 'message'),
        'action': ('user', 'channel', 'data'),
        'topicUpdated': ('user', 'channel', 'newTopic'),
        'userRenamed': ('oldname', 'newname')}


    def __init__(self, *a, **kw):
        # It is important that IRCClient.__init__ is not called since
        # traditionally it did not exist, so it is important that nothing is
        # initialised there that would prevent subclasses that did not (or
        # could not) invoke the base implementation. Any protocol
        # initialisation should happen in connectionMode.
        self.calls = []


    def __getattribute__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(NoticingClient, self).__getattribute__(name)
        try:
            args = super(NoticingClient, self).__getattribute__('methods')[name]
        except KeyError:
            return super(NoticingClient, self).__getattribute__(name)
        else:
            return self.makeMethod(name, args)


    def makeMethod(self, fname, args):
        def method(*a, **kw):
            if len(a) > len(args):
                raise TypeError("TypeError: %s() takes %d arguments "
                                "(%d given)" % (fname, len(args), len(a)))
            for (name, value) in zip(args, a):
                if name in kw:
                    raise TypeError("TypeError: %s() got multiple values "
                                    "for keyword argument '%s'" % (fname, name))
                else:
                    kw[name] = value
            if len(kw) != len(args):
                raise TypeError("TypeError: %s() takes %d arguments "
                                "(%d given)" % (fname, len(args), len(a)))
            self.calls.append((fname, kw))
        return method


def pop(dict, key, default):
    try:
        value = dict[key]
    except KeyError:
        return default
    else:
        del dict[key]
        return value



class ClientImplementationTests(unittest.TestCase):
    def setUp(self):
        self.transport = StringTransport()
        self.client = NoticingClient()
        self.client.makeConnection(self.transport)

        self.addCleanup(self.transport.loseConnection)
        self.addCleanup(self.client.connectionLost, None)


    def _serverTestImpl(self, code, msg, func, **kw):
        host = pop(kw, 'host', 'server.host')
        nick = pop(kw, 'nick', 'nickname')
        args = pop(kw, 'args', '')

        message = (":" +
                   host + " " +
                   code + " " +
                   nick + " " +
                   args + " :" +
                   msg + "\r\n")

        self.client.dataReceived(message)
        self.assertEqual(
            self.client.calls,
            [(func, kw)])


    def testYourHost(self):
        msg = "Your host is some.host[blah.blah/6667], running version server-version-3"
        self._serverTestImpl("002", msg, "yourHost", info=msg)


    def testCreated(self):
        msg = "This server was cobbled together Fri Aug 13 18:00:25 UTC 2004"
        self._serverTestImpl("003", msg, "created", when=msg)


    def testMyInfo(self):
        msg = "server.host server-version abcDEF bcdEHI"
        self._serverTestImpl("004", msg, "myInfo",
                             servername="server.host",
                             version="server-version",
                             umodes="abcDEF",
                             cmodes="bcdEHI")


    def testLuserClient(self):
        msg = "There are 9227 victims and 9542 hiding on 24 servers"
        self._serverTestImpl("251", msg, "luserClient",
                             info=msg)


    def _sendISUPPORT(self):
        args = ("MODES=4 CHANLIMIT=#:20 NICKLEN=16 USERLEN=10 HOSTLEN=63 "
                "TOPICLEN=450 KICKLEN=450 CHANNELLEN=30 KEYLEN=23 CHANTYPES=# "
                "PREFIX=(ov)@+ CASEMAPPING=ascii CAPAB IRCD=dancer")
        msg = "are available on this server"
        self._serverTestImpl("005", msg, "isupport", args=args,
                             options=['MODES=4',
                                      'CHANLIMIT=#:20',
                                      'NICKLEN=16',
                                      'USERLEN=10',
                                      'HOSTLEN=63',
                                      'TOPICLEN=450',
                                      'KICKLEN=450',
                                      'CHANNELLEN=30',
                                      'KEYLEN=23',
                                      'CHANTYPES=#',
                                      'PREFIX=(ov)@+',
                                      'CASEMAPPING=ascii',
                                      'CAPAB',
                                      'IRCD=dancer'])


    def test_ISUPPORT(self):
        """
        The client parses ISUPPORT messages sent by the server and calls
        L{IRCClient.isupport}.
        """
        self._sendISUPPORT()


    def testBounce(self):
        msg = "Try server some.host, port 321"
        self._serverTestImpl("010", msg, "bounce",
                             info=msg)


    def testLuserChannels(self):
        args = "7116"
        msg = "channels formed"
        self._serverTestImpl("254", msg, "luserChannels", args=args,
                             channels=int(args))


    def testLuserOp(self):
        args = "34"
        msg = "flagged staff members"
        self._serverTestImpl("252", msg, "luserOp", args=args,
                             ops=int(args))


    def testLuserMe(self):
        msg = "I have 1937 clients and 0 servers"
        self._serverTestImpl("255", msg, "luserMe",
                             info=msg)


    def test_receivedMOTD(self):
        """
        Lines received in I{RPL_MOTDSTART} and I{RPL_MOTD} are delivered to
        L{IRCClient.receivedMOTD} when I{RPL_ENDOFMOTD} is received.
        """
        lines = [
            ":host.name 375 nickname :- host.name Message of the Day -",
            ":host.name 372 nickname :- Welcome to host.name",
            ":host.name 376 nickname :End of /MOTD command."]
        for L in lines:
            self.assertEqual(self.client.calls, [])
            self.client.dataReceived(L + '\r\n')

        self.assertEqual(
            self.client.calls,
            [("receivedMOTD", {"motd": ["host.name Message of the Day -", "Welcome to host.name"]})])

        # After the motd is delivered, the tracking variable should be
        # reset.
        self.assertIdentical(self.client.motd, None)


    def test_withoutMOTDSTART(self):
        """
        If L{IRCClient} receives I{RPL_MOTD} and I{RPL_ENDOFMOTD} without
        receiving I{RPL_MOTDSTART}, L{IRCClient.receivedMOTD} is still
        called with a list of MOTD lines.
        """
        lines = [
            ":host.name 372 nickname :- Welcome to host.name",
            ":host.name 376 nickname :End of /MOTD command."]

        for L in lines:
            self.client.dataReceived(L + '\r\n')

        self.assertEqual(
            self.client.calls,
            [("receivedMOTD", {"motd": ["Welcome to host.name"]})])


    def _clientTestImpl(self, sender, group, type, msg, func, **kw):
        ident = pop(kw, 'ident', 'ident')
        host = pop(kw, 'host', 'host')

        wholeUser = sender + '!' + ident + '@' + host
        message = (":" +
                   wholeUser + " " +
                   type + " " +
                   group + " :" +
                   msg + "\r\n")
        self.client.dataReceived(message)
        self.assertEqual(
            self.client.calls,
            [(func, kw)])
        self.client.calls = []


    def testPrivmsg(self):
        msg = "Tooty toot toot."
        self._clientTestImpl("sender", "#group", "PRIVMSG", msg, "privmsg",
                             ident="ident", host="host",
                             # Expected results below
                             user="sender!ident@host",
                             channel="#group",
                             message=msg)

        self._clientTestImpl("sender", "recipient", "PRIVMSG", msg, "privmsg",
                             ident="ident", host="host",
                             # Expected results below
                             user="sender!ident@host",
                             channel="recipient",
                             message=msg)


    def test_getChannelModeParams(self):
        """
        L{IRCClient.getChannelModeParams} uses ISUPPORT information, either
        given by the server or defaults, to determine which channel modes
        require arguments when being added or removed.
        """
        add, remove = map(sorted, self.client.getChannelModeParams())
        self.assertEqual(add, ['b', 'h', 'k', 'l', 'o', 'v'])
        self.assertEqual(remove, ['b', 'h', 'o', 'v'])

        def removeFeature(name):
            name = '-' + name
            msg = "are available on this server"
            self._serverTestImpl(
                '005', msg, 'isupport', args=name, options=[name])
            self.assertIdentical(
                self.client.supported.getFeature(name), None)
            self.client.calls = []

        # Remove CHANMODES feature, causing getFeature('CHANMODES') to return
        # None.
        removeFeature('CHANMODES')
        add, remove = map(sorted, self.client.getChannelModeParams())
        self.assertEqual(add, ['h', 'o', 'v'])
        self.assertEqual(remove, ['h', 'o', 'v'])

        # Remove PREFIX feature, causing getFeature('PREFIX') to return None.
        removeFeature('PREFIX')
        add, remove = map(sorted, self.client.getChannelModeParams())
        self.assertEqual(add, [])
        self.assertEqual(remove, [])

        # Restore ISUPPORT features.
        self._sendISUPPORT()
        self.assertNotIdentical(
            self.client.supported.getFeature('PREFIX'), None)


    def test_getUserModeParams(self):
        """
        L{IRCClient.getUserModeParams} returns a list of user modes (modes that
        the user sets on themself, outside of channel modes) that require
        parameters when added and removed, respectively.
        """
        add, remove = map(sorted, self.client.getUserModeParams())
        self.assertEqual(add, [])
        self.assertEqual(remove, [])


    def _sendModeChange(self, msg, args='', target=None):
        """
        Build a MODE string and send it to the client.
        """
        if target is None:
            target = '#chan'
        message = ":Wolf!~wolf@yok.utu.fi MODE %s %s %s\r\n" % (
            target, msg, args)
        self.client.dataReceived(message)


    def _parseModeChange(self, results, target=None):
        """
        Parse the results, do some test and return the data to check.
        """
        if target is None:
            target = '#chan'

        for n, result in enumerate(results):
            method, data = result
            self.assertEqual(method, 'modeChanged')
            self.assertEqual(data['user'], 'Wolf!~wolf@yok.utu.fi')
            self.assertEqual(data['channel'], target)
            results[n] = tuple([data[key] for key in ('set', 'modes', 'args')])
        return results


    def _checkModeChange(self, expected, target=None):
        """
        Compare the expected result with the one returned by the client.
        """
        result = self._parseModeChange(self.client.calls, target)
        self.assertEqual(result, expected)
        self.client.calls = []


    def test_modeMissingDirection(self):
        """
        Mode strings that do not begin with a directional character, C{'+'} or
        C{'-'}, have C{'+'} automatically prepended.
        """
        self._sendModeChange('s')
        self._checkModeChange([(True, 's', (None,))])


    def test_noModeParameters(self):
        """
        No parameters are passed to L{IRCClient.modeChanged} for modes that
        don't take any parameters.
        """
        self._sendModeChange('-s')
        self._checkModeChange([(False, 's', (None,))])
        self._sendModeChange('+n')
        self._checkModeChange([(True, 'n', (None,))])


    def test_oneModeParameter(self):
        """
        Parameters are passed to L{IRCClient.modeChanged} for modes that take
        parameters.
        """
        self._sendModeChange('+o', 'a_user')
        self._checkModeChange([(True, 'o', ('a_user',))])
        self._sendModeChange('-o', 'a_user')
        self._checkModeChange([(False, 'o', ('a_user',))])


    def test_mixedModes(self):
        """
        Mixing adding and removing modes that do and don't take parameters
        invokes L{IRCClient.modeChanged} with mode characters and parameters
        that match up.
        """
        self._sendModeChange('+osv', 'a_user another_user')
        self._checkModeChange([(True, 'osv', ('a_user', None, 'another_user'))])
        self._sendModeChange('+v-os', 'a_user another_user')
        self._checkModeChange([(True, 'v', ('a_user',)),
                               (False, 'os', ('another_user', None))])


    def test_tooManyModeParameters(self):
        """
        Passing an argument to modes that take no parameters results in
        L{IRCClient.modeChanged} not being called and an error being logged.
        """
        self._sendModeChange('+s', 'wrong')
        self._checkModeChange([])
        errors = self.flushLoggedErrors(irc.IRCBadModes)
        self.assertEqual(len(errors), 1)
        self.assertSubstring(
            'Too many parameters', errors[0].getErrorMessage())


    def test_tooFewModeParameters(self):
        """
        Passing no arguments to modes that do take parameters results in
        L{IRCClient.modeChange} not being called and an error being logged.
        """
        self._sendModeChange('+o')
        self._checkModeChange([])
        errors = self.flushLoggedErrors(irc.IRCBadModes)
        self.assertEqual(len(errors), 1)
        self.assertSubstring(
            'Not enough parameters', errors[0].getErrorMessage())


    def test_userMode(self):
        """
        A C{MODE} message whose target is our user (the nickname of our user,
        to be precise), as opposed to a channel, will be parsed according to
        the modes specified by L{IRCClient.getUserModeParams}.
        """
        target = self.client.nickname
        # Mode "o" on channels is supposed to take a parameter, but since this
        # is not a channel this will not cause an exception.
        self._sendModeChange('+o', target=target)
        self._checkModeChange([(True, 'o', (None,))], target=target)

        def getUserModeParams():
            return ['Z', '']

        # Introduce our own user mode that takes an argument.
        self.patch(self.client, 'getUserModeParams', getUserModeParams)

        self._sendModeChange('+Z', 'an_arg', target=target)
        self._checkModeChange([(True, 'Z', ('an_arg',))], target=target)


    def test_heartbeat(self):
        """
        When the I{RPL_WELCOME} message is received a heartbeat is started that
        will send a I{PING} message to the IRC server every
        L{irc.IRCClient.heartbeatInterval} seconds. When the transport is
        closed the heartbeat looping call is stopped too.
        """
        def _createHeartbeat():
            heartbeat = self._originalCreateHeartbeat()
            heartbeat.clock = self.clock
            return heartbeat

        self.clock = task.Clock()
        self._originalCreateHeartbeat = self.client._createHeartbeat
        self.patch(self.client, '_createHeartbeat', _createHeartbeat)

        self.assertIdentical(self.client._heartbeat, None)
        self.client.irc_RPL_WELCOME('foo', [])
        self.assertNotIdentical(self.client._heartbeat, None)
        self.assertEqual(self.client.hostname, 'foo')

        # Pump the clock enough to trigger one LoopingCall.
        self.assertEqual(self.transport.value(), '')
        self.clock.advance(self.client.heartbeatInterval)
        self.assertEqual(self.transport.value(), 'PING foo\r\n')

        # When the connection is lost the heartbeat is stopped.
        self.transport.loseConnection()
        self.client.connectionLost(None)
        self.assertEqual(
            len(self.clock.getDelayedCalls()), 0)
        self.assertIdentical(self.client._heartbeat, None)


    def test_heartbeatDisabled(self):
        """
        If L{irc.IRCClient.heartbeatInterval} is set to C{None} then no
        heartbeat is created.
        """
        self.assertIdentical(self.client._heartbeat, None)
        self.client.heartbeatInterval = None
        self.client.irc_RPL_WELCOME('foo', [])
        self.assertIdentical(self.client._heartbeat, None)



class BasicServerFunctionalityTestCase(unittest.TestCase):
    def setUp(self):
        self.f = StringIOWithoutClosing()
        self.t = protocol.FileWrapper(self.f)
        self.p = irc.IRC()
        self.p.makeConnection(self.t)


    def check(self, s):
        self.assertEqual(self.f.getvalue(), s)


    def testPrivmsg(self):
        self.p.privmsg("this-is-sender", "this-is-recip", "this is message")
        self.check(":this-is-sender PRIVMSG this-is-recip :this is message\r\n")


    def testNotice(self):
        self.p.notice("this-is-sender", "this-is-recip", "this is notice")
        self.check(":this-is-sender NOTICE this-is-recip :this is notice\r\n")


    def testAction(self):
        self.p.action("this-is-sender", "this-is-recip", "this is action")
        self.check(":this-is-sender ACTION this-is-recip :this is action\r\n")


    def testJoin(self):
        self.p.join("this-person", "#this-channel")
        self.check(":this-person JOIN #this-channel\r\n")


    def testPart(self):
        self.p.part("this-person", "#that-channel")
        self.check(":this-person PART #that-channel\r\n")


    def testWhois(self):
        """
        Verify that a whois by the client receives the right protocol actions
        from the server.
        """
        timestamp = int(time.time()-100)
        hostname = self.p.hostname
        req = 'requesting-nick'
        targ = 'target-nick'
        self.p.whois(req, targ, 'target', 'host.com',
                'Target User', 'irc.host.com', 'A fake server', False,
                12, timestamp, ['#fakeusers', '#fakemisc'])
        expected = '\r\n'.join([
':%(hostname)s 311 %(req)s %(targ)s target host.com * :Target User',
':%(hostname)s 312 %(req)s %(targ)s irc.host.com :A fake server',
':%(hostname)s 317 %(req)s %(targ)s 12 %(timestamp)s :seconds idle, signon time',
':%(hostname)s 319 %(req)s %(targ)s :#fakeusers #fakemisc',
':%(hostname)s 318 %(req)s %(targ)s :End of WHOIS list.',
'']) % dict(hostname=hostname, timestamp=timestamp, req=req, targ=targ)
        self.check(expected)



class DummyClient(irc.IRCClient):
    """
    A L{twisted.words.protocols.irc.IRCClient} that stores sent lines in a
    C{list} rather than transmitting them.
    """
    def __init__(self):
        self.lines = []


    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self.lines = []


    def _truncateLine(self, line):
        """
        Truncate an IRC line to the maximum allowed length.
        """
        return line[:irc.MAX_COMMAND_LENGTH - len(self.delimiter)]


    def lineReceived(self, line):
        # Emulate IRC servers throwing away our important data.
        line = self._truncateLine(line)
        return irc.IRCClient.lineReceived(self, line)


    def sendLine(self, m):
        self.lines.append(self._truncateLine(m))



class ClientInviteTests(unittest.TestCase):
    """
    Tests for L{IRCClient.invite}.
    """
    def setUp(self):
        """
        Create a L{DummyClient} to call C{invite} on in test methods.
        """
        self.client = DummyClient()


    def test_channelCorrection(self):
        """
        If the channel name passed to L{IRCClient.invite} does not begin with a
        channel prefix character, one is prepended to it.
        """
        self.client.invite('foo', 'bar')
        self.assertEqual(self.client.lines, ['INVITE foo #bar'])


    def test_invite(self):
        """
        L{IRCClient.invite} sends an I{INVITE} message with the specified
        username and a channel.
        """
        self.client.invite('foo', '#bar')
        self.assertEqual(self.client.lines, ['INVITE foo #bar'])



class ClientMsgTests(unittest.TestCase):
    """
    Tests for messages sent with L{twisted.words.protocols.irc.IRCClient}.
    """
    def setUp(self):
        self.client = DummyClient()
        self.client.connectionMade()


    def test_singleLine(self):
        """
        A message containing no newlines is sent in a single command.
        """
        self.client.msg('foo', 'bar')
        self.assertEqual(self.client.lines, ['PRIVMSG foo :bar'])


    def test_invalidMaxLength(self):
        """
        Specifying a C{length} value to L{IRCClient.msg} that is too short to
        contain the protocol command to send a message raises C{ValueError}.
        """
        self.assertRaises(ValueError, self.client.msg, 'foo', 'bar', 0)
        self.assertRaises(ValueError, self.client.msg, 'foo', 'bar', 3)


    def test_multipleLine(self):
        """
        Messages longer than the C{length} parameter to L{IRCClient.msg} will
        be split and sent in multiple commands.
        """
        maxLen = len('PRIVMSG foo :') + 3 + 2 # 2 for line endings
        self.client.msg('foo', 'barbazbo', maxLen)
        self.assertEqual(
            self.client.lines,
            ['PRIVMSG foo :bar',
             'PRIVMSG foo :baz',
             'PRIVMSG foo :bo'])


    def test_sufficientWidth(self):
        """
        Messages exactly equal in length to the C{length} paramtere to
        L{IRCClient.msg} are sent in a single command.
        """
        msg = 'barbazbo'
        maxLen = len('PRIVMSG foo :%s' % (msg,)) + 2
        self.client.msg('foo', msg, maxLen)
        self.assertEqual(self.client.lines, ['PRIVMSG foo :%s' % (msg,)])
        self.client.lines = []
        self.client.msg('foo', msg, maxLen-1)
        self.assertEqual(2, len(self.client.lines))
        self.client.lines = []
        self.client.msg('foo', msg, maxLen+1)
        self.assertEqual(1, len(self.client.lines))


    def test_newlinesAtStart(self):
        """
        An LF at the beginning of the message is ignored.
        """
        self.client.lines = []
        self.client.msg('foo', '\nbar')
        self.assertEqual(self.client.lines, ['PRIVMSG foo :bar'])


    def test_newlinesAtEnd(self):
        """
        An LF at the end of the message is ignored.
        """
        self.client.lines = []
        self.client.msg('foo', 'bar\n')
        self.assertEqual(self.client.lines, ['PRIVMSG foo :bar'])


    def test_newlinesWithinMessage(self):
        """
        An LF within a message causes a new line.
        """
        self.client.lines = []
        self.client.msg('foo', 'bar\nbaz')
        self.assertEqual(
            self.client.lines,
            ['PRIVMSG foo :bar',
             'PRIVMSG foo :baz'])


    def test_consecutiveNewlines(self):
        """
        Consecutive LFs do not cause a blank line.
        """
        self.client.lines = []
        self.client.msg('foo', 'bar\n\nbaz')
        self.assertEqual(
            self.client.lines,
            ['PRIVMSG foo :bar',
             'PRIVMSG foo :baz'])


    def assertLongMessageSplitting(self, message, expectedNumCommands,
                                   length=None):
        """
        Assert that messages sent by L{IRCClient.msg} are split into an
        expected number of commands and the original message is transmitted in
        its entirety over those commands.
        """
        responsePrefix = ':%s!%s@%s ' % (
            self.client.nickname,
            self.client.realname,
            self.client.hostname)

        self.client.msg('foo', message, length=length)

        privmsg = []
        self.patch(self.client, 'privmsg', lambda *a: privmsg.append(a))
        # Deliver these to IRCClient via the normal mechanisms.
        for line in self.client.lines:
            self.client.lineReceived(responsePrefix + line)

        self.assertEqual(len(privmsg), expectedNumCommands)
        receivedMessage = ''.join(
            message for user, target, message in privmsg)

        # Did the long message we sent arrive as intended?
        self.assertEqual(message, receivedMessage)


    def test_splitLongMessagesWithDefault(self):
        """
        If a maximum message length is not provided to L{IRCClient.msg} a
        best-guess effort is made to determine a safe maximum,  messages longer
        than this are split into multiple commands with the intent of
        delivering long messages without losing data due to message truncation
        when the server relays them.
        """
        message = 'o' * (irc.MAX_COMMAND_LENGTH - 2)
        self.assertLongMessageSplitting(message, 2)


    def test_splitLongMessagesWithOverride(self):
        """
        The maximum message length can be specified to L{IRCClient.msg},
        messages longer than this are split into multiple commands with the
        intent of delivering long messages without losing data due to message
        truncation when the server relays them.
        """
        message = 'o' * (irc.MAX_COMMAND_LENGTH - 2)
        self.assertLongMessageSplitting(
            message, 3, length=irc.MAX_COMMAND_LENGTH // 2)


    def test_newlinesBeforeLineBreaking(self):
        """
        IRCClient breaks on newlines before it breaks long lines.
        """
        # Because MAX_COMMAND_LENGTH includes framing characters, this long
        # line is slightly longer than half the permissible message size.
        longline = 'o' * (irc.MAX_COMMAND_LENGTH // 2)

        self.client.msg('foo', longline + '\n' + longline)
        self.assertEqual(
            self.client.lines,
            ['PRIVMSG foo :' + longline,
             'PRIVMSG foo :' + longline])


    def test_lineBreakOnWordBoundaries(self):
        """
        IRCClient prefers to break long lines at word boundaries.
        """
        # Because MAX_COMMAND_LENGTH includes framing characters, this long
        # line is slightly longer than half the permissible message size.
        longline = 'o' * (irc.MAX_COMMAND_LENGTH // 2)

        self.client.msg('foo', longline + ' ' + longline)
        self.assertEqual(
            self.client.lines,
            ['PRIVMSG foo :' + longline,
             'PRIVMSG foo :' + longline])


    def test_splitSanity(self):
        """
        L{twisted.words.protocols.irc.split} raises C{ValueError} if given a
        length less than or equal to C{0} and returns C{[]} when splitting
        C{''}.
        """
        # Whiteboxing
        self.assertRaises(ValueError, irc.split, 'foo', -1)
        self.assertRaises(ValueError, irc.split, 'foo', 0)
        self.assertEqual([], irc.split('', 1))
        self.assertEqual([], irc.split(''))


    def test_splitDelimiters(self):
        """
        L{twisted.words.protocols.irc.split} skips any delimiter (space or
        newline) that it finds at the very beginning of the string segment it
        is operating on.  Nothing should be added to the output list because of
        it.
        """
        r = irc.split("xx yyz", 2)
        self.assertEqual(['xx', 'yy', 'z'], r)
        r = irc.split("xx\nyyz", 2)
        self.assertEqual(['xx', 'yy', 'z'], r)


    def test_splitValidatesLength(self):
        """
        L{twisted.words.protocols.irc.split} raises C{ValueError} if given a
        length less than or equal to C{0}.
        """
        self.assertRaises(ValueError, irc.split, "foo", 0)
        self.assertRaises(ValueError, irc.split, "foo", -1)


    def test_say(self):
        """
        L{IRCClient.say} prepends the channel prefix C{"#"} if necessary and
        then sends the message to the server for delivery to that channel.
        """
        self.client.say("thechannel", "the message")
        self.assertEquals(
            self.client.lines, ["PRIVMSG #thechannel :the message"])



class ClientTests(TestCase):
    """
    Tests for the protocol-level behavior of IRCClient methods intended to
    be called by application code.
    """
    def setUp(self):
        """
        Create and connect a new L{IRCClient} to a new L{StringTransport}.
        """
        self.transport = StringTransport()
        self.protocol = IRCClient()
        self.protocol.performLogin = False
        self.protocol.makeConnection(self.transport)

        # Sanity check - we don't want anything to have happened at this
        # point, since we're not in a test yet.
        self.assertEqual(self.transport.value(), "")

        self.addCleanup(self.transport.loseConnection)
        self.addCleanup(self.protocol.connectionLost, None)


    def getLastLine(self, transport):
        """
        Return the last IRC message in the transport buffer.
        """
        return transport.value().split('\r\n')[-2]


    def test_away(self):
        """
        L{IRCCLient.away} sends an AWAY command with the specified message.
        """
        message = "Sorry, I'm not here."
        self.protocol.away(message)
        expected = [
            'AWAY :%s' % (message,),
            '',
        ]
        self.assertEqual(self.transport.value().split('\r\n'), expected)


    def test_back(self):
        """
        L{IRCClient.back} sends an AWAY command with an empty message.
        """
        self.protocol.back()
        expected = [
            'AWAY :',
            '',
        ]
        self.assertEqual(self.transport.value().split('\r\n'), expected)


    def test_whois(self):
        """
        L{IRCClient.whois} sends a WHOIS message.
        """
        self.protocol.whois('alice')
        self.assertEqual(
            self.transport.value().split('\r\n'),
            ['WHOIS alice', ''])


    def test_whoisWithServer(self):
        """
        L{IRCClient.whois} sends a WHOIS message with a server name if a
        value is passed for the C{server} parameter.
        """
        self.protocol.whois('alice', 'example.org')
        self.assertEqual(
            self.transport.value().split('\r\n'),
            ['WHOIS example.org alice', ''])


    def test_register(self):
        """
        L{IRCClient.register} sends NICK and USER commands with the
        username, name, hostname, server name, and real name specified.
        """
        username = 'testuser'
        hostname = 'testhost'
        servername = 'testserver'
        self.protocol.realname = 'testname'
        self.protocol.password = None
        self.protocol.register(username, hostname, servername)
        expected = [
            'NICK %s' % (username,),
            'USER %s %s %s :%s' % (
                username, hostname, servername, self.protocol.realname),
            '']
        self.assertEqual(self.transport.value().split('\r\n'), expected)


    def test_registerWithPassword(self):
        """
        If the C{password} attribute of L{IRCClient} is not C{None}, the
        C{register} method also sends a PASS command with it as the
        argument.
        """
        username = 'testuser'
        hostname = 'testhost'
        servername = 'testserver'
        self.protocol.realname = 'testname'
        self.protocol.password = 'testpass'
        self.protocol.register(username, hostname, servername)
        expected = [
            'PASS %s' % (self.protocol.password,),
            'NICK %s' % (username,),
            'USER %s %s %s :%s' % (
                username, hostname, servername, self.protocol.realname),
            '']
        self.assertEqual(self.transport.value().split('\r\n'), expected)


    def test_registerWithTakenNick(self):
        """
        Verify that the client repeats the L{IRCClient.setNick} method with a
        new value when presented with an C{ERR_NICKNAMEINUSE} while trying to
        register.
        """
        username = 'testuser'
        hostname = 'testhost'
        servername = 'testserver'
        self.protocol.realname = 'testname'
        self.protocol.password = 'testpass'
        self.protocol.register(username, hostname, servername)
        self.protocol.irc_ERR_NICKNAMEINUSE('prefix', ['param'])
        lastLine = self.getLastLine(self.transport)
        self.assertNotEquals(lastLine, 'NICK %s' % (username,))

        # Keep chaining underscores for each collision
        self.protocol.irc_ERR_NICKNAMEINUSE('prefix', ['param'])
        lastLine = self.getLastLine(self.transport)
        self.assertEqual(lastLine, 'NICK %s' % (username + '__',))


    def test_overrideAlterCollidedNick(self):
        """
        L{IRCClient.alterCollidedNick} determines how a nickname is altered upon
        collision while a user is trying to change to that nickname.
        """
        nick = 'foo'
        self.protocol.alterCollidedNick = lambda nick: nick + '***'
        self.protocol.register(nick)
        self.protocol.irc_ERR_NICKNAMEINUSE('prefix', ['param'])
        lastLine = self.getLastLine(self.transport)
        self.assertEqual(
            lastLine, 'NICK %s' % (nick + '***',))


    def test_nickChange(self):
        """
        When a NICK command is sent after signon, C{IRCClient.nickname} is set
        to the new nickname I{after} the server sends an acknowledgement.
        """
        oldnick = 'foo'
        newnick = 'bar'
        self.protocol.register(oldnick)
        self.protocol.irc_RPL_WELCOME('prefix', ['param'])
        self.protocol.setNick(newnick)
        self.assertEqual(self.protocol.nickname, oldnick)
        self.protocol.irc_NICK('%s!quux@qux' % (oldnick,), [newnick])
        self.assertEqual(self.protocol.nickname, newnick)


    def test_erroneousNick(self):
        """
        Trying to register an illegal nickname results in the default legal
        nickname being set, and trying to change a nickname to an illegal
        nickname results in the old nickname being kept.
        """
        # Registration case: change illegal nickname to erroneousNickFallback
        badnick = 'foo'
        self.assertEqual(self.protocol._registered, False)
        self.protocol.register(badnick)
        self.protocol.irc_ERR_ERRONEUSNICKNAME('prefix', ['param'])
        lastLine = self.getLastLine(self.transport)
        self.assertEqual(
            lastLine, 'NICK %s' % (self.protocol.erroneousNickFallback,))
        self.protocol.irc_RPL_WELCOME('prefix', ['param'])
        self.assertEqual(self.protocol._registered, True)
        self.protocol.setNick(self.protocol.erroneousNickFallback)
        self.assertEqual(
            self.protocol.nickname, self.protocol.erroneousNickFallback)

        # Illegal nick change attempt after registration. Fall back to the old
        # nickname instead of erroneousNickFallback.
        oldnick = self.protocol.nickname
        self.protocol.setNick(badnick)
        self.protocol.irc_ERR_ERRONEUSNICKNAME('prefix', ['param'])
        lastLine = self.getLastLine(self.transport)
        self.assertEqual(
            lastLine, 'NICK %s' % (badnick,))
        self.assertEqual(self.protocol.nickname, oldnick)


    def test_describe(self):
        """
        L{IRCClient.desrcibe} sends a CTCP ACTION message to the target
        specified.
        """
        target = 'foo'
        channel = '#bar'
        action = 'waves'
        self.protocol.describe(target, action)
        self.protocol.describe(channel, action)
        expected = [
            'PRIVMSG %s :\01ACTION %s\01' % (target, action),
            'PRIVMSG %s :\01ACTION %s\01' % (channel, action),
            '']
        self.assertEqual(self.transport.value().split('\r\n'), expected)


    def test_noticedDoesntPrivmsg(self):
        """
        The default implementation of L{IRCClient.noticed} doesn't invoke
        C{privmsg()}
        """
        def privmsg(user, channel, message):
            self.fail("privmsg() should not have been called")
        self.protocol.privmsg = privmsg
        self.protocol.irc_NOTICE(
            'spam', ['#greasyspooncafe', "I don't want any spam!"])



class DccChatFactoryTests(unittest.TestCase):
    """
    Tests for L{DccChatFactory}
    """
    def test_buildProtocol(self):
        """
        An instance of the DccChat protocol is returned, which has the factory
        property set to the factory which created it.
        """
        queryData = ('fromUser', None, None)
        f = irc.DccChatFactory(None, queryData)
        p = f.buildProtocol('127.0.0.1')
        self.assertTrue(isinstance(p, irc.DccChat))
        self.assertEqual(p.factory, f)
