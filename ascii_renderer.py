"""
ASCII Art Renderer for ADS-B Data
Converts aircraft positions to terminal-based ASCII art display
"""

import os
import math
from typing import List, Tuple, Dict
from datetime import datetime

# Handle colorama import with fallback
try:
    from colorama import init, Fore, Back, Style
    init()
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    # Fallback color codes for terminals that support ANSI
    class Fore:
        BLACK = '\033[30m'
        RED = '\033[31m'
        GREEN = '\033[32m'
        YELLOW = '\033[33m'
        BLUE = '\033[34m'
        MAGENTA = '\033[35m'
        CYAN = '\033[36m'
        WHITE = '\033[37m'
    
    class Style:
        RESET_ALL = '\033[0m'
    
    class Back:
        pass

from config import DISPLAY_CONFIG, ASCII_STYLES, DEFAULT_STYLE
from adsb_data import Aircraft, calculate_distance


class ASCIIRenderer:
    """Renders aircraft data as ASCII art in the terminal"""
    
    def __init__(self, style: str = DEFAULT_STYLE):
        self.style = style
        self.ascii_style = ASCII_STYLES.get(style, ASCII_STYLES[DEFAULT_STYLE])
        # Get current terminal dimensions from DISPLAY_CONFIG
        self.terminal_width = DISPLAY_CONFIG.get('terminal_width', 80)
        # Reserve space for the info panel
        self.full_terminal_height = DISPLAY_CONFIG.get('terminal_height', 25)
        self.info_panel_height = 22  # Estimated height for the info panel

        # Calculate map height, ensuring it's not negative
        self.map_height = self.full_terminal_height - self.info_panel_height
        if self.map_height < 5: self.map_height = 5

        self.map_bounds = DISPLAY_CONFIG.get('map_bounds', {
            'lat_min': 40.0,
            'lat_max': 42.0,
            'lon_min': -75.0,
            'lon_max': -73.0,
        })
        
        # Create grid for rendering using the calculated map_height
        self.grid = [[' ' for _ in range(self.terminal_width)] 
                     for _ in range(self.map_height)]
        self.color_grid = [[None for _ in range(self.terminal_width)] 
                          for _ in range(self.map_height)]
        
        # Track cells reserved for airport symbol and name
        self.airport_cells = set()
        
        # Log the dimensions being used
        print(f"ASCIIRenderer initialized with terminal_width={self.terminal_width}, "
              f"full_terminal_height={self.full_terminal_height}, map_height={self.map_height}")
        
    def clear_grid(self):
        """Clear the rendering grid"""
        bg_char = self.ascii_style['background']
        for y in range(self.map_height):
            for x in range(self.terminal_width):
                self.grid[y][x] = bg_char
                self.color_grid[y][x] = None
    
    def lat_lon_to_grid(self, latitude: float, longitude: float) -> Tuple[int, int]:
        """Convert latitude/longitude to grid coordinates"""
        bounds = self.map_bounds
        
        lat_norm = (latitude - bounds['lat_min']) / (bounds['lat_max'] - bounds['lat_min'])
        lon_norm = (longitude - bounds['lon_min']) / (bounds['lon_max'] - bounds['lon_min'])
        
        x = int(lon_norm * (self.terminal_width - 1))
        y = int((1 - lat_norm) * (self.map_height - 1))
        
        x = max(0, min(self.terminal_width - 1, x))
        y = max(0, min(self.map_height - 1, y))
        
        return x, y
    
    def get_aircraft_symbol(self, aircraft: Aircraft) -> str:
        """Get the appropriate symbol for an aircraft based on properties"""
        # Check if we should use Unicode directional symbols
        if DISPLAY_CONFIG.get('use_unicode_symbols', False) and aircraft.track is not None:
            # Try different sets of directional symbols
            heading = aircraft.track
            
            # Option 1: Arrow symbols (most compatible)
            if 337.5 <= heading or heading < 22.5:
                return '^'  # North
            elif 22.5 <= heading < 67.5:
                return '>'  # Northeast (simplified)
            elif 67.5 <= heading < 112.5:
                return '>'  # East
            elif 112.5 <= heading < 157.5:
                return '>'  # Southeast (simplified)
            elif 157.5 <= heading < 202.5:
                return 'v'  # South
            elif 202.5 <= heading < 247.5:
                return '<'  # Southwest (simplified)
            elif 247.5 <= heading < 292.5:
                return '<'  # West
            elif 292.5 <= heading < 337.5:
                return '<'  # Northwest (simplified)
        
        # Fallback to ASCII symbols based on speed
        if aircraft.ground_speed and aircraft.ground_speed > 400:
            # Fast aircraft symbols
            symbols = ['*', '+', '#', '@']
        elif aircraft.ground_speed and aircraft.ground_speed < 200:
            # Slow aircraft symbols  
            symbols = ['o', '0', 'O', '.']
        else:
            # Medium speed aircraft symbols
            symbols = ['x', 'X', '*', '+']
        
        # Use ICAO hash to consistently assign symbol to each aircraft
        if aircraft.icao:
            symbol_index = hash(aircraft.icao) % len(symbols)
            return symbols[symbol_index]
        
        return 'x'  # Default fallback
    
    def get_aircraft_color(self, aircraft: Aircraft) -> str:
        """Get color for aircraft based on altitude"""
        colors = DISPLAY_CONFIG['colors']
        
        if aircraft.is_on_ground():
            return colors['ground']
        
        alt_category = aircraft.get_altitude_category()
        color_map = {
            'low': colors['altitude_low'],
            'med': colors['altitude_med'],
            'high': colors['altitude_high'],
        }
        
        return color_map.get(alt_category, colors['aircraft'])
    
    def render_aircraft_trails(self, aircraft: Aircraft):
        """Render position history trails for an aircraft"""
        if not DISPLAY_CONFIG['show_trails'] or not aircraft.position_history:
            return
        
        trail_char = '.'  # Use simple dot for trail compatibility
        
        # Render all trail points except the current position
        for i, (lat, lon, timestamp) in enumerate(aircraft.position_history[:-1]):
            x, y = self.lat_lon_to_grid(lat, lon)
            if 0 <= x < self.terminal_width and 0 <= y < self.map_height:
                # Only render if cell is empty or has background AND not reserved for airport
                if (x, y) not in self.airport_cells and self.grid[y][x] in [self.ascii_style['background'], ' ']:
                    self.grid[y][x] = trail_char
                    aircraft_color = self.get_aircraft_color(aircraft)
                    self.color_grid[y][x] = aircraft_color
    
    def render_airport(self, lat: float, lon: float, code: str):
        """Render airport marker at given coordinates"""
        x, y = self.lat_lon_to_grid(lat, lon)
        
        # Clear previous airport cells tracking
        self.airport_cells.clear()
        
        if 0 <= x < self.terminal_width and 0 <= y < self.map_height:
            # Use a distinctive symbol for the airport
            self.grid[y][x] = 'O'
            self.color_grid[y][x] = 'white'
            self.airport_cells.add((x, y))
            
            # Try to render the airport code around it if space permits
            code = code[:3]  # Limit to 3 chars
            # Place code above the airport marker if possible
            if y > 0 and x - 1 >= 0 and x + len(code) < self.terminal_width:
                for i, char in enumerate(code):
                    code_x = x - 1 + i
                    code_y = y - 1
                    self.grid[code_y][code_x] = char
                    self.color_grid[code_y][code_x] = 'white'
                    self.airport_cells.add((code_x, code_y))
    
    def render_aircraft(self, aircraft_list: List[Aircraft]):
        """Render all aircraft on the grid"""
        self.clear_grid()
        
        # First pass: render trails
        for aircraft in aircraft_list:
            if aircraft.latitude is not None and aircraft.longitude is not None:
                self.render_aircraft_trails(aircraft)
        
        # Second pass: render aircraft (so they appear on top of trails)
        for aircraft in aircraft_list:
            if aircraft.latitude is not None and aircraft.longitude is not None:
                x, y = self.lat_lon_to_grid(aircraft.latitude, aircraft.longitude)
                
                # Skip cells reserved for airport
                if (x, y) not in self.airport_cells and 0 <= x < self.terminal_width and 0 <= y < self.map_height:
                    symbol = self.get_aircraft_symbol(aircraft)
                    color = self.get_aircraft_color(aircraft)
                    
                    self.grid[y][x] = symbol
                    self.color_grid[y][x] = color
    
    def render_border(self):
        """Render border around the display area"""
        border_color = DISPLAY_CONFIG['colors']['border']
        
        # Top and bottom borders
        for x in range(self.terminal_width):
            if self.grid[0][x] == self.ascii_style['background']:
                self.grid[0][x] = '-'
                self.color_grid[0][x] = border_color
            if self.grid[self.map_height - 1][x] == self.ascii_style['background']:
                self.grid[self.map_height - 1][x] = '-'
                self.color_grid[self.map_height - 1][x] = border_color
        
        # Left and right borders
        for y in range(self.map_height):
            if self.grid[y][0] == self.ascii_style['background']:
                self.grid[y][0] = '|'
                self.color_grid[y][0] = border_color
            if self.grid[y][self.terminal_width - 1] == self.ascii_style['background']:
                self.grid[y][self.terminal_width - 1] = '|'
                self.color_grid[y][self.terminal_width - 1] = border_color
        
        # Corners
        self.grid[0][0] = '+'
        self.grid[0][self.terminal_width - 1] = '+'
        self.grid[self.map_height - 1][0] = '+'
        self.grid[self.map_height - 1][self.terminal_width - 1] = '+'
        self.color_grid[0][0] = border_color
        self.color_grid[0][self.terminal_width - 1] = border_color
        self.color_grid[self.map_height - 1][0] = border_color
        self.color_grid[self.map_height - 1][self.terminal_width - 1] = border_color
    
    def get_color_code(self, color_name: str) -> str:
        """Convert color name to ANSI color code"""
        color_map = {
            'black': Fore.BLACK,
            'red': Fore.RED,
            'green': Fore.GREEN,
            'yellow': Fore.YELLOW,
            'blue': Fore.BLUE,
            'magenta': Fore.MAGENTA,
            'cyan': Fore.CYAN,
            'white': Fore.WHITE,
        }
        return color_map.get(color_name, '')
    
    def render_to_string(self, aircraft_list: List[Aircraft], 
                        show_info: bool = True, airport_info: Dict = None) -> str:
        """Render the complete display as a string"""
        # First, calculate airport cells if airport info provided
        if airport_info and 'lat' in airport_info and 'lon' in airport_info:
            code = airport_info.get('code', 'APT')
            # Pre-calculate airport cells before rendering aircraft
            x, y = self.lat_lon_to_grid(airport_info['lat'], airport_info['lon'])
            self.airport_cells.clear()
            if 0 <= x < self.terminal_width and 0 <= y < self.map_height:
                self.airport_cells.add((x, y))
                # Also reserve cells for the airport code
                if y > 0 and x - 1 >= 0 and x + len(code[:3]) < self.terminal_width:
                    for i in range(len(code[:3])):
                        self.airport_cells.add((x - 1 + i, y - 1))
        
        # Now render aircraft (which will avoid airport cells)
        self.render_aircraft(aircraft_list)
        
        # Finally render airport on top
        if airport_info and 'lat' in airport_info and 'lon' in airport_info:
            code = airport_info.get('code', 'APT')
            self.render_airport(airport_info['lat'], airport_info['lon'], code)
        
        self.render_border()
        
        output_lines = []
        
        # Render grid with colors
        for y in range(self.map_height):
            line = ""
            
            for x in range(self.terminal_width):
                char = self.grid[y][x]
                color = self.color_grid[y][x]
                
                # Add color if specified, then character, then reset
                if color is not None:
                    line += self.get_color_code(color) + char + Style.RESET_ALL
                else:
                    line += char
            
            output_lines.append(line)
        
        # Add information panel if requested
        if show_info:
            # Clear from cursor to end of screen to prevent old text from persisting
            output_lines.append("\x1b[J") 
            output_lines.extend(self._create_info_panel(aircraft_list, airport_info))
        
        return '\n'.join(output_lines)
    
    def _create_info_panel(self, aircraft_list: List[Aircraft], airport_info: Dict = None) -> List[str]:
        """Create information panel showing aircraft details"""
        info_lines = []
        info_lines.append("=" * self.terminal_width)
        info_lines.append(f"ADS-B ASCII Radar - {datetime.utcnow().strftime('%H:%M:%S')} UTC")
        # Show display mode and aircraft count
        # Use session-specific display mode if available
        if hasattr(self, 'session_display_mode'):
            display_mode = self.session_display_mode[0]
        else:
            display_mode = DISPLAY_CONFIG.get('display_mode', 'all')
            
        if display_mode == 'closest':
            limit = DISPLAY_CONFIG.get('display_aircraft_limit', 10)
            info_lines.append(f"Aircraft tracked: {len(aircraft_list)} (showing closest {limit})")
        else:
            info_lines.append(f"Aircraft tracked: {len(aircraft_list)} (showing all)")
        
        bounds = self.map_bounds
        info_lines.append(f"Bounds: {bounds['lat_min']:.2f},{bounds['lon_min']:.2f} to "
                         f"{bounds['lat_max']:.2f},{bounds['lon_max']:.2f}")
        
        # Show current mode and speed multiplier
        if DISPLAY_CONFIG.get('demo_mode', False):
            info_lines.append(f"Mode: DEMO (Speed x{DISPLAY_CONFIG['speed_multiplier']})")
        else:
            airport = DISPLAY_CONFIG.get('airport', 'RDU')
            radius = DISPLAY_CONFIG.get('radius', 25)
            info_lines.append(f"Mode: LIVE - {airport} ({radius}nm radius)")
        
        # Add hotkeys
        info_lines.append("")
        info_lines.append("Hotkeys: (r)efresh, (t)oggle display mode, (q)uit")
        info_lines.append("")
        
        # Show some aircraft details
        if airport_info and 'lat' in airport_info and 'lon' in airport_info:
            info_lines.append(f"Closest Aircraft to {airport_info.get('code', 'Airport')}:")
        else:
            info_lines.append("Aircraft Details:")
        info_lines.append("ICAO     Call     Alt(ft)  Spd(kt)  Hdg°  Dist(nm)")
        info_lines.append("-" * 55)
        
        # Sort by distance (closest first) to airport
        if airport_info and 'lat' in airport_info and 'lon' in airport_info:
            airport_lat = airport_info['lat']
            airport_lon = airport_info['lon']
            sorted_aircraft = sorted([a for a in aircraft_list if a.latitude is not None and a.longitude is not None], 
                                     key=lambda x: calculate_distance(airport_lat, airport_lon, x.latitude, x.longitude))
        else:
            sorted_aircraft = aircraft_list # Fallback in case airport info is missing
        
        # Get the limit for number of aircraft to display
        display_limit = DISPLAY_CONFIG.get('display_aircraft_limit', 10)
        
        for i, aircraft in enumerate(sorted_aircraft[:display_limit]):  # Apply display limit
            callsign = aircraft.callsign[:8] if aircraft.callsign else "N/A"
            speed = f"{aircraft.ground_speed}" if aircraft.ground_speed else "N/A"
            heading = f"{aircraft.track:.0f}" if aircraft.track else "N/A"
            
            # Color-code the altitude based on aircraft altitude category
            if aircraft.altitude:
                altitude_str = f"{aircraft.altitude:,}"
                altitude_color = self.get_aircraft_color(aircraft)
                colored_altitude = f"{self.get_color_code(altitude_color)}{altitude_str:>8}{Style.RESET_ALL}"
            else:
                colored_altitude = "     N/A"
            
            # Calculate distance if airport info is available
            if airport_info and 'lat' in airport_info and 'lon' in airport_info:
                distance = calculate_distance(airport_lat, airport_lon, aircraft.latitude, aircraft.longitude)
                distance_str = f"{distance:.1f}"
            else:
                distance_str = "N/A"
            
            info_lines.append(f"{aircraft.icao:8} {callsign:8} {colored_altitude} {speed:>7} {heading:>5} {distance_str:>8}")
        
        return info_lines
    
    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def display(self, aircraft_list: List[Aircraft], clear_screen: bool = True):
        """Display the rendered output to terminal"""
        if clear_screen:
            self.clear_screen()
        
        print(self.render_to_string(aircraft_list))


def create_demo_aircraft() -> List[Aircraft]:
    """Create some demo aircraft for testing"""
    demo_aircraft = []
    
    # Create a few test aircraft within the default bounds
    aircraft_data = [
        {"icao": "ABC123", "lat": 40.5, "lon": -74.5, "altitude": 25000, "speed": 450, "track": 90, "flight": "UAL123"},
        {"icao": "DEF456", "lat": 41.2, "lon": -73.8, "altitude": 15000, "speed": 320, "track": 180, "flight": "DAL456"},
        {"icao": "GHI789", "lat": 40.8, "lon": -74.2, "altitude": 35000, "speed": 520, "track": 270, "flight": "AAL789"},
        {"icao": "JKL012", "lat": 41.5, "lon": -73.5, "altitude": 8000, "speed": 250, "track": 45, "flight": "SWA012"},
    ]
    
    for data in aircraft_data:
        aircraft = Aircraft(data["icao"])
        aircraft.update(data)
        demo_aircraft.append(aircraft)
    
    return demo_aircraft


if __name__ == "__main__":
    # Demo/test mode
    renderer = ASCIIRenderer()
    demo_aircraft = create_demo_aircraft()
    
    print("ADS-B ASCII Art Renderer Demo")
    print("Displaying demo aircraft...")
    
    renderer.display(demo_aircraft)
