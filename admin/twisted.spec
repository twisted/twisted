%define name Twisted
%define libname twisted

%define ver 0.99.3alpha2
%define release 1mdk
%{expand:%%define py_ver %(python -V 2>&1| awk '{print $2}'|cut -d. -f1-2)}

Name:		%{name}
Version:	%{ver}
Release:	%{release}
Source:		%{name}-%{ver}.tar.bz2
Summary:	Twisted is an event-based framework for internet applications.
License:	LGPL
Group:		System/Libraries
URL:		http://www.twistedmatrix.com/
Requires:	libpython%{py_ver}
BuildRequires:	libpython%{py_ver}-devel
BuildRoot:	%{_tmppath}/%{name}-buildroot
Prefix:		%{_prefix}


%description
Twisted is an event-based framework for internet applications.  It includes a
web server, a telnet server, a chat server, a news server, a generic client 
and server for remote object access, and APIs for creating new protocols and
services. Twisted supports integration of the Tk, GTK+, Qt or wxPython event
loop with its main event loop. The Win32 event loop is also supported, as is
basic support for running servers on top of Jython. Twisted works with
Python 2.1 and Python 2.2. Twisted even supports the CVS versions of Python, 
so it is ready for Python 2.3.

%package doc
Summary: Twisted documentation and example programs
Group: Development/Python
%description doc
Twisted is an event-based framework for internet applications.
Install Twisted-doc if you need the API documentation and example programs.

%prep
%setup -q %{name}-%{ver}

%build
python setup.py build

%install
mkdir -p $RPM_BUILD_ROOT/%{_mandir}/man1/
cp doc/man/* $RPM_BUILD_ROOT/%{_mandir}/man1/
python setup.py install --prefix $RPM_BUILD_ROOT/%{_prefix}

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%{_bindir}/*
%{_mandir}/*
%{_libdir}/python%{py_ver}/site-packages/%{libname}/*
%doc ChangeLog CREDITS ERRATA LICENSE README TODO

%files doc
%defattr(-,root,root)
%doc doc/*
