# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.scripts.tap2rpm}.
"""

import os
import warnings

from twisted.trial.unittest import TestCase, SkipTest
from twisted.python import procutils
from twisted.python import versions
from twisted.python import deprecate
from twisted.python.failure import Failure
from twisted.internet import utils

# When we query the RPM metadata, we get back a string we'll have to parse, so
# we'll use suitably rare delimiter characters to split on. Luckily, ASCII
# defines some for us!
RECORD_SEPARATOR = "\x1E"
UNIT_SEPARATOR = "\x1F"

with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=DeprecationWarning)
    from twisted.scripts import tap2rpm


def _makeRPMs(tapfile=None, maintainer=None, protocol=None, description=None,
        longDescription=None, setVersion=None, rpmfile=None, type_=None):
    """
    Helper function to invoke tap2rpm with the given parameters.
    """
    args = []

    if not tapfile:
        tapfile = "dummy-tap-file"
        handle = open(tapfile, "w")
        handle.write("# Dummy TAP file\n")
        handle.close()

    args.extend(["--quiet", "--tapfile", tapfile])

    if maintainer:
        args.extend(["--maintainer", maintainer])
    if protocol:
        args.extend(["--protocol", protocol])
    if description:
        args.extend(["--description", description])
    if longDescription:
        args.extend(["--long_description", longDescription])
    if setVersion:
        args.extend(["--set-version", setVersion])
    if rpmfile:
        args.extend(["--rpmfile", rpmfile])
    if type_:
        args.extend(["--type", type_])

    return tap2rpm.run(args)



def _queryRPMTags(rpmfile, taglist):
    """
    Helper function to read the given header tags from the given RPM file.

    Returns a Deferred that fires with dictionary mapping a tag name to a list
    of the associated values in the RPM header. If a tag has only a single
    value in the header (like NAME or VERSION), it will be returned as a 1-item
    list.

    Run "rpm --querytags" to see what tags can be queried.
    """

    # Build a query format string that will return appropriately delimited
    # results. Every field is treated as an array field, so single-value tags
    # like VERSION will be returned as 1-item lists.
    queryFormat = RECORD_SEPARATOR.join([
            "[%%{%s}%s]" % (tag, UNIT_SEPARATOR) for tag in taglist
           ])

    def parseTagValues(output):
        res = {}

        for tag, values in zip(taglist, output.split(RECORD_SEPARATOR)):
            values = values.strip(UNIT_SEPARATOR).split(UNIT_SEPARATOR)
            res[tag] = values

        return res

    def checkErrorResult(failure):
        # The current rpm packages on Debian and Ubuntu don't properly set up
        # the RPM database, which causes rpm to print a harmless warning to
        # stderr. Unfortunately, .getProcessOutput() assumes all warnings are
        # catastrophic and panics whenever it sees one.
        #
        # See also:
        #   http://twistedmatrix.com/trac/ticket/3292#comment:42
        #   http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=551669
        #   http://rpm.org/ticket/106

        failure.trap(IOError)

        # Depending on kernel scheduling, we might read the whole error
        # message, or only the first few bytes.
        if str(failure.value).startswith("got stderr: 'error: "):
            newFailure = Failure(SkipTest("rpm is missing its package "
                    "database. Run 'sudo rpm -qa > /dev/null' to create one."))
        else:
            # Not the exception we were looking for; we should report the
            # original failure.
            newFailure = failure

        # We don't want to raise the exception right away; we want to wait for
        # the process to exit, otherwise we'll get extra useless errors
        # reported.
        d = failure.value.processEnded
        d.addBoth(lambda _: newFailure)
        return d

    d = utils.getProcessOutput("rpm",
            ("-q", "--queryformat", queryFormat, "-p", rpmfile))
    d.addCallbacks(parseTagValues, checkErrorResult)
    return d



class TestTap2RPM(TestCase):


    def setUp(self):
        return self._checkForRpmbuild()


    def _checkForRpmbuild(self):
        """
        tap2rpm requires rpmbuild; skip tests if rpmbuild is not present.
        """
        if not procutils.which("rpmbuild"):
            raise SkipTest("rpmbuild must be present to test tap2rpm")


    def _makeTapFile(self, basename="dummy"):
        """
        Make a temporary .tap file and returns the absolute path.
        """
        path = basename + ".tap"
        handle = open(path, "w")
        handle.write("# Dummy .tap file")
        handle.close()
        return path


    def _verifyRPMTags(self, rpmfile, **tags):
        """
        Check the given file has the given tags set to the given values.
        """

        d = _queryRPMTags(rpmfile, tags.keys())
        d.addCallback(self.assertEqual, tags)
        return d


    def test_optionDefaults(self):
        """
        Commandline options should default to sensible values.

        "sensible" here is defined as "the same values that previous versions
        defaulted to".
        """
        config = tap2rpm.MyOptions()
        config.parseOptions([])

        self.assertEqual(config['tapfile'], 'twistd.tap')
        self.assertEqual(config['maintainer'], 'tap2rpm')
        self.assertEqual(config['protocol'], 'twistd')
        self.assertEqual(config['description'], 'A TCP server for twistd')
        self.assertEqual(config['long_description'],
                'Automatically created by tap2rpm')
        self.assertEqual(config['set-version'], '1.0')
        self.assertEqual(config['rpmfile'], 'twisted-twistd')
        self.assertEqual(config['type'], 'tap')
        self.assertEqual(config['quiet'], False)
        self.assertEqual(config['twistd_option'], 'file')
        self.assertEqual(config['release-name'], 'twisted-twistd-1.0')


    def test_protocolCalculatedFromTapFile(self):
        """
        The protocol name defaults to a value based on the tapfile value.
        """
        config = tap2rpm.MyOptions()
        config.parseOptions(['--tapfile', 'pancakes.tap'])

        self.assertEqual(config['tapfile'], 'pancakes.tap')
        self.assertEqual(config['protocol'], 'pancakes')


    def test_optionsDefaultToProtocolValue(self):
        """
        Many options default to a value calculated from the protocol name.
        """
        config = tap2rpm.MyOptions()
        config.parseOptions([
                '--tapfile', 'sausages.tap',
                '--protocol', 'eggs',
            ])

        self.assertEqual(config['tapfile'], 'sausages.tap')
        self.assertEqual(config['maintainer'], 'tap2rpm')
        self.assertEqual(config['protocol'], 'eggs')
        self.assertEqual(config['description'], 'A TCP server for eggs')
        self.assertEqual(config['long_description'],
                'Automatically created by tap2rpm')
        self.assertEqual(config['set-version'], '1.0')
        self.assertEqual(config['rpmfile'], 'twisted-eggs')
        self.assertEqual(config['type'], 'tap')
        self.assertEqual(config['quiet'], False)
        self.assertEqual(config['twistd_option'], 'file')
        self.assertEqual(config['release-name'], 'twisted-eggs-1.0')


    def test_releaseNameDefaultsToRpmfileValue(self):
        """
        The release-name option is calculated from rpmfile and set-version.
        """
        config = tap2rpm.MyOptions()
        config.parseOptions([
                "--rpmfile", "beans",
                "--set-version", "1.2.3",
            ])

        self.assertEqual(config['release-name'], 'beans-1.2.3')


    def test_basicOperation(self):
        """
        Calling tap2rpm should produce an RPM and SRPM with default metadata.
        """
        basename = "frenchtoast"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile=self._makeTapFile(basename))

        # Verify the resulting RPMs have the correct tags.
        d = self._verifyRPMTags(rpm,
                NAME=["twisted-%s" % (basename,)],
                VERSION=["1.0"],
                RELEASE=["1"],
                SUMMARY=["A TCP server for %s" % (basename,)],
                DESCRIPTION=["Automatically created by tap2rpm"],
            )
        d.addCallback(lambda _: self._verifyRPMTags(srpm,
                NAME=["twisted-%s" % (basename,)],
                VERSION=["1.0"],
                RELEASE=["1"],
                SUMMARY=["A TCP server for %s" % (basename,)],
                DESCRIPTION=["Automatically created by tap2rpm"],
            ))

        return d


    def test_protocolOverride(self):
        """
        Setting 'protocol' should change the name of the resulting package.
        """
        basename = "acorn"
        protocol = "banana"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile=self._makeTapFile(basename),
                protocol=protocol)

        # Verify the resulting RPMs have the correct tags.
        d = self._verifyRPMTags(rpm,
                NAME=["twisted-%s" % (protocol,)],
                SUMMARY=["A TCP server for %s" % (protocol,)],
            )
        d.addCallback(lambda _: self._verifyRPMTags(srpm,
                NAME=["twisted-%s" % (protocol,)],
                SUMMARY=["A TCP server for %s" % (protocol,)],
            ))

        return d


    def test_rpmfileOverride(self):
        """
        Setting 'rpmfile' should change the name of the resulting package.
        """
        basename = "cherry"
        rpmfile = "donut"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile=self._makeTapFile(basename),
                rpmfile=rpmfile)

        # Verify the resulting RPMs have the correct tags.
        d = self._verifyRPMTags(rpm,
                NAME=[rpmfile],
                SUMMARY=["A TCP server for %s" % (basename,)],
            )
        d.addCallback(lambda _: self._verifyRPMTags(srpm,
                NAME=[rpmfile],
                SUMMARY=["A TCP server for %s" % (basename,)],
            ))

        return d


    def test_descriptionOverride(self):
        """
        Setting 'description' should change the SUMMARY tag.
        """
        description = "eggplant"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile=self._makeTapFile(),
                description=description)

        # Verify the resulting RPMs have the correct tags.
        d = self._verifyRPMTags(rpm,
                SUMMARY=[description],
            )
        d.addCallback(lambda _: self._verifyRPMTags(srpm,
                SUMMARY=[description],
            ))

        return d


    def test_longDescriptionOverride(self):
        """
        Setting 'longDescription' should change the DESCRIPTION tag.
        """
        longDescription = "fig"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile=self._makeTapFile(),
                longDescription=longDescription)

        # Verify the resulting RPMs have the correct tags.
        d = self._verifyRPMTags(rpm,
                DESCRIPTION=[longDescription],
            )
        d.addCallback(lambda _: self._verifyRPMTags(srpm,
                DESCRIPTION=[longDescription],
            ))

        return d


    def test_setVersionOverride(self):
        """
        Setting 'setVersion' should change the RPM's version info.
        """
        version = "123.456"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile=self._makeTapFile(),
                setVersion=version)

        # Verify the resulting RPMs have the correct tags.
        d = self._verifyRPMTags(rpm,
                VERSION=["123.456"],
                RELEASE=["1"],
            )
        d.addCallback(lambda _: self._verifyRPMTags(srpm,
                VERSION=["123.456"],
                RELEASE=["1"],
            ))

        return d


    def test_tapInOtherDirectory(self):
        """
        tap2rpm handles tapfiles outside the current directory.
        """
        # Make a tapfile outside the current directory.
        tempdir = self.mktemp()
        os.mkdir(tempdir)
        tapfile = self._makeTapFile(os.path.join(tempdir, "bacon"))

        # Try and make an RPM from that tapfile.
        _makeRPMs(tapfile=tapfile)


    def test_unsignedFlagDeprecationWarning(self):
        """
        The 'unsigned' flag in tap2rpm should be deprecated, and its use
        should raise a warning as such.
        """
        config = tap2rpm.MyOptions()
        config.parseOptions(['--unsigned'])
        warnings = self.flushWarnings()
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            deprecate.getDeprecationWarningString(
                config.opt_unsigned, versions.Version("Twisted", 12, 1, 0)),
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))
