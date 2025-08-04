#!/usr/bin/env python3
"""
Direct test of movement and rendering
"""

from ascii_renderer import create_demo_aircraft, ASCIIRenderer
from main import ADSBRadarApp

# Create demo aircraft and renderer
aircraft = create_demo_aircraft()
renderer = ASCIIRenderer()
app = ADSBRadarApp(demo_mode=True)

print("=== INITIAL STATE ===")
for a in aircraft:
    print(f"{a.icao}: lat={a.latitude:.4f}, lon={a.longitude:.4f}")

# Test multiple animation steps
for step in range(5):
    print(f"\n=== AFTER STEP {step+1} ===")
    app._animate_demo_aircraft(aircraft)
    for a in aircraft:
        print(f"{a.icao}: lat={a.latitude:.4f}, lon={a.longitude:.4f}")
        print(f"  History: {len(a.position_history)} points")
        if len(a.position_history) >= 2:
            last_two = a.position_history[-2:]
            print(f"  Last positions: {last_two}")

print("\n=== TESTING RENDERER ===")
# Test the renderer coordinate conversion
renderer.map_bounds = {'lat_min': 40.0, 'lat_max': 42.0, 'lon_min': -75.0, 'lon_max': -73.0}

for a in aircraft:
    if a.latitude and a.longitude:
        x, y = renderer.lat_lon_to_grid(a.latitude, a.longitude)
        print(f"{a.icao}: lat={a.latitude:.4f}, lon={a.longitude:.4f} -> grid ({x}, {y})")
