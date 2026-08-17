"""POST /api/v1/scan and /api/v1/scan/confirm — implemented in Fase 3-4.

Will call app.pipeline.resolver to run preprocess -> hash match -> OCR
disambiguation and return the identified card or top-N candidates.
"""
