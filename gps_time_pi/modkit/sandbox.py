"""What a module's own process sets up before any module code is imported.

Layers, from the outside in:

1. The station runs modules only through gps-time-modules.service (systemd
   hardening; a root supervisor that holds nothing but CAP_SETUID/SETGID).
2. drop_privileges(): each module process becomes the unprivileged module user
   (gps-time-mod) with no supplementary groups. File permissions then keep it
   out of the station config (exact position), the admin token and the
   station key, whatever the module's code does.
3. apply_limits(): POSIX resource limits: address space (memory), file size
   (disk), open files, no core dumps.
4. install_guard(): a Python audit hook (it can't be removed once installed)
   that enforces the manifest's permissions for Python code: no sockets
   without network permission, no device files but the declared ones, writes
   only inside the module's storage, no new processes, no native libraries
   through ctypes, no reading of the paths the host denies.

The CPU share, resident memory and output rate are watched by the host
(loader.py), which kills a module that exceeds them. Layer 4 binds Python
code; a C extension could get round it, which is why layers 1-3 are OS-level.
"""

import os
import sys

DEVICE_READ_OK = {"/dev/null", "/dev/zero", "/dev/urandom", "/dev/random"}
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND


class SandboxError(Exception):
    pass


def available():
    """True where every layer the process applies itself is available (POSIX)."""
    try:
        import resource  # noqa: F401
    except ImportError:
        return False
    return os.name == "posix" and hasattr(sys, "addaudithook")


def drop_privileges(user):
    """Become `user` if running as root; refuse to stay root. Returns the user name now in effect."""
    if os.name != "posix":
        return None
    import pwd
    if os.geteuid() == 0:
        if not user:
            raise SandboxError("refusing to run a module as root: no module user given")
        pw = pwd.getpwnam(user)
        if pw.pw_uid == 0:
            raise SandboxError("the module user must not be root")
        os.setgroups([])
        os.setgid(pw.pw_gid)
        os.setuid(pw.pw_uid)
        if os.geteuid() == 0 or os.getegid() == 0:
            raise SandboxError("could not drop root privileges")
    return pwd.getpwuid(os.geteuid()).pw_name


def apply_limits(limits):
    """limits: memory_bytes, file_size_bytes, open_files."""
    import resource

    def cap(which, value):
        soft, hard = resource.getrlimit(which)
        value = int(value)
        if hard != resource.RLIM_INFINITY:
            value = min(value, hard)
        resource.setrlimit(which, (value, value))
    cap(resource.RLIMIT_AS, limits["memory_bytes"])
    cap(resource.RLIMIT_FSIZE, limits["file_size_bytes"])
    cap(resource.RLIMIT_NOFILE, limits.get("open_files", 64))
    cap(resource.RLIMIT_CORE, 0)


def _real(p):
    if isinstance(p, bytes):
        p = os.fsdecode(p)
    return os.path.realpath(p)


def _inside(path, roots):
    return any(path == r or path.startswith(r.rstrip(os.sep) + os.sep) for r in roots)


def make_guard(permissions, write_roots, deny_read):
    """The audit hook enforcing permissions (separate from installing it, for tests)."""
    network = bool(permissions.get("network"))
    devices = {_real(d) for d in permissions.get("devices", [])}
    write_roots = [_real(r) for r in write_roots]
    deny = [_real(p) for p in deny_read]

    def deny_(what):
        raise PermissionError(f"module sandbox: {what}")

    def check_write(path):
        if path is None or isinstance(path, int):
            return
        rp = _real(path)
        if rp in devices or rp in ("/dev/null",):
            return
        if not _inside(rp, write_roots):
            deny_(f"write outside the module's storage: {rp}")

    def hook(event, args):
        if event == "open":
            path, mode, flags = (list(args) + [None, None, None])[:3]
            if path is None or isinstance(path, int):
                return
            rp = _real(path)
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or \
                      (isinstance(flags, int) and flags & _WRITE_FLAGS)
            if _inside(rp, deny):
                deny_(f"no access to {rp}")
            if rp.startswith("/dev/") and rp not in devices and not (rp in DEVICE_READ_OK and not writing):
                deny_(f"device not in the manifest: {rp}")
            if writing:
                check_write(rp)
        elif event == "socket.__new__" and not network:
            deny_("no network permission")
        elif event in ("socket.connect", "socket.bind", "socket.sendto", "socket.getaddrinfo") and not network:
            deny_("no network permission")
        elif event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn",
                       "os.fork", "os.forkpty", "os.startfile", "pty.spawn"):
            deny_("modules may not start processes")
        elif event in ("ctypes.dlopen", "ctypes.dlsym", "ctypes.cdata", "ctypes.call_function"):
            deny_("modules may not load native libraries through ctypes")
        elif event == "os.kill":
            deny_("modules may not signal processes")
        elif event in ("os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.truncate", "os.utime"):
            check_write(args[0] if args else None)
        elif event in ("os.rename", "os.link", "os.symlink"):
            for p in args[:2]:
                check_write(p)
    return hook


def install_guard(permissions, write_roots, deny_read=()):
    sys.dont_write_bytecode = True
    sys.addaudithook(make_guard(permissions, write_roots, deny_read))
