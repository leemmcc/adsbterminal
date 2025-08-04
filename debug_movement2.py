#!/usr/bin/env python3
"""
Debug the movement calculation in detail
"""

import math
from config import DISPLAY_CONFIG

# Test movement calculation
aircraft_track = 90.0  # East
bounds = DISPLAY_CONFIG['map_bounds']
lat_range = bounds['lat_max'] - bounds['lat_min']
lon_range = bounds['lon_max'] - bounds['lon_min']

print(f"Bounds: {bounds}")
print(f"Lat range: {lat_range}")
print(f"Lon range: {lon_range}")

movement_factor = 0.01
track_rad = math.radians(aircraft_track)

print(f"Track: {aircraft_track}° = {track_rad} radians")

lat_delta = movement_factor * lat_range * math.cos(track_rad)
lon_delta = movement_factor * lon_range * math.sin(track_rad)

print(f"Lat delta: {lat_delta}")
print(f"Lon delta: {lon_delta}")

# Test with initial position
initial_lat, initial_lon = 40.5, -74.5
new_lat = initial_lat + lat_delta
new_lon = initial_lon + lon_delta

print(f"Initial: {initial_lat}, {initial_lon}")
print(f"New: {new_lat}, {new_lon}")
print(f"Movement: {new_lat - initial_lat:.6f}, {new_lon - initial_lon:.6f}")
