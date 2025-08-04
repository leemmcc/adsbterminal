#!/usr/bin/env python3
"""
Debug script to test aircraft movement
"""

from ascii_renderer import create_demo_aircraft
from main import ADSBRadarApp

# Create demo aircraft
aircraft = create_demo_aircraft()

print("Initial positions:")
for a in aircraft:
    print(f"{a.icao}: lat={a.latitude:.4f}, lon={a.longitude:.4f}, track={a.track}")

# Create app and test animation  
app = ADSBRadarApp(demo_mode=True)

print("\nAfter 1 animation step:")
app._animate_demo_aircraft(aircraft)
for a in aircraft:
    print(f"{a.icao}: lat={a.latitude:.4f}, lon={a.longitude:.4f}, track={a.track}")
    print(f"  Position history length: {len(a.position_history)}")

print("\nAfter 2nd animation step:")
app._animate_demo_aircraft(aircraft)
for a in aircraft:
    print(f"{a.icao}: lat={a.latitude:.4f}, lon={a.longitude:.4f}, track={a.track}")
    print(f"  Position history length: {len(a.position_history)}")
