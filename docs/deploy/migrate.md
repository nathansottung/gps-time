# Moving a station to a new SD card or a new Pi

One encrypted file carries the station's config, keys, survey and oscillator log (`gps_time_pi/migrate.py`, #160). Owner's rc.3 list, 2026-11-04.

## What moves, and what doesn't

| Part | Files | On the new card |
|---|---|---|
| Config and survey | `config.json` (the site survey and exact position, privacy mode, display time zone, module settings), `config.json.prev` | used as they are |
| Keys | `station-key` and `.pub` (the station's identity; it signs observation files), `admin-token.sha256` (the same admin token keeps working), the web SDR password hash (`/etc/gps-time-websdr/password`) | replace the ones `install.sh` made |
| Oscillator | `oscillator-log.csv`, `oscillator-profile.json`, `oscillator-profile-reference.json` | same Pi: the log carries on. Another Pi: the station sets the log aside at start and begins a new one, because the log is bound to its board by a serial hash. The profiles stay reference only. |

**Not moved, on purpose:**
- `timing-events.json` and `evidence/`: they describe the old install;
- `sky-obstruction.json`: it describes the old antenna site (useful when the antenna moves);
- chrony's and gpsd's own files: `install.sh` and `fresh-pi-install.md` set those up.

## Export, on the old card

```sh
sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.migrate export ~/station.gtpmig
```

- **It asks for a passphrase twice** (at least 12 characters). The passphrase is never taken from the command line or the environment.
- **The file holds the station's exact position and its private key.** It is encrypted: AES-256-GCM, with the key derived from the passphrase by scrypt (n = 2¹⁵, r = 8, p = 1). It's written 0600 and given to the user who ran `sudo`.
- **Copy it off with `scp`.** It is never offered over HTTP or the web UI. Delete it once it's imported.

## Import, on the new card

After `install.sh` has run on the new card (it creates the users the files belong to):

```sh
sudo systemctl stop gps-time-pi
sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.migrate import ~/station.gtpmig --dry-run
sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.migrate import ~/station.gtpmig
sudo systemctl start gps-time-pi
```

- **It refuses while `gps-time-pi` runs.** The service writes `config.json` when it stops, and would undo the import.
- **Checks first:** it decrypts, verifies every file's SHA-256 against the manifest, and refuses anything it doesn't know. A wrong passphrase, a changed byte or an unknown entry changes nothing.
- **`--dry-run`** says what would be added, replaced or left unchanged, and writes nothing.
- **Nothing is lost:** a file it replaces is kept as `<name>.before-migrate-<UTC time>`.
- **Owners and modes** are the ones `install.sh` gives each file: `config.json` and `station-key` gps-time 0600; `station-key.pub` 0644; `admin-token.sha256` root:gps-time 0640; the oscillator files gps-time 0640; the web SDR password root 0600.
- **Run it twice** and the second run changes nothing.

## After the move

- **Don't run the old card as a station again.** It has the same station key, and two stations must never sign with one key.
- **Same antenna, new site:** the survey in `config.json` is the old site's. Reset it on Administration → Position survey once the antenna is in its new place.
- **The privacy mode moves with the config.** A hidden station stays hidden.

## Not verified

Tested on temporary folders with the station's `cryptography` (`tests/test_migrate.py`, run in the station venv in CI). Not yet run between two real cards or Pis.
