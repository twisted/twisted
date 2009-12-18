# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.scripts.tap2rpm}.
"""
from os.path import exists
from twisted.trial.unittest import TestCase, SkipTest
from twisted.python import log
from twisted.internet import utils
from twisted.scripts import tap2rpm

# When we query the RPM metadata, we get back a string we'll have to parse, so
# we'll use suitably rare delimiter characters to split on. Luckily, ASCII
# defines some for us!
RECORD_SEPARATOR = "\x1E"
UNIT_SEPARATOR   = "\x1F"



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

    args.extend(["--tapfile", tapfile])

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

    d = utils.getProcessOutput("rpm",
            ("-q", "--queryformat", queryFormat, "-p", rpmfile))
    d.addCallback(parseTagValues)
    return d



class TestTap2RPM(TestCase):


    def setUp(self):
        return self._checkForRpmbuild()


    def _checkForRpmbuild(self):
        """
        tap2rpm requires rpmbuild; skip tests if rpmbuild is not present.
        """
        def skipTestIfError(result):
            out, err, code = result
            if code != 0 or not out.startswith("RPM version"):
                raise SkipTest("rpmbuild must be present to test tap2rpm")

        d = utils.getProcessOutputAndValue("rpmbuild", ("--version",))
        d.addCallback(skipTestIfError)
        return d


    def _makeTapFile(self, basename="dummy"):
        """
        Makes a temporary .tap file and returns the absolute path.
        """
        path = basename + ".tap"
        handle = open(path, "w")
        handle.write("# Dummy .tap file")
        handle.close()
        return path


    def _verifyRPMTags(self, rpmfile, **tags):
        """
        Checks the given file has the given tags set to the given values.
        """

        d = _queryRPMTags(rpmfile, tags.keys())
        d.addCallback(self.failUnlessEqual, tags)
        return d


    def test_basicOperation(self):
        """
        Calling tap2rpm should produce an RPM and SRPM with default metadata.
        """
        basename = "frenchtoast"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile = self._makeTapFile(basename))

        # Verify the resulting RPMs have the correct tags.
        d = self._verifyRPMTags(rpm,
                NAME=["twisted-%s" % (basename,)],
                VERSION=["1.0"],
                RELEASE=["1"],
                SUMMARY=["A TCP server for %s" % (basename,)],
                DESCRIPTION=["Automatically created by tap2deb"],
            )
        d.addCallback(lambda _: self._verifyRPMTags(srpm,
                NAME=["twisted-%s" % (basename,)],
                VERSION=["1.0"],
                RELEASE=["1"],
                SUMMARY=["A TCP server for %s" % (basename,)],
                DESCRIPTION=["Automatically created by tap2deb"],
            ))

        return d


    def test_protocolOverride(self):
        """
        Setting 'protocol' should change the name of the resulting package.
        """
        basename = "acorn"
        protocol = "banana"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile = self._makeTapFile(basename),
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
        rpm, srpm = _makeRPMs(tapfile = self._makeTapFile(basename),
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
        description="eggplant"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile = self._makeTapFile(),
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
        longDescription="fig"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile = self._makeTapFile(),
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
        version="123.456"

        # Create RPMs based on a TAP file with this name.
        rpm, srpm = _makeRPMs(tapfile = self._makeTapFile(),
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
