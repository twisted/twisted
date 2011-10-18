# -*- test-case-name: twisted.scripts.test.test_tap2rpm -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys, os, shutil, time, glob
import subprocess
import tempfile
import tarfile
from StringIO import StringIO

from twisted.python import usage, log


#################################
#  data that goes in /etc/inittab
initFileData = '''\
#!/bin/sh
#
#  Startup script for a Twisted service.
#
#  chkconfig: - 85 15
#  description: Start-up script for the Twisted service "%(tap_file)s".

PATH=/usr/bin:/bin:/usr/sbin:/sbin

pidfile=/var/run/%(rpm_file)s.pid
rundir=/var/lib/twisted-taps/%(rpm_file)s/
file=/etc/twisted-taps/%(tap_file)s
logfile=/var/log/%(rpm_file)s.log

#  load init function library
. /etc/init.d/functions

[ -r /etc/default/%(rpm_file)s ] && . /etc/default/%(rpm_file)s

#  check for required files
if [ ! -x /usr/bin/twistd ]
then
	echo "$0: Aborting, no /usr/bin/twistd found"
	exit 0
fi
if [ ! -r "$file" ]
then
	echo "$0: Aborting, no file $file found."
	exit 0
fi

#  set up run directory if necessary
if [ ! -d "${rundir}" ]
then
	mkdir -p "${rundir}"
fi


case "$1" in
	start)
		echo -n "Starting %(rpm_file)s: twistd"
		daemon twistd  \\
				--pidfile=$pidfile \\
				--rundir=$rundir \\
				--%(twistd_option)s=$file \\
				--logfile=$logfile
		status %(rpm_file)s
		;;

	stop)
		echo -n "Stopping %(rpm_file)s: twistd"
		kill `cat "${pidfile}"`
		status %(rpm_file)s
		;;

	restart)
		"${0}" stop
		"${0}" start
		;;

    *)
		echo "Usage: ${0} {start|stop|restart|}" >&2
		exit 1
		;;
esac

exit 0
'''

#######################################
#  the data for creating the spec file
specFileData = '''\
Summary:    %(description)s
Name:       %(rpm_file)s
Version:    %(version)s
Release:    1
License:    Unknown
Group:      Networking/Daemons
Source:     %(tarfile_basename)s
BuildRoot:  %%{_tmppath}/%%{name}-%%{version}-root
Requires:   /usr/bin/twistd
BuildArch:  noarch

%%description
%(long_description)s

%%prep
%%setup
%%build

%%install
[ ! -z "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != '/' ] \
		&& rm -rf "$RPM_BUILD_ROOT"
mkdir -p "$RPM_BUILD_ROOT"/etc/twisted-taps
mkdir -p "$RPM_BUILD_ROOT"/etc/init.d
mkdir -p "$RPM_BUILD_ROOT"/var/lib/twisted-taps
cp "%(tap_file)s" "$RPM_BUILD_ROOT"/etc/twisted-taps/
cp "%(rpm_file)s.init" "$RPM_BUILD_ROOT"/etc/init.d/"%(rpm_file)s"

%%clean
[ ! -z "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != '/' ] \
		&& rm -rf "$RPM_BUILD_ROOT"

%%post
/sbin/chkconfig --add %(rpm_file)s
/sbin/chkconfig --level 35 %(rpm_file)s
/etc/init.d/%(rpm_file)s start

%%preun
/etc/init.d/%(rpm_file)s stop
/sbin/chkconfig --del %(rpm_file)s

%%files
%%defattr(-,root,root)
%%attr(0755,root,root) /etc/init.d/%(rpm_file)s
%%attr(0660,root,root) /etc/twisted-taps/%(tap_file)s

%%changelog
* %(date)s %(maintainer)s
- Created by tap2rpm: %(rpm_file)s (%(version)s)
'''

###############################
class MyOptions(usage.Options):
    optFlags = [["unsigned", "u"], ['quiet', 'q']]
    optParameters = [
                     ["tapfile", "t", "twistd.tap"],
                     ["maintainer", "m", "tap2rpm"],
                     ["protocol", "p", None],
                     ["description", "e", None],
                     ["long_description", "l",
                         "Automatically created by tap2rpm"],
                     ["set-version", "V", "1.0"],
                     ["rpmfile", "r", None],
                     ["type", "y", "tap", "type of configuration: 'tap', 'xml, "
                      "'source' or 'python'"],
                    ]

    compData = usage.Completions(
        optActions={"type": usage.CompleteList(["tap", "xml", "source",
                                                "python"]),
                    "rpmfile": usage.CompleteFiles("*.rpm")}
        )

    def postOptions(self):
        """
        Calculate the default values for certain command-line options.
        """
        # Options whose defaults depend on other parameters.
        if self['protocol'] is None:
            base_tapfile = os.path.basename(self['tapfile'])
            self['protocol'] = os.path.splitext(base_tapfile)[0]
        if self['description'] is None:
            self['description'] = "A TCP server for %s" % (self['protocol'],)
        if self['rpmfile'] is None:
            self['rpmfile'] = 'twisted-%s' % (self['protocol'],)

        # Values that aren't options, but are calculated from options and are
        # handy to have around.
        self['twistd_option'] = type_dict[self['type']]
        self['release-name'] = '%s-%s' % (self['rpmfile'], self['set-version'])



type_dict = {
    'tap': 'file',
    'python': 'python',
    'source': 'source',
    'xml': 'xml',
}



##########################
def makeBuildDir():
    """
    Set up the temporary directory for building RPMs.

    Returns: buildDir, a randomly-named subdirectory of baseDir.
    """
    tmpDir = tempfile.mkdtemp()
    #  set up initial directory contents
    os.makedirs(os.path.join(tmpDir, 'RPMS', 'noarch'))
    os.makedirs(os.path.join(tmpDir, 'SPECS'))
    os.makedirs(os.path.join(tmpDir, 'BUILD'))
    os.makedirs(os.path.join(tmpDir, 'SOURCES'))
    os.makedirs(os.path.join(tmpDir, 'SRPMS'))

    log.msg(format="Created RPM build structure in %(path)r",
            path=tmpDir)
    return tmpDir



def setupBuildFiles(buildDir, config):
    """
    Create files required to build an RPM in the build directory.
    """
    # Create the source tarball in the SOURCES directory.
    tarballName = "%s.tar" % (config['release-name'],)
    tarballPath = os.path.join(buildDir, "SOURCES", tarballName)
    tarballHandle = tarfile.open(tarballPath, "w")

    sourceDirInfo = tarfile.TarInfo(config['release-name'])
    sourceDirInfo.type = tarfile.DIRTYPE
    sourceDirInfo.mode = 0755
    tarballHandle.addfile(sourceDirInfo)

    tapFileBase = os.path.basename(config['tapfile'])

    initFileInfo = tarfile.TarInfo(
            os.path.join(
                config['release-name'],
                '%s.init' % config['rpmfile'],
            )
        )
    initFileInfo.type = tarfile.REGTYPE
    initFileInfo.mode = 0755
    initFileRealData = initFileData % {
            'tap_file': tapFileBase,
            'rpm_file': config['release-name'],
            'twistd_option': config['twistd_option'],
        }
    initFileInfo.size = len(initFileRealData)
    tarballHandle.addfile(initFileInfo, StringIO(initFileRealData))

    tapFileHandle = open(config['tapfile'], 'rb')
    tapFileInfo = tarballHandle.gettarinfo(
            arcname=os.path.join(config['release-name'], tapFileBase),
            fileobj=tapFileHandle,
        )
    tapFileInfo.mode = 0644
    tarballHandle.addfile(tapFileInfo, tapFileHandle)

    tarballHandle.close()

    log.msg(format="Created dummy source tarball %(tarballPath)r",
            tarballPath=tarballPath)

    # Create the spec file in the SPECS directory.
    specName = "%s.spec" % (config['release-name'],)
    specPath = os.path.join(buildDir, "SPECS", specName)
    specHandle = open(specPath, "w")
    specFileRealData = specFileData % {
            'description': config['description'],
            'rpm_file': config['rpmfile'],
            'version': config['set-version'],
            'tarfile_basename': tarballName,
            'tap_file': tapFileBase,
            'date': time.strftime('%a %b %d %Y', time.localtime(time.time())),
            'maintainer': config['maintainer'],
            'long_description': config['long_description'],
        }
    specHandle.write(specFileRealData)
    specHandle.close()

    log.msg(format="Created RPM spec file %(specPath)r",
            specPath=specPath)

    return specPath



def run(options=None):
    #  parse options
    try:
        config = MyOptions()
        config.parseOptions(options)
    except usage.error, ue:
         sys.exit("%s: %s" % (sys.argv[0], ue))

    #  create RPM build environment
    tmpDir = makeBuildDir()
    specPath = setupBuildFiles(tmpDir, config)

    #  build rpm
    job = subprocess.Popen([
            "rpmbuild",
            "-vv",
            "--define", "_topdir %s" % (tmpDir,),
            "-ba", specPath,
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, _ = job.communicate()

    # If there was a problem, show people what it was.
    if job.returncode != 0:
        print stdout

    #  copy the RPMs to the local directory
    rpmPath = glob.glob(os.path.join(tmpDir, 'RPMS', 'noarch', '*'))[0]
    srpmPath = glob.glob(os.path.join(tmpDir, 'SRPMS', '*'))[0]
    if not config['quiet']:
        print 'Writing "%s"...' % os.path.basename(rpmPath)
    shutil.copy(rpmPath, '.')
    if not config['quiet']:
        print 'Writing "%s"...' % os.path.basename(srpmPath)
    shutil.copy(srpmPath, '.')

    #  remove the build directory
    shutil.rmtree(tmpDir)

    return [os.path.basename(rpmPath), os.path.basename(srpmPath)]
