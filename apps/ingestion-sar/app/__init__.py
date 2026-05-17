"""Sentinel-1 SAR ingestion.

Tiles Sentinel-1 GRD scenes from Copernicus Data Space, classifies each pixel
as water / not-water with a thresholded ratio (VV/VH), rolls up to H3 res 8 and
publishes ``hex → water_prior`` to the feature store.
"""
