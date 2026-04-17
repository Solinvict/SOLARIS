# Security Policy

Solaris is currently an `alpha` / `research preview`, so security hardening is still evolving.

## Reporting A Vulnerability

Please do not open public issues for suspected security vulnerabilities.

Instead, report them privately to the project maintainers with:

- a short description of the issue
- affected component or file paths
- reproduction steps if available
- expected impact

## Scope Notes

Security-sensitive areas are likely to include:

- web API exposure
- MCP-facing surfaces
- SQLite file handling
- event ingestion and review paths
- any future authentication or multi-tenant deployment patterns

## Response Expectations

The project is actively maintained, but it is not yet staffed like a large commercial product. Reports will be triaged seriously, but response times may vary.

## Deployment Reminder

Solaris is not yet positioned as a hardened internet-facing service by default. If you deploy it beyond local or trusted environments, do so with normal production caution.
