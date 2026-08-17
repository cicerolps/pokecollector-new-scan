"""Pipeline orchestration — implemented in Fase 3-4.

Runs preprocess -> hash_matcher -> (conditionally) ocr_disambiguator and
decides the final confidence / candidate list per PROJECT_SPEC.md section 3.4.
"""
