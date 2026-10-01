# Publish GPS Time Pi to GitHub

This package intentionally does **not** contain a `.git` directory, credentials, tokens, or GitHub-specific account information.

## 1. Initialize the extracted folder

Open the repository folder in VS Code, then open its integrated terminal:

```bash
git init -b main
git add .
git commit -m "Initial public GPS Time Pi import"
```

Before the commit, review the staged files:

```bash
git status
git diff --cached
```

Confirm that no private configuration, credentials, precise private location, SSH material, or generated runtime data has been added.

## 2. Create the GitHub repository

On GitHub, create a new empty repository named something like `gps-time-pi`.

When GitHub offers to initialize the repository with a README, `.gitignore`, or license, leave those unchecked because this package already contains them.

Copy the repository URL shown by GitHub and run one of the following.

### HTTPS

```bash
git remote add origin https://github.com/YOURUSERNAME/gps-time-pi.git
git push -u origin main
```

### SSH

```bash
git remote add origin git@github.com:YOURUSERNAME/gps-time-pi.git
git push -u origin main
```

## 3. Recommended GitHub settings before calling it stable

- Enable branch protection/rules for `main` once CI is stable.
- Require pull requests for changes to timing, security, and persistence code if other contributors join.
- Enable Dependabot/security alerts if appropriate for the repository.
- Add a concise repository description and topics such as `raspberry-pi`, `ntp`, `chrony`, `gps`, `pps`, and `ham-radio` where appropriate.
- Do not mark the first public commit as a stable release until the foundation items in `docs/PROJECT-SCOPE.md` are resolved or clearly documented as limitations.

## 4. Normal VS Code workflow afterward

```bash
git switch -c feat/example-change
# edit + test
git add .
git commit -m "Describe the change"
git push -u origin feat/example-change
```

Then open a pull request into `main` on GitHub.

## 5. Release packaging

Tag releases only after clean-install and upgrade testing on supported Pi hardware:

```bash
git tag -a vX.Y.Z -m "GPS Time Pi vX.Y.Z"
git push origin vX.Y.Z
```

Use GitHub Releases for downloadable release archives rather than committing generated ZIPs into the repository.
