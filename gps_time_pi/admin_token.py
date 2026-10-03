"""Create or replace the station admin token.

    sudo python3 -m gps_time_pi.admin_token [--path FILE] [--group gps-time] [--tty-only]

Generates 32 random bytes with `secrets` (URL-safe base64, 43 characters),
shows the token once, and stores only its SHA-256 (mode 0640, readable by the
service group). Run it again to rotate the token; delete the file to disable
admin actions. See docs/api/README.md ("Authentication and request checks").

--tty-only (used by install.sh) writes the token straight to the controlling
terminal (/dev/tty), never to stdout, so it can't end up in a log file or a
pipe (`install.sh | tee install.log`). With no terminal, no token is created.
"""

import argparse
import os
import secrets
import sys
import tempfile

from . import security

TOKEN_BYTES = 32


def new_token():
    """32 bytes from the OS CSPRNG, URL-safe base64 without padding."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def write_token_hash(path, token, group=None):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".admin-token-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(security.hash_token(token) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o640)
        if group and hasattr(os, "chown"):
            import grp
            os.chown(tmp, -1, grp.getgrnam(group).gr_gid)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None, tty_path="/dev/tty"):
    p = argparse.ArgumentParser(description="Create or replace the GPS Time admin token.")
    p.add_argument("--path", default=security.token_path(), help="token hash file (default: %(default)s)")
    p.add_argument("--group", help="group that may read the hash file (the service group, e.g. gps-time)")
    p.add_argument("--tty-only", action="store_true",
                   help="show the token only on the controlling terminal; create nothing without one")
    args = p.parse_args(argv)

    out = sys.stdout
    tty = None
    if args.tty_only:
        try:
            tty = open(tty_path, "w", encoding="utf-8")
        except OSError:
            print("No terminal available: admin token NOT created (admin stays disabled).\n"
                  "Create it interactively on the station:\n"
                  f"    sudo python3 -m gps_time_pi.admin_token --path {args.path}"
                  + (f" --group {args.group}" if args.group else ""), file=sys.stderr)
            return 2
        out = tty
    token = new_token()
    write_token_hash(args.path, token, args.group)
    try:
        print("New GPS Time admin token (shown once; only its hash is stored):\n", file=out)
        print("    " + token + "\n", file=out)
        out.flush()
    finally:
        if tty:
            tty.close()
    print(f"Admin token hash stored: {args.path}"
          + (" (token shown on the terminal only)" if args.tty_only else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
