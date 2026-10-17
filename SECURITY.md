# Security and trust boundaries

This is a small manager for running Valve's Windows Steam client with Wine.
Wine is **not a security sandbox**. Programs running inside a prefix may access
files available to your macOS account. Separate prefixes prevent configuration
collisions; they do not isolate hostile software.

The manager uses argument arrays, strips inherited runtime overrides and agent
credentials from child environments, downloads only over HTTPS, and pins SHA-256
digests in `config/runtime-lock.json`. Runtime archives are extracted with Python's
data filter into new directories. Existing runtimes and profiles are not replaced.
No operation disables Gatekeeper, removes quarantine, re-signs vendor software,
uses sudo, modifies the native Steam app, or kills Wine processes.

A checksum verifies the bytes selected for review, not their safety. GitHub's
asset digest and the asset share a publishing trust boundary. The standalone Wine
engine's complete binary-to-source reproducibility has **not** been established.
The free runtime is experimental. CrossOver is optional and its full app signature
is checked against CodeWeavers' team identity before launch.

The manager never reads Steam login files, asks for passwords, or implements its
own authentication. Sign in directly in Valve's Steam client. Private runtime logs
and backup archives can contain account identifiers and game data. Keep them local;
`doctor` emits only selected metadata and does not include raw logs or account IDs.

The manager preserves Steam and game update behavior. It does not bypass entitlement,
DRM, anti-cheat, Cloud conflicts or runtime licenses. No compatibility or account-safety
guarantee is made for a changing multiplayer game.

To report a problem, use GitHub's private vulnerability reporting if enabled. Do
not attach credentials, Steam session files, full bottle archives or raw logs to
public issues. The original installer remains in Git history for auditability but
is removed from this branch; it is not a fallback path.
