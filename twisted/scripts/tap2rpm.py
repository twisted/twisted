# -*- test-case-name: twisted.scripts.test.test_tap2rpm -*-

# Copyright (c) 2003-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

import sys, os, shutil, time, glob
import subprocess

from twisted.python import usage
from twisted.scripts import tap2deb


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
BuildRoot:  /var/tmp/%%{name}-%%{version}-root
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
                     ["maintainer", "m", ""],
                     ["protocol", "p", ""],
                     ["description", "e", ""],
                     ["long_description", "l", ""],
                     ["set-version", "V", "1.0"],
                     ["rpmfile", "r", None],
                     ["type", "y", "tap", "type of configuration: 'tap', 'xml, "
                      "'source' or 'python'"],
                    ]

    #zsh_altArgDescr = {"foo":"use this description for foo instead"}
    #zsh_multiUse = ["foo", "bar"]
    #zsh_mutuallyExclusive = [("foo", "bar"), ("bar", "baz")]
    zsh_actions = {"type":"(tap xml source python)",
                   "rpmfile":'_files -g "*.rpm"'}
    #zsh_actionDescr = {"logfile":"log file name", "random":"random seed"}


type_dict = {
    'tap': 'file',
    'python': 'python',
    'source': 'source',
    'xml': 'xml',
}


##########################
def makeBuildDir(baseDir):
    '''
    Set up the temporary directory for building RPMs.

    Returns: buildDir, a randomly-named subdirectory of baseDir.
    '''
    import random, string

    #  make top directory
    oldMask = os.umask(0077)
    while 1:
        tmpDir = os.path.join(baseDir, 'tap2rpm-%s-%s' % ( os.getpid(),
                                        random.randint(0, 999999999) ))
        if not os.path.exists(tmpDir):
            os.makedirs(tmpDir)
            break
    os.umask(oldMask)

    #  set up initial directory contents
    os.makedirs(os.path.join(tmpDir, 'RPMS', 'noarch'))
    os.makedirs(os.path.join(tmpDir, 'SPECS'))
    os.makedirs(os.path.join(tmpDir, 'BUILD'))
    os.makedirs(os.path.join(tmpDir, 'SOURCES'))
    os.makedirs(os.path.join(tmpDir, 'SRPMS'))

    return tmpDir


##########
def run(options=None):
    #  parse options
    try:
        config = MyOptions()
        config.parseOptions(options)
    except usage.error, ue:
         sys.exit("%s: %s" % (sys.argv[0], ue))

    #  set up some useful local variables
    tap_file = config['tapfile']
    base_tap_file = os.path.basename(config['tapfile'])
    protocol = (config['protocol'] or os.path.splitext(base_tap_file)[0])
    rpm_file = config['rpmfile'] or 'twisted-'+protocol
    version = config['set-version']
    maintainer = config['maintainer']
    description = config['description'] or ('A TCP server for %(protocol)s' %
                                            vars())
    long_description = (config['long_description']
                        or "Automatically created by tap2rpm")
    twistd_option = type_dict[config['type']]
    date = time.strftime('%a %b %d %Y', time.localtime(time.time()))
    directory = rpm_file + '-' + version
    python_version = '%s.%s' % sys.version_info[:2]

    #  set up a blank maintainer if not present
    if not maintainer:
        maintainer = 'tap2rpm'

    #  create source archive directory
    tmp_dir = makeBuildDir('/var/tmp')
    source_dir = os.path.join(tmp_dir, directory)
    os.makedirs(source_dir)

    #  populate source directory
    tarfile_name = source_dir + '.tar.gz'
    tarfile_basename = os.path.basename(tarfile_name)
    tap2deb.save_to_file(os.path.join(source_dir, '%s.spec' % rpm_file),
                                      specFileData % vars())
    tap2deb.save_to_file(os.path.join(source_dir, '%s.init' % rpm_file),
                                      initFileData % vars())
    shutil.copy(tap_file, source_dir)

    #  create source tar
    os.system('cd "%(tmp_dir)s"; tar cfz "%(tarfile_name)s" "%(directory)s"'
              % vars())
    
    #  build rpm
    job = subprocess.Popen([
            "rpmbuild",
            "--define", "_topdir %s" % (tmp_dir,),
            "-ta", tarfile_name,
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, _ = job.communicate()

    # If there was a problem, show people what it was.
    if job.returncode != 0:
        print stdout
    
    #  copy the RPMs to the local directory
    rpm_path = glob.glob(os.path.join(tmp_dir, 'RPMS', 'noarch', '*'))[0]
    srpm_path = glob.glob(os.path.join(tmp_dir, 'SRPMS', '*'))[0]
    if not config['quiet']:
        print 'Writing "%s"...' % os.path.basename(rpm_path)
    shutil.copy(rpm_path, '.')
    if not config['quiet']:
        print 'Writing "%s"...' % os.path.basename(srpm_path)
    shutil.copy(srpm_path, '.')
    
    #  remove the build directory
    shutil.rmtree(tmp_dir)

    return [
            os.path.basename(rpm_path),
            os.path.basename(srpm_path),
        ]
