"""ETA inference micro-service.

Wraps :class:`roadpulse_ml.eta.EtaModel` behind a thin FastAPI surface so the
api-gateway, dispatch dashboard and ml-eval pipelines all talk to a single,
horizontally-scalable inference endpoint.
"""
