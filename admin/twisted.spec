%define name     Twisted
%define version  SVN-trunk
%define release  1tummy
%define prefix   %{_prefix}
%define py_libver 2.3

Summary:	Twisted is an event-based framework for internet applications.
Name:		%{name}
Version:	%{version}
Release:	%{release}
Source:		%{name}-%{version}.tar.bz2
License:	MIT
Group:		System/Libraries
URL:		http://www.twistedmatrix.com/
Requires:	python >= %{py_libver}
BuildRequires:	python-devel
BuildRequires:	pyproject-rpm-macros >= 1.2.0
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
%pyproject_install
%pyproject_save_files %{srcname}

%clean
[ -n "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != / ] && rm -rf "$RPM_BUILD_ROOT"

%files
%defattr(755,root,root)
%doc CREDITS LICENSE README
%{_bindir}/*
%attr(644,-,-) %{_mandir}/man1/*
%{_libdir}/python%{py_libver}/site-packages/twisted/

%files doc
%defattr(-,root,root)
%doc doc/*
