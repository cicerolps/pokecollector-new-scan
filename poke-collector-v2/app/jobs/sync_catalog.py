"""Catalog/hash sync batch job — implemented in Fase 2.

Uses app.integrations.pokemontcg_client and app.integrations.tcgdex_client to
list sets/cards, download reference images into Settings.catalog_dir, compute
perceptual hashes, and upsert app.db.models.Card / CardHash. Runs
incrementally — only new sets/uncached cards are processed.
"""
