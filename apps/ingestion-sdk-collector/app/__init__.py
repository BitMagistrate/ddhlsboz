"""Voluntary fleet-SDK collector.

gRPC service that ingests `Probe` streams from opted-in fleet operators. Every
probe is k-anonymised at the hex-bucket level before it leaves the boundary;
raw GPS tracks are never persisted.
"""
