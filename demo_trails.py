#!/usr/bin/env python3
"""
Demo script specifically designed to show aircraft trails clearly
"""

import time
import signal
import sys
from datetime import datetime

from config import DISPLAY_CONFIG
from adsb_data import Aircraft
from ascii_renderer import ASCIIRenderer

def create_trail_demo_aircraft():
    """Create demo aircraft with more aggressive movement for better trail visibility"""
    demo_aircraft = []
    
    # Create aircraft that will move more visibly
    aircraft_data = [
        {"icao": "TRAIL1", "lat": 40.2, "lon": -74.8, "altitude": 25000, "speed": 600, "track": 45, "flight": "DEMO01"},
        {"icao": "TRAIL2", "lat": 41.8, "lon": -73.2, "altitude": 15000, "speed": 400, "track": 225, "flight": "DEMO02"},
        {"icao": "TRAIL3", "lat": 40.2, "lon": -73.2, "altitude": 35000, "speed": 500, "track": 135, "flight": "DEMO03"},
    ]
    
    for data in aircraft_data:
        aircraft = Aircraft(data["icao"])
        aircraft.update(data)
        demo_aircraft.append(aircraft)
    
    return demo_aircraft

def animate_aircraft_aggressively(aircraft_list):
    """Animate aircraft with more visible movement to create clear trails"""
    import random
    
    for aircraft in aircraft_list:
        if aircraft.latitude and aircraft.longitude and aircraft.track is not None:
            # More aggressive movement for better trail visibility
            speed_factor = 0.008  # Much faster movement
            track_rad = aircraft.track * 3.14159 / 180
            
            # Move aircraft in their heading direction
            import math
            lat_delta = speed_factor * math.cos(track_rad)
            lon_delta = speed_factor * math.sin(track_rad)
            
            aircraft.latitude += lat_delta
            aircraft.longitude += lon_delta
            
            # Keep within bounds
            bounds = DISPLAY_CONFIG['map_bounds']
            if aircraft.latitude <= bounds['lat_min'] or aircraft.latitude >= bounds['lat_max']:
                aircraft.track = (aircraft.track + 180) % 360  # Reverse direction
            if aircraft.longitude <= bounds['lon_min'] or aircraft.longitude >= bounds['lon_max']:
                aircraft.track = (180 - aircraft.track) % 360  # Bounce off walls
            
            # Clamp to bounds
            aircraft.latitude = max(bounds['lat_min'], min(bounds['lat_max'], aircraft.latitude))
            aircraft.longitude = max(bounds['lon_min'], min(bounds['lon_max'], aircraft.longitude))
            
            # Add to position history for trails
            aircraft.position_history.append(
                (aircraft.latitude, aircraft.longitude, aircraft.last_seen)
            )
            
            # Limit trail length
            if len(aircraft.position_history) > 20:
                aircraft.position_history = aircraft.position_history[-20:]

def main():
    print("🛩️  ADS-B ASCII Radar - Trail Demo")
    print("=" * 50)
    print("Watch the aircraft move and leave trails behind!")
    print("Different styles show trails differently:")
    print("  - Simple: ✈ with · trails")  
    print("  - Detailed: →↓← with • trails and · background")
    print("  - Classic: ><v^ with . trails")
    print()
    print("Press Ctrl+C to exit")
    print("=" * 50)
    
    # Ask user for style
    style_choice = input("Choose style (s=simple, d=detailed, c=classic) [s]: ").lower()
    if style_choice == 'd':
        style = 'detailed'
    elif style_choice == 'c':
        style = 'classic'  
    else:
        style = 'simple'
    
    print(f"\nStarting demo with '{style}' style...")
    time.sleep(1)
    
    demo_aircraft = create_trail_demo_aircraft()
    renderer = ASCIIRenderer(style=style)
    
    running = True
    
    def signal_handler(signum, frame):
        nonlocal running
        running = False
        print("\n\n🛑 Demo ended. Thanks for watching!")
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    iteration = 0
    try:
        while running:
            iteration += 1
            
            # Animate aircraft
            animate_aircraft_aggressively(demo_aircraft)
            
            # Add some status info
            if iteration % 5 == 0:  # Every 5 iterations, show progress
                total_trail_points = sum(len(a.position_history) for a in demo_aircraft)
                print(f"\n🔄 Demo running... Iteration {iteration}, Total trail points: {total_trail_points}")
            
            # Render and display
            renderer.display(demo_aircraft)
            
            # Wait a bit
            time.sleep(0.8)  # Faster updates for better trail visibility
            
    except KeyboardInterrupt:
        pass
    finally:
        print("\n\n✅ Trail demo completed!")
        print(f"Aircraft created {sum(len(a.position_history) for a in demo_aircraft)} trail points total")

if __name__ == "__main__":
    main()
