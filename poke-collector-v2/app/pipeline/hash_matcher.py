"""Perceptual hash computation and lookup — implemented in Fase 3.

Computes phash/dhash/whash (imagehash) for a normalized card image and
searches app.db.models.CardHash for the closest candidates by combined
Hamming distance.
"""
