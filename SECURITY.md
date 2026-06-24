# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 2.2.x   | ✅ Active  |
| 2.1.x   | ⚠️ Security fixes only |
| < 2.1   | ❌ End of life |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Email **devansh.jay.singh@gmail.com** with the subject line `[SECURITY] ChronoMap — <short description>`.

Include:
- A description of the vulnerability
- Steps to reproduce it
- The potential impact
- Your suggested fix (optional)

You will receive an acknowledgement within **48 hours** and a status update within **7 days**.

We follow responsible disclosure: we will coordinate a fix and public disclosure timeline with you before publishing anything. Credit will be given in the release notes unless you prefer to remain anonymous.

## Scope

In scope:
- Remote code execution via ChronoMap's pickle loading (`load_pickle`)
- Denial of service via malformed inputs to public API methods
- Memory exhaustion bypassing `max_memory_mb` limits
- Unsafe deserialization

Out of scope:
- Issues in Python itself or third-party libraries that ChronoMap uses
- Issues that require physical access to the host machine
