"""POST /api/v1/admin/sync — implemented in Fase 2.

Triggers app.jobs.sync_catalog for on-demand catalog/hash refresh, as an
alternative to the systemd timer.
"""
