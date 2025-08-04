"""
ADS-B Data Fetcher and Processor
Handles fetching aircraft data from various ADS-B sources
"""

import json
import time
import socket
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from config import ADSB_CONFIG, PROCESSING_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Aircraft:
    """Represents a single aircraft with its current and historical data"""
    
    def __init__(self, icao: str):
        self.icao = icao
        self.callsign = ""
        self.latitude = None
        self.longitude = None
        self.altitude = None
        self.ground_speed = None
        self.track = None  # heading in degrees
        self.vertical_rate = None
        self.last_seen = datetime.now()
        self.position_history = []  # List of (lat, lon, timestamp) tuples
        
    def update(self, data: Dict):
        """Update aircraft data from ADS-B message"""
        self.last_seen = datetime.now()
        
        if 'lat' in data and 'lon' in data and data['lat'] and data['lon']:
            new_lat, new_lon = float(data['lat']), float(data['lon'])
            
            # Only update position if it's different (ensures unique trail points)
            if (self.latitude is None or self.longitude is None or
                abs(new_lat - self.latitude) > 0.0001 or
                abs(new_lon - self.longitude) > 0.0001):
                
                self.latitude = new_lat
                self.longitude = new_lon
                
                # Add unique position to history
                if not self.position_history or calculate_distance(self.position_history[-1][0], self.position_history[-1][1], new_lat, new_lon) > 0.1:
                    self.position_history.append((new_lat, new_lon, self.last_seen))
                
                # Limit history length
                max_history = PROCESSING_CONFIG.get('trail_length', 10)
                if len(self.position_history) > max_history:
                    self.position_history = self.position_history[-max_history:]
        
        # Update other attributes
        if 'flight' in data and data['flight']:
            self.callsign = data['flight'].strip()
        if 'altitude' in data and data['altitude']:
            self.altitude = int(data['altitude'])
        if 'speed' in data and data['speed']:
            self.ground_speed = int(data['speed'])
        if 'track' in data and data['track']:
            self.track = float(data['track'])
        if 'vert_rate' in data and data['vert_rate']:
            self.vertical_rate = int(data['vert_rate'])
    
    def is_on_ground(self) -> bool:
        """Check if aircraft is on ground"""
        return self.altitude is not None and self.altitude < 100
    
    def get_altitude_category(self) -> str:
        """Get altitude category for coloring"""
        if self.altitude is None:
            return 'unknown'
        elif self.altitude < 10000:
            return 'low'
        elif self.altitude < 30000:
            return 'med'
        else:
            return 'high'


class ADSBDataFetcher:
    """Fetches and manages ADS-B data from various sources"""
    
    def __init__(self):
        self.aircraft = {}  # Dict of ICAO -> Aircraft
        self.last_update = datetime.now()
        
    def fetch_from_dump1090_json(self, url: str = None) -> bool:
        """Fetch data from dump1090 JSON interface"""
        if url is None:
            url = ADSB_CONFIG['dump1090_url']
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'aircraft' in data:
                self._process_aircraft_list(data['aircraft'])
                return True
            else:
                logger.warning(f"No aircraft data in response from {url}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Failed to fetch data from {url}: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {url}: {e}")
            return False
    
    def _process_aircraft_list(self, aircraft_list: List[Dict]):
        """Process a list of aircraft data"""
        current_time = datetime.now()
        seen_aircraft = set()
        
        for aircraft_data in aircraft_list:
            if 'hex' not in aircraft_data:
                continue
                
            icao = aircraft_data['hex'].upper()
            seen_aircraft.add(icao)
            
            # Create or update aircraft
            if icao not in self.aircraft:
                self.aircraft[icao] = Aircraft(icao)
            
            self.aircraft[icao].update(aircraft_data)
        
        # Clean up old aircraft
        timeout = timedelta(seconds=ADSB_CONFIG['cleanup_timeout'])
        to_remove = []
        
        for icao, aircraft in self.aircraft.items():
            if (current_time - aircraft.last_seen) > timeout:
                to_remove.append(icao)
        
        for icao in to_remove:
            del self.aircraft[icao]
            logger.info(f"Removed stale aircraft {icao}")
    
    def get_aircraft_in_bounds(self, lat_min: float, lat_max: float, 
                             lon_min: float, lon_max: float) -> List[Aircraft]:
        """Get aircraft within specified geographic bounds"""
        result = []
        
        for aircraft in self.aircraft.values():
            if (aircraft.latitude is not None and aircraft.longitude is not None and
                lat_min <= aircraft.latitude <= lat_max and
                lon_min <= aircraft.longitude <= lon_max):
                
                # Apply filters
                if PROCESSING_CONFIG['filter_ground'] and aircraft.is_on_ground():
                    continue
                
                if (aircraft.altitude is not None and 
                    not (PROCESSING_CONFIG['min_altitude'] <= aircraft.altitude <= 
                         PROCESSING_CONFIG['max_altitude'])):
                    continue
                
                result.append(aircraft)
        
        return result
    
    def get_aircraft_count(self) -> int:
        """Get total number of tracked aircraft"""
        return len(self.aircraft)
    
    def update(self) -> bool:
        """Update aircraft data from configured source"""
        # Try dump1090 JSON first
        if self.fetch_from_dump1090_json():
            self.last_update = datetime.now()
            return True
        
        # Could add fallback to other sources here
        logger.warning("Failed to update from any ADS-B source")
        return False


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in nautical miles"""
    import math
    
    # Convert to radians
    lat1_r = math.radians(lat1)
    lon1_r = math.radians(lon1)
    lat2_r = math.radians(lat2)
    lon2_r = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth radius in nautical miles
    r = 3440.065
    
    return c * r
