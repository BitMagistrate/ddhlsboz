"""Trigger feed micro-service.

Signed parametric-insurance events sourced from `flood.hex.score`. Carriers
(Bao Viet, PVI) consume this feed and trigger automatic payouts on policy
threshold breaches. Every event is Ed25519-signed per policy key.
"""
