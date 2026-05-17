"""Flood scoring micro-service.

Wraps :class:`roadpulse_ml.flood.FloodDetector` and re-publishes Bayesian
posterior scores onto the ``flood.hex.score`` Kafka topic every 5 minutes.
"""
