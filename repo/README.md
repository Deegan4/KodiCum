# Generated Kodi repository

**Do not edit these files by hand.** This directory is produced by
`tools/build_repo.py` from the add-on sources at the repo root.

`zips/` is the repository datadir that `repository.cumnation` points Kodi at:

```
zips/
├── addons.xml                # merged index of all add-ons
├── addons.xml.md5            # checksum Kodi verifies before downloading
├── plugin.video.cumnation/
│   └── plugin.video.cumnation-<version>.zip
└── repository.cumnation/
    └── repository.cumnation-<version>.zip
```

To regenerate after changing an add-on or bumping its version:

```bash
python3 tools/build_repo.py
```

See the top-level [README](../README.md) for how to add this repository as a
source in Kodi.
