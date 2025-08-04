"""
Configuration settings for ADS-B ASCII Art application
"""

# ADS-B Data Source Configuration
ADSB_CONFIG = {
    # Common ADS-B data sources
    'dump1090_url': 'http://localhost:8080/data/aircraft.json',  # dump1090 web interface
    'rtl1090_url': 'http://localhost:31090/data/aircraft.json',  # RTL1090
    'virtual_radar_url': 'http://localhost:8080/VirtualRadar/AircraftList.json',  # Virtual Radar Server
    'flightaware_url': 'https://flightaware.com/adsb/piaware/',  # FlightAware (if accessible)
    
    # Alternative: Direct TCP connection to dump1090
    'dump1090_host': 'localhost',
    'dump1090_port': 30003,  # Beast format port
    
    # Update intervals
    'update_interval': 5,  # seconds between data refreshes
    'cleanup_timeout': 300,  # remove aircraft not seen for 5 minutes
}

# ASCII Art Display Configuration
DISPLAY_CONFIG = {
    'terminal_width': 80,
    'terminal_height': 25,
    'map_bounds': {
        'lat_min': 40.0,   # Adjust these to your local area
        'lat_max': 42.0,
        'lon_min': -75.0,
        'lon_max': -73.0,
    },
    'aircraft_symbol': '✈',
    'airport_symbol': '🛫',
    'colors': {
        'aircraft': 'cyan',
        'altitude_high': 'red',      # >30,000 ft
        'altitude_med': 'yellow',    # 10,000-30,000 ft
        'altitude_low': 'green',     # <10,000 ft
        'ground': 'white',
        'border': 'blue',
    },
    'show_trails': True,
    'trail_length': 10,  # number of previous positions to show
}

# Data Processing Configuration
PROCESSING_CONFIG = {
    'min_altitude': 0,      # minimum altitude to display (feet)
    'max_altitude': 50000,  # maximum altitude to display (feet)
    'filter_ground': False, # whether to filter out ground traffic
    'distance_filter': 100, # maximum distance in nautical miles (0 = no filter)
}

# ASCII Art Styles
ASCII_STYLES = {
    'simple': {
        'aircraft': ['✈', '✈', '✈', '✈'],  # N, E, S, W orientations
        'trail': '·',
        'background': ' ',
    },
    'detailed': {
        'aircraft': ['↑', '→', '↓', '←'],  # directional arrows
        'trail': '•',
        'background': '·',
    },
    'classic': {
        'aircraft': ['^', '>', 'v', '<'],  # ASCII arrows
        'trail': '.',
        'background': ' ',
    }
}

# Default style
DEFAULT_STYLE = 'simple'
