"""Create or replace the station admin token.

    sudo python3 -m gps_time_pi.admin_token [--path FILE] [--group gps-time]

Prints a new random token once and stores only its SHA-256 (mode 0640,
readable by the service group). Run it again to rotate the token; delete the
file to disable admin actions. See docs/api/README.md ("Authentication").
"""

import argparse
import os
import secrets
import sys
import tempfile

from . import security


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


def main(argv=None):
    p = argparse.ArgumentParser(description="Create or replace the GPS Time admin token.")
    p.add_argument("--path", default=security.token_path(), help="token hash file (default: %(default)s)")
    p.add_argument("--group", help="group that may read the hash file (the service group, e.g. gps-time)")
    args = p.parse_args(argv)
    token = secrets.token_urlsafe(24)          # 192 bits
    write_token_hash(args.path, token, args.group)
    print("New GPS Time admin token (shown once; only its hash is stored):")
    print()
    print("    " + token)
    print()
    print(f"Stored hash: {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
