"""Routing-engine wrapper service.

In production this hands off to OSRM via the C++ library; the Python fallback
exposed here uses :class:`roadpulse_routing.engine.RoutingEngine` against the
seeded HCMC graph so demos keep working when OSRM is being rebuilt.
"""
