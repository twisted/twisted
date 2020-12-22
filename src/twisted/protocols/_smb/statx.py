# obtained from https://github.com/ipfs-shipyard/py-datastore/datastore/filesystem/util/statx.py
# no licence header in file but overall project MIT
import collections
import ctypes
import ctypes.util
import errno
import typing
import os


class Mask(ctypes.c_uint):
	# Basic stats (stuff also part of `os.stat()`)
	TYPE        = 0x00000001  # Want/got stx_mode & S_IFMT
	MODE        = 0x00000002  # Want/got stx_mode & ~S_IFMT
	NLINK       = 0x00000004  # Want/got stx_nlink
	UID         = 0x00000008  # Want/got stx_uid
	GID         = 0x00000010  # Want/got stx_gid
	ATIME       = 0x00000020  # Want/got stx_atime
	MTIME       = 0x00000040  # Want/got stx_mtime
	CTIME       = 0x00000080  # Want/got stx_ctime
	INO         = 0x00000100  # Want/got stx_ino
	SIZE        = 0x00000200  # Want/got stx_size
	BLOCKS      = 0x00000400  # Want/got stx_blocks
	BASIC_STATS = 0x000007FF  # The stuff in the normal stat struct
	
	# Extensions
	BTIME       = 0x00000800  # Want/got stx_btime
	ALL         = 0x00000FFF  # All currently supported flags
	_RESERVED   = 0x80000000  # Reserved for future struct statx expansion


# Special FD for value for meaning “no FD”
AT_FDCWD = -100

# Path lookup flags applicable for `statx`
AT_SYMLINK_NOFOLLOW = 0x100  # Do not resolve symbolic links
AT_REMOVEDIR        = 0x200  # Remove directory instead of unlinking file
AT_NO_AUTOMOUNT     = 0x800  # Suppress terminal automount traversal
AT_EMPTY_PATH       = 0x1000  # Allow empty relative pathname

# Accuracy of timestamps required in case of network file systems
AT_STATX_SYNC_TYPE    = 0x6000  # Type of synchronisation required from statx():
AT_STATX_SYNC_AS_STAT = 0x0000  # - Do whatever stat() does
AT_STATX_FORCE_SYNC   = 0x2000  # - Force the attributes to be sync'd with the server
AT_STATX_DONT_SYNC    = 0x4000  # - Don't sync attributes with the server


class struct_statx_timestamp(ctypes.Structure):
	_fields_ = [
		# Base file attributes
		("tv_sec",     ctypes.c_uint64),
		("tv_nsec",    ctypes.c_uint32),
		("__reserved", ctypes.c_uint32),
	]


class struct_statx(ctypes.Structure):
	_fields_ = [
		# Base file attributes
		("stx_mask",       Mask),
		("stx_blksize",    ctypes.c_uint32),
		("stx_attributes", ctypes.c_uint64),
		("stx_nlink",      ctypes.c_uint32),
		("stx_uid",        ctypes.c_uint32),
		("stx_gid",        ctypes.c_uint32),
		("stx_mode",       ctypes.c_uint16),
		("__spare0",       ctypes.c_uint16 * 1),
		("stx_ino",        ctypes.c_uint64),
		("stx_size",       ctypes.c_uint64),
		("stx_blocks",     ctypes.c_uint64),
		("stx_attributes_mask", ctypes.c_uint64),
		
		# Timestamps
		("stx_atime", struct_statx_timestamp),
		("stx_btime", struct_statx_timestamp),
		("stx_ctime", struct_statx_timestamp),
		("stx_mtime", struct_statx_timestamp),
		
		# Device ID (if device file)
		("stx_rdev_major", ctypes.c_uint32),
		("stx_rdev_minor", ctypes.c_uint32),
		("stx_dev_major",  ctypes.c_uint32),
		("stx_dev_minor",  ctypes.c_uint32),
		
		# Spare space
		("__spare2", ctypes.c_uint64 * 14),
	]


assert ctypes.sizeof(struct_statx) == 0x100



# Only works on Linux with GLibC afaik
_func: typing.Optional[typing.Any]
if os.name == "posix" and os.uname().sysname == "Linux":
	try:
		_libc = ctypes.CDLL("libc.so.6", use_errno=True)
		try:
			_error = None
			_func  = _libc.statx
			_func.argtypes = (
				ctypes.c_int,     # dirfd
				ctypes.c_char_p,  # pathname
				ctypes.c_int,     # flags
				ctypes.c_uint,    # mask
				ctypes.POINTER(struct_statx)
			)
		except AttributeError:  # Probably not GLibC 2.28+
			_error = NotImplementedError("statx: C library does not expose symbol 'statx'")
			_func  = None
	except OSError:
		_error = NotImplementedError("statx: No C library found at name 'libc.so.6'")
		_func = None
else:
	_error = NotImplementedError("statx: System call is Linux-specific")
	_func  = None



# We have define our own `stat_result` here as there is no way to add fields
# to `os.stat_result` unless Python thinks they should be there
_stat_result = collections.namedtuple("stat_result", [
	# Standard attributes
	"st_mode",
	"st_ino",
	"st_dev",
	"st_nlink",
	"st_uid",
	"st_gid",
	"st_size",
	"st_atime",
	"st_mtime",
	"st_ctime",
	
	# Platform-dependant attributes
	"st_blksize",
	"st_blocks",
	"st_rdev",
	"st_flags",
	
	# High-precision timestamps
	"st_atime_ns",
	"st_mtime_ns",
	"st_ctime_ns",
	
	# Birthtime extension (otherwise only available on FreeBSD/macOS)
	"st_birthtime",
	"st_birthtime_ns"
], defaults=[None, None, None, None, None, None, None, None, None])


class stat_result(_stat_result):
	def __repr__(self):
		return (f"{self.__module__}.{type(self).__qualname__}("
		        f"st_mode={self.st_mode!r}, "
		        f"st_ino={self.st_ino!r}, "
		        f"st_dev={self.st_dev!r}, "
		        f"st_nlink={self.st_nlink!r}, "
		        f"st_uid={self.st_uid!r}, "
		        f"st_gid={self.st_gid!r}, "
		        f"st_size={self.st_size!r}, "
		        f"st_atime={self.st_atime!r}, "
		        f"st_mtime={self.st_mtime!r}, "
		        f"st_ctime={self.st_ctime!r})")



def statx(
		dirfd: int      = AT_FDCWD,
		pathname: bytes = b"",
		flags: int      = AT_STATX_SYNC_AS_STAT,
		mask: int       = Mask.BASIC_STATS
) -> struct_statx:
	"""Low-level wrapper around the ``statx(2)`` Linux system call"""
	global _error
	if _error:
		raise _error
	assert _func
	
	statx_data = struct_statx()
	
	result = _func(dirfd, pathname, flags, mask, ctypes.byref(statx_data))
	if result < 0:
		if ctypes.get_errno() == errno.ENOSYS:  # Kernel does not support syscall
			_error = NotImplementedError("statx: System call not supported by this version of Linux")
			raise _error
		raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
	
	return statx_data


def stat(path, *, dir_fd: int = None, follow_symlinks: bool = True) \
    -> typing.Union[os.stat_result, stat_result]:
	"""High-level wrapper around the ``statx(2)`` system call, that delegates
	to :func:`os.stat` on other platforms, but provides `st_birthtime` on Linux."""
	def ts_to_nstime(ts):
		return ts.tv_sec * 1000_000_000 + ts.tv_nsec
	
	if not _error:
		try:
			stx_flags = AT_STATX_SYNC_AS_STAT
			
			if isinstance(path, int):
				stx_dirfd  = path
				stx_path   = b""
				stx_flags |= AT_EMPTY_PATH
			else:
				stx_dirfd = dir_fd if dir_fd is not None else AT_FDCWD
				stx_path  = os.fsencode(os.fspath(path))
			
			if not follow_symlinks:
				stx_flags |= AT_SYMLINK_NOFOLLOW
			
			stx_result = statx(stx_dirfd, stx_path, stx_flags, Mask.BASIC_STATS | Mask.BTIME)
			assert (~stx_result.stx_mask.value & (Mask.BASIC_STATS & ~Mask.BLOCKS)) == 0
			
			st_blocks       = None
			st_birthtime    = None
			st_birthtime_ns = None
			if stx_result.stx_mask.value & Mask.BLOCKS:
				st_blocks = stx_result.stx_blocks
			if stx_result.stx_mask.value & Mask.BTIME:
				st_birthtime    = stx_result.stx_btime.tv_sec
				st_birthtime_ns = ts_to_nstime(stx_result.stx_btime)
			
			
			return stat_result(
				# Standard struct data
				stx_result.stx_mode,
				stx_result.stx_ino,
				os.makedev(stx_result.stx_dev_major, stx_result.stx_dev_minor),
				stx_result.stx_nlink,
				stx_result.stx_uid,
				stx_result.stx_gid,
				stx_result.stx_size,
				stx_result.stx_atime.tv_sec,
				stx_result.stx_ctime.tv_sec,
				stx_result.stx_mtime.tv_sec,
				
				# Extended (platform-dependant) attributes
				stx_result.stx_blksize,
				os.makedev(stx_result.stx_rdev_major, stx_result.stx_rdev_minor),
				stx_result.stx_attributes,
				st_blocks,
				
				# High-precision timestamps
				ts_to_nstime(stx_result.stx_atime),
				ts_to_nstime(stx_result.stx_ctime),
				ts_to_nstime(stx_result.stx_mtime),
				
				# Non-standard birth time value
				st_birthtime,
				st_birthtime_ns
			)
		except NotImplementedError:
			pass
	
	return os.stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)


def lstat(path, *, dir_fd=None):
	"""Alias for ``stat(…, follow_symlinks=False)`."""
	return stat(path, dir_fd=dir_fd, follow_symlinks=False)


def fstat(fd):
	"""Alias for ``stat(fd)`."""
	return stat(fd)
