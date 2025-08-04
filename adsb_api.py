"""
ADS-B API Client with Caching
Fetches live aircraft data from api.adsb.lol with local caching
"""

import asyncio
import aiohttp
import json
import time
import math
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from adsb_data import Aircraft

# API Configuration
API_BASE_URL = "https://api.adsb.lol/v2"
DEFAULT_RADIUS = 25  # nautical miles
CACHE_DURATION = 5  # seconds - how long to cache data
REQUEST_TIMEOUT = 10  # seconds

# Known airport coordinates
AIRPORTS = {
    'RDU': {'lat': 35.877602, 'lon': -78.787498, 'name': 'Raleigh-Durham International'},
    'CLT': {'lat': 35.214, 'lon': -80.943, 'name': 'Charlotte Douglas International'},
    'ATL': {'lat': 33.6407, 'lon': -84.4277, 'name': 'Hartsfield-Jackson Atlanta'},
    'DCA': {'lat': 38.8521, 'lon': -77.0402, 'name': 'Ronald Reagan Washington National'},
    'JFK': {'lat': 40.6413, 'lon': -73.7781, 'name': 'John F. Kennedy International'},
    'LAX': {'lat': 33.9425, 'lon': -118.4081, 'name': 'Los Angeles International'},
    'ORD': {'lat': 41.9742, 'lon': -87.9073, 'name': "Chicago O'Hare International"},
    'DFW': {'lat': 32.8998, 'lon': -97.0403, 'name': 'Dallas/Fort Worth International'},
    'DEN': {'lat': 39.8561, 'lon': -104.6737, 'name': 'Denver International'},
    'SFO': {'lat': 37.6213, 'lon': -122.3790, 'name': 'San Francisco International'},
}


class ADSBApiClient:
    """Client for fetching live ADS-B data with caching"""
    
    def __init__(self):
        self.cache: Dict[str, Tuple[float, List[Aircraft]]] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _get_cache_key(self, lat: float, lon: float, radius: int) -> str:
        """Generate cache key for location"""
        return f"{lat:.6f},{lon:.6f},{radius}"
    
    async def get_aircraft(self, lat: float, lon: float, radius: int = DEFAULT_RADIUS) -> List[Aircraft]:
        """
        Fetch aircraft data for a given location with caching
        
        Args:
            lat: Latitude of center point
            lon: Longitude of center point
            radius: Radius in nautical miles
            
        Returns:
            List of Aircraft objects
        """
        cache_key = self._get_cache_key(lat, lon, radius)
        
        async with self._lock:
            # Check cache first
            if cache_key in self.cache:
                timestamp, aircraft_list = self.cache[cache_key]
                if time.time() - timestamp < CACHE_DURATION:
                    print(f"Cache hit for {cache_key}")
                    return aircraft_list
            
            # Fetch from API
            try:
                aircraft_list = await self._fetch_from_api(lat, lon, radius)
                # Update cache
                self.cache[cache_key] = (time.time(), aircraft_list)
                print(f"Fetched {len(aircraft_list)} aircraft from API")
                return aircraft_list
            except Exception as e:
                print(f"Error fetching from API: {e}")
                # Return cached data even if expired
                if cache_key in self.cache:
                    _, aircraft_list = self.cache[cache_key]
                    print(f"Returning expired cache data ({len(aircraft_list)} aircraft)")
                    return aircraft_list
                return []
    
    async def _fetch_from_api(self, lat: float, lon: float, radius: int) -> List[Aircraft]:
        """Fetch aircraft data from the API"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with ADSBApiClient()' context manager.")
        
        url = f"{API_BASE_URL}/lat/{lat}/lon/{lon}/dist/{radius}"
        print(f"Fetching from: {url}")
        
        async with self.session.get(url, timeout=REQUEST_TIMEOUT) as response:
            if response.status != 200:
                raise Exception(f"API returned status {response.status}")
            
            data = await response.json()
            
            if 'ac' not in data:
                return []
            
            aircraft_list = []
            for ac_data in data['ac']:
                aircraft = self._parse_aircraft_data(ac_data)
                if aircraft:
                    aircraft_list.append(aircraft)
            
            return aircraft_list
    
    def _parse_aircraft_data(self, data: Dict[str, Any]) -> Optional[Aircraft]:
        """Parse API aircraft data into Aircraft object"""
        try:
            # Required fields
            if 'hex' not in data:
                return None
            
            aircraft = Aircraft(data['hex'])
            
            # Map API fields to Aircraft object
            update_data = {}
            
            # Position
            if 'lat' in data and 'lon' in data:
                update_data['lat'] = data['lat']
                update_data['lon'] = data['lon']
            
            # Altitude
            if 'alt_baro' in data:
                if isinstance(data['alt_baro'], (int, float)):
                    update_data['altitude'] = data['alt_baro']
                elif data['alt_baro'] == 'ground':
                    update_data['altitude'] = 0
                    update_data['on_ground'] = True
            
            # Speed and heading
            if 'gs' in data:
                update_data['speed'] = data['gs']
            if 'track' in data:
                update_data['track'] = data['track']
            elif 'true_heading' in data:
                update_data['track'] = data['true_heading']
            
            # Flight info
            if 'flight' in data:
                update_data['flight'] = data['flight'].strip()
            if 'r' in data:
                update_data['registration'] = data['r']
            if 't' in data:
                update_data['type'] = data['t']
            
            # Other fields
            if 'squawk' in data:
                update_data['squawk'] = data['squawk']
            if 'baro_rate' in data:
                update_data['vertical_rate'] = data['baro_rate']
            
            # Update the aircraft object
            aircraft.update(update_data)
            
            return aircraft
            
        except Exception as e:
            print(f"Error parsing aircraft data: {e}")
            return None
    
    def get_airport_info(self, code: str) -> Optional[Dict[str, Any]]:
        """Get airport information by code"""
        return AIRPORTS.get(code.upper())
    
    def list_airports(self) -> Dict[str, Dict[str, Any]]:
        """Get all available airports"""
        return AIRPORTS


# Singleton instance for shared caching
_api_client: Optional[ADSBApiClient] = None
_client_lock = asyncio.Lock()


async def get_api_client() -> ADSBApiClient:
    """Get or create the singleton API client"""
    global _api_client
    
    async with _client_lock:
        if _api_client is None:
            _api_client = ADSBApiClient()
            await _api_client.__aenter__()
    
    return _api_client


async def fetch_aircraft_near_airport(airport_code: str = 'RDU', radius: int = DEFAULT_RADIUS) -> List[Aircraft]:
    """
    Convenience function to fetch aircraft near an airport
    
    Args:
        airport_code: Airport code (e.g., 'RDU')
        radius: Radius in nautical miles
        
    Returns:
        List of Aircraft objects
    """
    client = await get_api_client()
    
    airport = client.get_airport_info(airport_code)
    if not airport:
        raise ValueError(f"Unknown airport code: {airport_code}")
    
    return await client.get_aircraft(airport['lat'], airport['lon'], radius)


def calculate_bounds_from_point(lat: float, lon: float, radius_nm: int) -> Dict[str, float]:
    """
    Calculate map bounds from a center point and radius in nautical miles.
    
    Args:
        lat: Center latitude
        lon: Center longitude
        radius_nm: Radius in nautical miles
        
    Returns:
        Dictionary with lat_min, lat_max, lon_min, lon_max
    """
    # Convert radius to degrees latitude (1 degree ≈ 60 nautical miles)
    lat_delta = radius_nm / 60.0
    
    # Longitude delta depends on latitude due to Earth's curvature
    # At the equator, 1 degree longitude ≈ 60 nautical miles
    # At higher latitudes, it's less
    lon_delta = radius_nm / (60.0 * math.cos(math.radians(lat)))
    
    # Add some padding to ensure all aircraft in the radius are visible
    padding = 1.2  # 20% padding
    
    return {
        'lat_min': lat - (lat_delta * padding),
        'lat_max': lat + (lat_delta * padding),
        'lon_min': lon - (lon_delta * padding),
        'lon_max': lon + (lon_delta * padding)
    }


if __name__ == "__main__":
    # Test the API client
    async def test():
        async with ADSBApiClient() as client:
            # Test RDU
            aircraft = await client.get_aircraft(35.877602, -78.787498, 25)
            print(f"Found {len(aircraft)} aircraft near RDU")
            
            for ac in aircraft[:5]:  # Show first 5
                print(f"  {ac.icao}: {ac.callsign} at {ac.altitude}ft, {ac.ground_speed}kt")
            
            # Test caching
            print("\nTesting cache...")
            start = time.time()
            aircraft2 = await client.get_aircraft(35.877602, -78.787498, 25)
            elapsed = time.time() - start
            print(f"Second call took {elapsed:.3f}s (should be fast due to cache)")
    
    asyncio.run(test())
