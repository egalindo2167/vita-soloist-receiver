# Contributing

Bug reports and focused pull requests are welcome. For setup problems, start
with [SUPPORT.md](SUPPORT.md). Report vulnerabilities privately through
[SECURITY.md](SECURITY.md#reporting-a-vulnerability).

## Development

1. Fork and clone the repository. Keep your installed host data and Soloist
   credentials outside the checkout. Never commit credentials or recordings.
2. Create a branch for one change. Read [BUILDING.md](docs/dev/BUILDING.md),
   [tests/README.md](tests/README.md), [SECURITY.md](SECURITY.md) and the relevant
   protocol/guide before changing audio, networking, capture or queue selection.
3. Run checks appropriate to the change. State exactly which ran locally and
   which require Windows/Vita hardware. Do not describe mocks as device tests.
4. Include the problem, resulting behavior, validation and remaining limitations
   in the pull request. Update user instructions when controls/setup change.

Keep existing paired TLS authentication, missing-device rejection, process-only
capture and original-queue selection guarantees. Avoid new dependencies for
small features. Dependency changes require exact pins, hash updates, license
notices and verification of native payloads; see [SUPPLY_CHAIN.md](docs/dev/SUPPLY_CHAIN.md).

Project-authored contributions are made under the existing [MIT license](LICENSE).
Keep upstream copyright/license notices intact. Do not add proprietary Soloist
binaries, Spotify keys or third-party drivers to the repository or release.

## Releases

Build/package with [BUILDING.md](docs/dev/BUILDING.md). Follow [PUBLISHING.md](docs/dev/PUBLISHING.md)
for repository/release publication. GitHub Actions verifies and builds artifacts;
it does not publish releases automatically. Do not replace a published version's
assets with different application binaries; use a new version for code changes.
