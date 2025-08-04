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
from adsb_data import Aircraft


class ASCIIRenderer:
    """Renders aircraft data as ASCII art in the terminal"""
    
    def __init__(self, style: str = DEFAULT_STYLE):
        self.style = style
        self.ascii_style = ASCII_STYLES.get(style, ASCII_STYLES[DEFAULT_STYLE])
        self.terminal_width = DISPLAY_CONFIG['terminal_width']
        self.terminal_height = DISPLAY_CONFIG['terminal_height']
        self.map_bounds = DISPLAY_CONFIG['map_bounds']
        
        # Create grid for rendering
        self.grid = [[' ' for _ in range(self.terminal_width)] 
                     for _ in range(self.terminal_height)]
        self.color_grid = [[None for _ in range(self.terminal_width)] 
                          for _ in range(self.terminal_height)]
        
    def clear_grid(self):
        """Clear the rendering grid"""
        bg_char = self.ascii_style['background']
        for y in range(self.terminal_height):
            for x in range(self.terminal_width):
                self.grid[y][x] = bg_char
                self.color_grid[y][x] = None
    
    def lat_lon_to_grid(self, latitude: float, longitude: float) -> Tuple[int, int]:
        """Convert latitude/longitude to grid coordinates"""
        bounds = self.map_bounds
        
        # Normalize coordinates to 0-1
        lat_norm = (latitude - bounds['lat_min']) / (bounds['lat_max'] - bounds['lat_min'])
        lon_norm = (longitude - bounds['lon_min']) / (bounds['lon_max'] - bounds['lon_min'])
        
        # Convert to grid coordinates (flip Y axis for display)
        x = int(lon_norm * (self.terminal_width - 1))
        y = int((1 - lat_norm) * (self.terminal_height - 1))
        
        # Clamp to grid bounds
        x = max(0, min(self.terminal_width - 1, x))
        y = max(0, min(self.terminal_height - 1, y))
        
        return x, y
    
    def get_aircraft_symbol(self, aircraft: Aircraft) -> str:
        """Get the appropriate symbol for an aircraft based on heading"""
        if aircraft.track is None:
            return self.ascii_style['aircraft'][0]  # Default to north-facing
        
        # Convert track to 4-direction index (N, E, S, W)
        # Normalize to 0-360
        track = aircraft.track % 360
        
        # Divide into quadrants
        if track < 45 or track >= 315:
            direction_idx = 0  # North
        elif track < 135:
            direction_idx = 1  # East
        elif track < 225:
            direction_idx = 2  # South
        else:
            direction_idx = 3  # West
        
        return self.ascii_style['aircraft'][direction_idx]
    
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
        
        trail_char = self.ascii_style['trail']
        
        # Render trail from oldest to newest (so newer positions overwrite older)
        for lat, lon, timestamp in aircraft.position_history[:-1]:  # Exclude current position
            x, y = self.lat_lon_to_grid(lat, lon)
            if 0 <= x < self.terminal_width and 0 <= y < self.terminal_height:
                if self.grid[y][x] == self.ascii_style['background']:  # Don't overwrite aircraft
                    self.grid[y][x] = trail_char
                    self.color_grid[y][x] = 'white'
    
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
                
                if 0 <= x < self.terminal_width and 0 <= y < self.terminal_height:
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
            if self.grid[self.terminal_height - 1][x] == self.ascii_style['background']:
                self.grid[self.terminal_height - 1][x] = '-'
                self.color_grid[self.terminal_height - 1][x] = border_color
        
        # Left and right borders
        for y in range(self.terminal_height):
            if self.grid[y][0] == self.ascii_style['background']:
                self.grid[y][0] = '|'
                self.color_grid[y][0] = border_color
            if self.grid[y][self.terminal_width - 1] == self.ascii_style['background']:
                self.grid[y][self.terminal_width - 1] = '|'
                self.color_grid[y][self.terminal_width - 1] = border_color
        
        # Corners
        self.grid[0][0] = '+'
        self.grid[0][self.terminal_width - 1] = '+'
        self.grid[self.terminal_height - 1][0] = '+'
        self.grid[self.terminal_height - 1][self.terminal_width - 1] = '+'
        self.color_grid[0][0] = border_color
        self.color_grid[0][self.terminal_width - 1] = border_color
        self.color_grid[self.terminal_height - 1][0] = border_color
        self.color_grid[self.terminal_height - 1][self.terminal_width - 1] = border_color
    
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
                        show_info: bool = True) -> str:
        """Render the complete display as a string"""
        self.render_aircraft(aircraft_list)
        self.render_border()
        
        output_lines = []
        
        # Render grid with colors
        for y in range(self.terminal_height):
            line = ""
            current_color = None
            
            for x in range(self.terminal_width):
                char = self.grid[y][x]
                color = self.color_grid[y][x]
                
                # Apply color changes
                if color != current_color:
                    if current_color is not None:
                        line += Style.RESET_ALL
                    
                    if color is not None:
                        line += self.get_color_code(color)
                    
                    current_color = color
                
                line += char
            
            # Reset color at end of line
            if current_color is not None:
                line += Style.RESET_ALL
            
            output_lines.append(line)
        
        # Add information panel if requested
        if show_info:
            output_lines.extend(self._create_info_panel(aircraft_list))
        
        return '\n'.join(output_lines)
    
    def _create_info_panel(self, aircraft_list: List[Aircraft]) -> List[str]:
        """Create information panel showing aircraft details"""
        info_lines = []
        info_lines.append("=" * self.terminal_width)
        info_lines.append(f"ADS-B ASCII Radar - {datetime.now().strftime('%H:%M:%S')} UTC")
        info_lines.append(f"Aircraft tracked: {len(aircraft_list)}")
        
        bounds = self.map_bounds
        info_lines.append(f"Bounds: {bounds['lat_min']:.2f},{bounds['lon_min']:.2f} to "
                         f"{bounds['lat_max']:.2f},{bounds['lon_max']:.2f}")
        
        # Show some aircraft details
        info_lines.append("")
        info_lines.append("ICAO     Call     Alt(ft)  Spd(kt)  Hdg°")
        info_lines.append("-" * 45)
        
        # Sort by altitude (highest first)
        sorted_aircraft = sorted([a for a in aircraft_list if a.altitude is not None], 
                               key=lambda x: x.altitude or 0, reverse=True)
        
        for i, aircraft in enumerate(sorted_aircraft[:10]):  # Show top 10
            callsign = aircraft.callsign[:8] if aircraft.callsign else "N/A"
            altitude = f"{aircraft.altitude:,}" if aircraft.altitude else "N/A"
            speed = f"{aircraft.ground_speed}" if aircraft.ground_speed else "N/A"
            heading = f"{aircraft.track:.0f}" if aircraft.track else "N/A"
            
            info_lines.append(f"{aircraft.icao:8} {callsign:8} {altitude:>8} {speed:>7} {heading:>5}")
        
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
