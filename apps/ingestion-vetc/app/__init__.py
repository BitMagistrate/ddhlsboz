"""VETC ingestion micro-service.

Connects to the VETC SFTP drop (or sandbox CSV mirror), validates each
5-minute rollup against `schemas/avro/vetc_hex_5min.avsc`, enforces
k-anonymity ≥ 50 and publishes onto the `vetc.hex.5min` Redpanda topic.
"""
