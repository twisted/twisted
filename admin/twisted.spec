%define name     Twisted
%define version  SVN-trunk
%define release  1
%define prefix   %{_prefix}

#  This is to work around an issue with some versions of RPM.
%define _unpackaged_files_terminate_build 0

Summary:	Twisted is an event-based framework for internet applications.
Name:		%{name}
Version:	%{version}
Release:	%{release}
Source:		%{name}-%{version}.tar.bz2
License:	MIT
Group:		System/Libraries
URL:		http://www.twistedmatrix.com/
Requires:	python >= 2.3
BuildRequires:	python-devel
BuildRoot:	%{_tmppath}/%{name}-buildroot
Prefix:		%{_prefix}

%description
Twisted is an event-based framework for internet applications.  It includes a
web server, a telnet server, a chat server, a news server, a generic client 
and server for remote object access, and APIs for creating new protocols and
services. Twisted supports integration of the Tk, GTK+, Qt or wxPython event
loop with its main event loop. The Win32 event loop is also supported, as is
basic support for running servers on top of Jython.

%package doc
Summary: Twisted documentation and example programs
Group: Development/Python
%description doc
Twisted is an event-based framework for internet applications.
Install Twisted-doc if you need the API documentation and example programs.

%prep
%setup -n %{name}-%{version}
%build

%install
[ -n "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != / ] && rm -rf "$RPM_BUILD_ROOT"
mkdir -p "$RPM_BUILD_ROOT"

#  remove the generator tests that don't work on 2.4 and older
python -V 2>&1 | grep -q 'Python 2.[01234]' && rm -f twisted/test/generator_failure_tests.py

python setup.py install --optimize=2 --record=installed-files \
      --root="$RPM_BUILD_ROOT"

#  install man pages
mkdir -p "$RPM_BUILD_ROOT"/%{_mandir}/man1/
cp -a doc/core/man/*.1 "$RPM_BUILD_ROOT"/%{_mandir}/man1/

%clean
[ -n "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != / ] && rm -rf "$RPM_BUILD_ROOT"

%post
python -c 'from twisted.plugin import IPlugin, getPlugins; list(getPlugins(IPlugin))' || true

%files
%defattr(755,root,root)
%doc twisted/topfiles/CREDITS LICENSE README
%{_bindir}/*
%attr(644,-,-) %{_mandir}/man1/*
%{_libdir}/python*/site-packages/twisted/

%files doc
%defattr(-,root,root)
%doc doc/*
