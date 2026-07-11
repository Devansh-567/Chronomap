# Security Policy

ChronoMap is an in-memory data structure with no network I/O, so most
traditional "security" concerns (auth, injection, etc.) don't apply
directly. That said, if you find something that could let untrusted
input crash a process, corrupt data, or execute code unexpectedly
(e.g. via `load_pickle` — pickle deserialization of untrusted data is
never safe, in any library), please report it privately rather than
opening a public issue.

**Contact:** devansh.jay.singh@gmail.com

Please include:
- A description of the issue and its impact
- Steps to reproduce
- Affected version(s)

We'll acknowledge within a few days and keep you updated as it's worked on.
