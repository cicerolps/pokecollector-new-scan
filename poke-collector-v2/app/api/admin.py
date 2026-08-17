"""POST /api/v1/admin/sync — not implemented yet, deliberately.

app.jobs.sync_catalog already works standalone via `docker exec` or a
systemd timer (PROJECT_SPEC.md 4.1), which is the primary invocation path
for a single-user homelab install. This HTTP trigger would just be a
convenience wrapper around the same job — add it if/when it's actually
wanted, not preemptively.
"""
