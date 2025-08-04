#!/usr/bin/env python3
"""
ADS-B ASCII Art Radar
Main application for displaying aircraft as ASCII art in the terminal
"""

import sys
import time
import argparse
import signal
import logging
from typing import Optional

from config import ADSB_CONFIG, DISPLAY_CONFIG, ASCII_STYLES
from adsb_data import ADSBDataFetcher
from ascii_renderer import ASCIIRenderer, create_demo_aircraft

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ADSBRadarApp:
    """Main application class for ADS-B ASCII radar"""
    
    def __init__(self, demo_mode: bool = False, style: str = 'simple'):
        self.demo_mode = demo_mode
        self.running = False
        self.data_fetcher = None if demo_mode else ADSBDataFetcher()
        self.renderer = ASCIIRenderer(style=style)
        self.update_interval = ADSB_CONFIG['update_interval']
        
        self.speed_multiplier = 1  # Default speed multiplier
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def set_bounds(self, lat_min: float, lon_min: float, lat_max: float, lon_max: float):
        """Set the geographic bounds for the display"""
        DISPLAY_CONFIG['map_bounds'].update({
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lon_min': lon_min,
            'lon_max': lon_max,
        })
        self.renderer.map_bounds = DISPLAY_CONFIG['map_bounds']
        logger.info(f"Set bounds to: {lat_min},{lon_min} -> {lat_max},{lon_max}")
    
    def set_data_source(self, url: str):
        """Set the ADS-B data source URL"""
        ADSB_CONFIG['dump1090_url'] = url
        logger.info(f"Set data source to: {url}")
    
    def set_update_interval(self, interval: int):
        """Set the update interval in seconds"""
        self.update_interval = max(1, interval)  # Minimum 1 second
        logger.info(f"Set update interval to: {self.update_interval} seconds")
    
    def run_demo(self):
        """Run in demo mode with fake aircraft"""
        print("ADS-B ASCII Radar - Demo Mode")
        print(f"Speed multiplier: {self.speed_multiplier}x")
        print("Press Ctrl+C to exit")
        print("=" * 50)
        
        demo_aircraft = create_demo_aircraft()
        
        try:
            self.running = True
            while self.running:
                # Simulate aircraft movement
                self._animate_demo_aircraft(demo_aircraft)
                
                # Render and display
                self.renderer.display(demo_aircraft)
                
                # Wait for next update
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            pass
        finally:
            print("\nDemo mode ended.")
    
    def _animate_demo_aircraft(self, aircraft_list):
        """Animate demo aircraft positions"""
        import random
        
        for aircraft in aircraft_list:
            if aircraft.latitude and aircraft.longitude and aircraft.track is not None:
                # Simple movement simulation
                speed_factor = 0.01 * self.speed_multiplier
                track_rad = aircraft.track * 3.14159 / 180
                
                # Move aircraft slightly in their heading direction
                lat_delta = speed_factor * (aircraft.ground_speed or 400) / 60 * 0.00144
                lon_delta = speed_factor * (aircraft.ground_speed or 400) / 60 * 0.00144
                
                aircraft.latitude += lat_delta * abs(1 - abs(track_rad - 1.57) / 1.57)
                aircraft.longitude += lon_delta * (1 if track_rad < 1.57 or track_rad > 4.71 else -1)
                
                # Keep within bounds
                bounds = DISPLAY_CONFIG['map_bounds']
                aircraft.latitude = max(bounds['lat_min'], min(bounds['lat_max'], aircraft.latitude))
                aircraft.longitude = max(bounds['lon_min'], min(bounds['lon_max'], aircraft.longitude))
                
                # Add to position history for trails
                aircraft.position_history.append(
                    (aircraft.latitude, aircraft.longitude, aircraft.last_seen)
                )
                
                # Randomly adjust heading slightly
                if random.random() < 0.1:
                    aircraft.track = (aircraft.track + random.randint(-10, 10)) % 360
    
    def run_live(self):
        """Run with live ADS-B data"""
        print("ADS-B ASCII Radar - Live Mode")
        print("Press Ctrl+C to exit")
        print("=" * 50)
        
        if not self.data_fetcher:
            print("Error: Data fetcher not initialized")
            return False
        
        # Test connection
        print("Testing ADS-B data connection...")
        if not self.data_fetcher.update():
            print("Warning: Could not connect to ADS-B data source")
            print(f"Trying to connect to: {ADSB_CONFIG['dump1090_url']}")
            print("Make sure dump1090 or another ADS-B source is running")
            
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                return False
        else:
            print("Connection successful!")
        
        try:
            self.running = True
            while self.running:
                # Update aircraft data
                success = self.data_fetcher.update()
                if not success:
                    logger.warning("Failed to update aircraft data")
                
                # Get aircraft within bounds
                bounds = DISPLAY_CONFIG['map_bounds']
                aircraft_list = self.data_fetcher.get_aircraft_in_bounds(
                    bounds['lat_min'], bounds['lat_max'],
                    bounds['lon_min'], bounds['lon_max']
                )
                
                # Render and display
                self.renderer.display(aircraft_list)
                
                # Show connection status
                if not success:
                    print("WARNING: Data connection lost - retrying...")
                
                # Wait for next update
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            pass
        finally:
            print("\nLive mode ended.")
        
        return True
    
    def run(self):
        """Run the application"""
        if self.demo_mode:
            self.run_demo()
        else:
            return self.run_live()


def parse_bounds(bounds_str: str):
    """Parse bounds string like 'lat_min,lon_min,lat_max,lon_max'"""
    try:
        parts = bounds_str.split(',')
        if len(parts) != 4:
            raise ValueError("Bounds must have 4 values")
        
        lat_min, lon_min, lat_max, lon_max = map(float, parts)
        
        if lat_min >= lat_max or lon_min >= lon_max:
            raise ValueError("Invalid bounds: min values must be less than max values")
        
        return lat_min, lon_min, lat_max, lon_max
    
    except (ValueError, TypeError) as e:
        raise argparse.ArgumentTypeError(f"Invalid bounds format: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="ADS-B ASCII Art Radar - Display aircraft as ASCII art",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --demo                    # Run demo mode
  python main.py --style detailed         # Use detailed ASCII style
  python main.py --bounds 40,-75,42,-73   # Set custom map bounds
  python main.py --url http://pi:8080/data/aircraft.json  # Custom data source
  python main.py --interval 2             # Update every 2 seconds
        """
    )
    
    parser.add_argument('--demo', action='store_true',
                       help='Run in demo mode with simulated aircraft')
    
    parser.add_argument('--style', choices=list(ASCII_STYLES.keys()),
                       default='simple',
                       help='ASCII art style to use')
    
    parser.add_argument('--bounds', type=parse_bounds,
                       help='Map bounds as lat_min,lon_min,lat_max,lon_max')
    
    parser.add_argument('--url', type=str,
                       help='ADS-B data source URL')
    
    parser.add_argument('--interval', type=int, default=ADSB_CONFIG['update_interval'],
                       help='Update interval in seconds')
    
    parser.add_argument('--speed', type=int, default=1,
                       help='Set movement speed multiplier for demo mode')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    
    # Create and configure application
    app = ADSBRadarApp(demo_mode=args.demo, style=args.style)
    
    if args.bounds:
        app.set_bounds(*args.bounds)
    
    if args.url:
        app.set_data_source(args.url)
    
    app.set_update_interval(args.interval)

    # Set speed multiplier
    app.speed_multiplier = args.speed if args.demo else 1

    # Update DISPLAY_CONFIG to reflect current mode
    DISPLAY_CONFIG['demo_mode'] = args.demo
    DISPLAY_CONFIG['speed_multiplier'] = app.speed_multiplier

    # Run the application
    try:
        success = app.run()
        return 0 if success else 1
    
    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
