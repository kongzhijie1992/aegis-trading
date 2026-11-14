# Desktop repository migration — 14 November 2026

The source release archive was SHA-256 verified against its release manifest and
copied into the previously empty aegis-trading repository root. The existing .git
metadata and remote were preserved. Account configuration, runtime databases,
logs, environments and built wheel caches were excluded.

## Review 1: structure and safety

Checked root-level .github placement, independent src-layout libraries, unchanged
paper-only execution, preserved order-key semantics, no private runtime/config
files, and editable dependency paths relative to the repository. The original
workspace remains the owner of its existing local account settings and journal;
no journal was reset or transferred into source control. A fresh checkout must
be configured deliberately before any broker use.

## Review 2: portability and release behavior

Updated platform naming and remote activation documentation. Found and corrected
a release-script path that would have written to a sibling Desktop/outputs folder;
release artifacts now remain within this repository at dist/release. Recheck
installation, quality gates and built-wheel portability after migration. Remote
CI activation and branch protection require GitHub-side verification after push.

## Completed validation

Fresh Poetry installation succeeded from the lock in the Desktop clone. All 41
tests, formatting/lint checks, strict typing for the five core libraries, package
boundaries, workflow checks and every per-library coverage gate passed. Rebuilt
12 own wheels, downloaded hash-verified runtime dependencies, and passed both the
minimal strategy-only install and all 41 tests from clean installed wheels. The
dependency audit found no known vulnerabilities. Checked all 113 candidate source
files: private account config, runtime history, environments and generated build
outputs are excluded by Git. Added LF/UTF-8 editor and Git settings. Both migration
review passes are complete. Changes remain local and uncommitted; no push, broker
connection, brokerage order or hosted deployment was performed during migration.
