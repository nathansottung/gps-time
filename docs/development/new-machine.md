# Setting up a new development machine

How to get from a fresh laptop to a working GPS Time checkout with passing tests. Windows (PowerShell) is the primary path; macOS/Linux equivalents are noted. Nothing here touches a Raspberry Pi. For deploying, see `raspberry-pi-deploy.md`.

## 1. Install the tools

| Tool | Version | Used for |
|---|---|---|
| Git | any recent | version control |
| GitHub CLI (`gh`) | any recent | auth, PRs, deriving your noreply address |
| Python | 3.11 or newer (CI uses 3.11) | server, tests, demo (standard library only) |
| Node.js | 22 LTS (matches `web/.mise.toml` and CI) | web UI build |
| pnpm | 10.34.3, via corepack (pinned in `web/package.json`) | web UI dependencies |
| VS Code | optional | `.vscode/tasks.json` has demo, compile and build tasks |

On Windows with winget:

```powershell
winget install Git.Git GitHub.cli Python.Python.3.11 OpenJS.NodeJS.LTS
```

`OpenJS.NodeJS.LTS` installs the *current* LTS, which may be newer than 22. The web UI builds and type-checks on Node 24 as well. CI pins 22. If you use [mise](https://mise.jdx.dev/), `mise install` inside `web/` installs exactly the pinned Node and pnpm.

Corepack ships with Node 22 and 24. If `corepack` is missing (later Node releases may not bundle it), run `npm install -g corepack`.

## 2. Sign in to GitHub

```powershell
gh auth login          # GitHub.com → HTTPS → authenticate in the browser
```

The repository is private, so cloning needs this.

## 3. Clone with line-ending conversion OFF

Git for Windows usually enables `core.autocrlf`, which converts files to CRLF on checkout. That breaks shell scripts and systemd units bundled for the Pi. Turn it off **as part of the clone**, so the very first checkout is already correct:

```powershell
gh repo clone nathansottung/gps-time -- -c core.autocrlf=false
cd gps-time
```

(Plain git: `git clone -c core.autocrlf=false https://github.com/nathansottung/gps-time.git`.) The `-c` setting is saved in the new repo's `.git/config`.

Git for Windows sets `core.autocrlf=true` in its *system* config (`C:\Program Files\Git\etc\gitconfig`), so this matters even when you never set it yourself. A clone without the flag checked out about 150 files with CRLF endings.

**Keep the clone path short on Windows.** pnpm nests packages deeply under `web/node_modules/.pnpm/…`. In a long parent folder, some files exceed Windows' 260-character path limit, and `pnpm run build` then fails with `ERR_PACKAGE_IMPORT_NOT_DEFINED` (`#module-sync-enabled`); a 283-character path failed in testing. Either:
- clone into a folder whose full path is at most about 64 characters, e.g. `C:\dev\gps-time` (tested: `C:\Users\<name>\Documents\Software Development\pi_ntp\gps-time`, 64 characters, builds); or
- enable long paths, from an elevated PowerShell:
  ```powershell
  New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
  git config --system core.longpaths true
  ```

Check that every tracked file has LF line endings in the working tree. This should print nothing:

```powershell
git ls-files --eol | Select-String "w/crlf"      # bash: git ls-files --eol | grep w/crlf
```

## 4. Commit identity: repo-local GitHub noreply address

Commits must not carry a personal email. Set the identity **for this repository only** (no `--global`):

```powershell
git config user.name "nathansottung"
$email = gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"'
git config user.email $email
git config --show-origin --get user.email        # must show .git/config and a ...@users.noreply.github.com address
```

bash/zsh:

```sh
git config user.name "nathansottung"
git config user.email "$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"')"
```

Optionally, turn on GitHub's "Block command line pushes that expose my email" (Settings → Emails) as a backstop.

## 5. Python

No third-party packages are needed for the server, the demo or the tests (standard library only). Skyfield is needed only for astronomy on the Pi, where `install.sh` installs it.

```powershell
python --version                                  # 3.11+
python -m compileall gps_time_pi tools tests
python tools/generate_config.py --help
python -m unittest discover -s tests -t . -v
```

On Windows, expect `OK (skipped=1)`. The real-SIGTERM test needs POSIX and runs in CI (Ubuntu). The tests need no GNSS, chrony, Internet or root. They never read the host's chrony or boot configuration.

## 6. Web UI (pnpm)

```powershell
cd web
corepack pnpm install --frozen-lockfile   # install-time network only
corepack pnpm run typecheck
corepack pnpm run build                   # output: web/dist (git-ignored)
corepack pnpm run dev                     # http://127.0.0.1:5173 (loopback only)
cd ..
```

`corepack enable` lets you type `pnpm` directly. On Windows it may need an elevated shell; `corepack pnpm …` works without it.

## 7. Run the desktop demo

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-demo.ps1
```

This opens http://127.0.0.1:8080/ with sample data (`.dev/` holds demo config; it is git-ignored). The timing-chain scenarios are at `/api/timing-chain?scenario=pps_path_anomaly` (others: `pps_selected`, `acquiring`, `network_failover`, `holdover`, …).

## 8. Working agreement

`CLAUDE.md` at the repository root holds the project rules and workflow:
- one branch per task, merged with a merge commit after CI;
- docs updated in the same branch;
- provenance labels and UNKNOWN;
- no real coordinates.

Claude Code reads it automatically; human contributors should read it too.

## 9. Not in the repository

- **The dashboard concept mockup PNG** is kept outside the repository on purpose (unrecorded provenance). Copy it by hand if you need it. It doesn't belong in `docs/`.
- **Claude Code's per-machine memory** doesn't transfer. The rules it held are in `CLAUDE.md`.
- **Pi access** (SSH keys, the Pi's address) is per machine. Set it up when you deploy.

## 10. Check everything is backed up (any machine)

```sh
git status                              # nothing to commit, working tree clean
git stash list                          # empty
git log --branches --not --remotes      # empty: every local commit exists on GitHub
git status --ignored --short            # only build/runtime output (__pycache__, web/node_modules, web/dist, .dev, dist)
```
