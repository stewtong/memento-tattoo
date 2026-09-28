"""Evaluation harness for memento-tattoo retrieval.

Kept outside the package so the CLI stays dependency-free and never calls a
model. Optional dependencies (an embedding model for the A4 baseline) are
imported only by the modules that need them.
"""
