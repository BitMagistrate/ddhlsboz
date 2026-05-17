"""Weather ingestion micro-service.

Polls NMHS bulletins and GSMaP precipitation grids, projects values onto VN
administrative districts and publishes onto `weather.district.hourly`.
"""
