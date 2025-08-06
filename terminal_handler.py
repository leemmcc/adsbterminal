"""
Shared terminal handler for both telnet and SSH connections.
This module contains the core terminal handling logic that can be used
by both telnet_server.py and ssh_server.py.
"""

import asyncio
import yaml
import re
import time
from datetime import datetime
from ascii_renderer import ASCIIRenderer, create_demo_aircraft
from main import ADSBRadarApp
from adsb_api import fetch_aircraft_near_airport, ADSBApiClient, AIRPORTS, calculate_bounds_from_point
from config import PROCESSING_CONFIG, DISPLAY_CONFIG

# Load config file at module level
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

def process_colored_line(line, terminal_width, use_colors):
    """Process a line with ANSI colors, ensuring proper terminal width"""
    if not use_colors:
        clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
        if len(clean_line) > terminal_width:
            clean_line = clean_line[:terminal_width]
        return clean_line.ljust(terminal_width).rstrip() + '\r\n'
    
    segments = re.split(r'(\x1b\[[0-9;]*m)', line)
    visible_chars = 0
    result = ""
    
    for segment in segments:
        if re.match(r'\x1b\[[0-9;]*m', segment):
            result += segment
        else:
            remaining_width = terminal_width - visible_chars
            if remaining_width <= 0:
                break
            
            segment_len = len(segment)
            if segment_len > remaining_width:
                result += segment[:remaining_width]
                visible_chars = terminal_width
                break
            else:
                result += segment
                visible_chars += segment_len
    
    if visible_chars < terminal_width:
        result += ' ' * (terminal_width - visible_chars)
    
    return result.rstrip() + '\r\n'

async def reader_task(reader, queue):
    """Reads data from the client and puts it into a queue."""
    while True:
        try:
            char = await reader.read(1)
            if not char:
                await queue.put(None)  # Signal EOF
                break
            # Handle both bytes and strings
            if isinstance(char, bytes):
                char = char.decode('utf-8', errors='ignore')
            await queue.put(char)
        except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
            await queue.put(None)  # Signal EOF
            break
        except Exception as e:
            print(f"Reader task error: {e}")
            await queue.put(None)  # Signal EOF
            break

async def handle_input(queue, app, on_reset, force_update, session_display_mode):
    """Handles user input from the queue."""
    debug = config.get('debug', False)
    while app.running:
        try:
            char = await asyncio.wait_for(queue.get(), timeout=0.1)
            if char is None:  # EOF
                app.running = False
                break

            if debug:
                print(f"Input received: {repr(char)} (len={len(char)})")

            # Only process single printable ASCII characters
            if len(char) == 1 and char.isprintable():
                key = char.lower()
                if key == 'q':
                    print("Quit command received.")
                    app.running = False
                elif key == 'r':
                    print("Refreshing display, re-detecting terminal size, and clearing trails...")
                    await on_reset(clear_trails=True, refresh_display=True)
                elif key == 't':
                    # Toggle display mode for this session only
                    modes = ['all', 'closest', 'high', 'medium', 'low']
                    current_idx = modes.index(session_display_mode[0])
                    next_idx = (current_idx + 1) % len(modes)
                    session_display_mode[0] = modes[next_idx]
                    print(f"Display mode changed to: {session_display_mode[0].upper()} (session-specific)")
                    # Force screen update
                    force_update.set()
        except asyncio.TimeoutError:
            continue

async def detect_terminal_size(reader, writer, is_ssh=False):
    """Detect current terminal size using cursor position query."""
    try:
        # Save cursor, move to bottom-right corner, and query position
        writer.write('\x1b[s\x1b[999;999H\x1b[6n')
        await writer.drain()
        
        # Read the response
        response = await asyncio.wait_for(reader.read(20), timeout=1.0)
        
        # Restore cursor position
        writer.write('\x1b[u')
        await writer.drain()
        
        # Parse the response
        match = re.search(r'\x1b\[(\d+);(\d+)R', response)
        if match:
            rows, cols = int(match.group(1)), int(match.group(2))
            if rows > 0 and cols > 0:
                return cols, rows
                
    except asyncio.TimeoutError:
        print("Terminal size detection timed out.")
    except Exception as e:
        print(f"Error during terminal size detection: {e}")
    
    # Ensure cursor is restored on failure
    try:
        writer.write('\x1b[u')
        await writer.drain()
    except Exception:
        pass
        
    return None, None

async def handle_terminal_session(reader, writer, speed, peername, protocol='telnet'):
    """
    Main terminal session handler that works for both telnet and SSH.
    
    Args:
        reader: Stream reader (telnet or SSH)
        writer: Stream writer (telnet or SSH)
        speed: Animation speed multiplier
        peername: Client connection info
        protocol: 'telnet' or 'ssh'
    """
    print(f"Client connected via {protocol} from {peername}")
    
    input_queue = asyncio.Queue()
    
    # Give client time to establish connection
    await asyncio.sleep(0.2)
    
    # --- Terminal Size Detection ---
    terminal_width, terminal_height = None, None
    config_width, config_height = config.get('terminal_width'), config.get('terminal_height')

    if config_width and config_height:
        terminal_width, terminal_height = int(config_width), int(config_height)
        print(f"Using configured terminal size: {terminal_width}x{terminal_height}")
    else:
        print(f"Attempting terminal size detection for {peername}...")
        
        if protocol == 'telnet':
            # telnetlib3 handles NAWS negotiation automatically
            await writer.drain()
            await asyncio.sleep(0.1)
            if hasattr(writer, 'get_extra_info') and writer.get_extra_info('columns'):
                terminal_width = writer.get_extra_info('columns')
                terminal_height = writer.get_extra_info('lines')
                print(f"Detected size via NAWS: {terminal_width}x{terminal_height}")
        elif protocol == 'ssh':
            # For SSH, try to get terminal size from the SSH session
            if hasattr(writer, 'get_terminal_size'):
                try:
                    terminal_width, terminal_height = writer.get_terminal_size()
                    print(f"Detected size via SSH: {terminal_width}x{terminal_height}")
                except:
                    pass

        if not terminal_width:
            print(f"{protocol.upper()} size detection failed, trying cursor position query...")
            terminal_width, terminal_height = await detect_terminal_size(reader, writer, is_ssh=(protocol=='ssh'))
            if terminal_width:
                print(f"Detected size via cursor query: {terminal_width}x{terminal_height}")

    if not terminal_width or not terminal_height:
        terminal_width, terminal_height = 120, 40
        print(f"All detection methods failed. Using modern default size: {terminal_width}x{terminal_height}")
        print("Tip: You can set custom terminal size in config.yaml")
    
    # Start the reader task AFTER terminal size detection
    rtask = asyncio.create_task(reader_task(reader, input_queue))

    # --- App Setup ---
    print(f"Final terminal size: width={terminal_width}, height={terminal_height}")
    session_display_mode = ['all']  # Default to showing all aircraft
    
    DISPLAY_CONFIG.update({
        'terminal_width': terminal_width,
        'terminal_height': terminal_height,
        'demo_mode': config.get('demomode', True),
        'speed_multiplier': speed,
        'use_unicode_symbols': config.get('use_unicode_symbols', False),
        'airport': config.get('airport', 'RDU'),
        'radius': config.get('radius', 25),
        'display_aircraft_limit': config.get('display_aircraft_limit', 5)
    })
    
    # Function to check for terminal resize
    def check_terminal_resize():
        nonlocal terminal_width, terminal_height, renderer
        new_width = new_height = None
        
        if protocol == 'telnet' and hasattr(writer, 'get_extra_info'):
            new_width = writer.get_extra_info('columns')
            new_height = writer.get_extra_info('lines')
        elif protocol == 'ssh' and hasattr(writer, 'get_terminal_size'):
            try:
                new_width, new_height = writer.get_terminal_size()
            except:
                pass
        
        if new_width and new_height and (new_width != terminal_width or new_height != terminal_height):
            terminal_width = new_width
            terminal_height = new_height
            print(f"Terminal resized to: {terminal_width}x{terminal_height}")
            
            # Update display config
            DISPLAY_CONFIG.update({
                'terminal_width': terminal_width,
                'terminal_height': terminal_height
            })
            
            # Recreate renderer with new dimensions
            renderer = ASCIIRenderer()
            renderer.session_display_mode = session_display_mode
            
            force_update.set()
            return True
        return False
    
    airport_code = config.get('airport', 'RDU')
    radius = config.get('radius', 25)
    
    # Calculate map bounds based on airport location
    airport_info = AIRPORTS.get(airport_code)
    if airport_info:
        map_bounds = calculate_bounds_from_point(airport_info['lat'], airport_info['lon'], radius)
        DISPLAY_CONFIG['map_bounds'] = map_bounds
        print(f"Set map bounds for {airport_code}: {map_bounds['lat_min']:.2f},{map_bounds['lon_min']:.2f} to {map_bounds['lat_max']:.2f},{map_bounds['lon_max']:.2f}")
    
    # Create renderer and app AFTER setting map bounds
    renderer = ASCIIRenderer()
    renderer.session_display_mode = session_display_mode
    app = ADSBRadarApp(demo_mode=config.get('demomode', True))
    app.speed_multiplier = speed
    app.set_update_interval(config.get('interval', 1))

    async def fetch_aircraft():
        """Fetches live aircraft or creates demo data based on mode"""
        if app.demo_mode:
            return create_demo_aircraft()
        if config.get('debug', False):
            print(f"Fetching live data for {airport_code}, radius {radius}")
        return await fetch_aircraft_near_airport(airport_code, radius)

    # Setup reset function for async context
    aircraft_ref = {'data': None}
    tracked_aircraft = {}  # Keep track of aircraft across updates
    force_update = asyncio.Event()  # Event to trigger immediate screen update
    
    async def reset_aircraft(clear_trails=False, refresh_display=False):
        """Reset aircraft data - works for both demo and live modes"""
        nonlocal terminal_width, terminal_height, renderer, rtask
        
        # If refresh_display is requested, re-detect terminal size
        if refresh_display:
            if config.get('debug', False):
                print("Re-detecting terminal size...")
            
            # Pause the reader task temporarily
            rtask.cancel()
            await asyncio.sleep(0.1)
            
            # Try to detect new size
            detected_width, detected_height = await detect_terminal_size(reader, writer, is_ssh=(protocol=='ssh'))
            if detected_width and detected_height:
                terminal_width = detected_width
                terminal_height = detected_height
                if config.get('debug', False):
                    print(f"Detected size via cursor query: {terminal_width}x{terminal_height}")
            
            # Restart the reader task
            rtask = asyncio.create_task(reader_task(reader, input_queue))
            
            # Update display config
            DISPLAY_CONFIG.update({
                'terminal_width': terminal_width,
                'terminal_height': terminal_height
            })
            
            # Recreate renderer with new dimensions
            renderer = ASCIIRenderer()
            renderer.session_display_mode = session_display_mode
            
            # Clear screen and reset cursor
            writer.write("\x1b[2J\x1b[1;1H\x1b[?25l")
            await writer.drain()
            
            clear_trails = True
            force_update.set()
        
        # If we need to clear trails
        if clear_trails:
            if tracked_aircraft:
                for aircraft in tracked_aircraft.values():
                    aircraft.position_history = []
                if config.get('debug', False):
                    print("Cleared all aircraft trails")
                if not refresh_display and not app.demo_mode:
                    aircraft_ref['data'] = list(tracked_aircraft.values())
                    force_update.set()
                    return
        
        # Fetch new data
        new_data = await fetch_aircraft()
        
        if app.demo_mode:
            aircraft_ref['data'] = new_data
        else:
            # For live mode, maintain position history
            current_icaos = set()
            updated_aircraft = []
            
            for new_aircraft in new_data:
                icao = new_aircraft.icao
                current_icaos.add(icao)
                
                if icao in tracked_aircraft:
                    existing = tracked_aircraft[icao]
                    if not clear_trails:
                        new_aircraft.position_history = existing.position_history.copy()
                    else:
                        new_aircraft.position_history = []
                    
                    # Check if position has changed enough to add to history
                    if new_aircraft.latitude and new_aircraft.longitude:
                        should_add = False
                        if not new_aircraft.position_history:
                            should_add = True
                        else:
                            last_lat, last_lon, _ = new_aircraft.position_history[-1]
                            from adsb_data import calculate_distance
                            dist = calculate_distance(last_lat, last_lon, new_aircraft.latitude, new_aircraft.longitude)
                            if dist > 0.5:  # 0.5 nautical miles minimum between points
                                should_add = True
                                
                        if should_add:
                            new_aircraft.position_history.append((new_aircraft.latitude, new_aircraft.longitude, datetime.now()))
                            max_history = config.get('trail_length', PROCESSING_CONFIG.get('trail_length', 15))
                            if len(new_aircraft.position_history) > max_history:
                                new_aircraft.position_history = new_aircraft.position_history[-max_history:]
                else:
                    # New aircraft
                    if new_aircraft.latitude and new_aircraft.longitude and not clear_trails:
                        new_aircraft.position_history.append((new_aircraft.latitude, new_aircraft.longitude, datetime.now()))
                
                tracked_aircraft[icao] = new_aircraft
                updated_aircraft.append(new_aircraft)
            
            # Remove aircraft that are no longer being tracked
            for icao in list(tracked_aircraft.keys()):
                if icao not in current_icaos:
                    del tracked_aircraft[icao]
            
            aircraft_ref['data'] = updated_aircraft
        
        if config.get('debug', False):
            print(f"Loaded {len(aircraft_ref['data'])} aircraft")

    # Clear any remaining data from terminal size detection
    cleared_count = 0
    while not input_queue.empty():
        try:
            char = input_queue.get_nowait()
            cleared_count += 1
        except asyncio.QueueEmpty:
            break
    
    # Set app.running to True BEFORE starting the input handler
    app.running = True
    
    # Initialize aircraft data without building trails
    await reset_aircraft(clear_trails=True)

    # Start input handler
    input_task = asyncio.create_task(handle_input(input_queue, app, reset_aircraft, force_update, session_display_mode))

    # --- Main Loop ---
    writer.write("\x1b[2J\x1b[1;1H\x1b[?25l")
    await writer.drain()
    
    # Give the terminal a moment to stabilize
    await asyncio.sleep(0.5)
    
    last_data_update = time.time()
    last_keepalive = time.time()
    update_counter = 0
    keepalive_interval = config.get('keepalive_interval', 30)
    
    try:
        while app.running:
            if writer.is_closing():
                print(f"Client {peername} connection closed.")
                break
            
            # Send periodic keepalive to prevent timeout
            current_time = time.time()
            if keepalive_interval > 0 and current_time - last_keepalive > keepalive_interval:
                try:
                    # Send empty data as keepalive
                    writer.write('')
                    await writer.drain()
                    last_keepalive = current_time
                    if config.get('debug', False):
                        print(f"Sent keepalive to {peername}")
                except Exception as e:
                    print(f"Keepalive failed for {peername}: {e}")
                    break
            
            # Check for terminal resize
            check_terminal_resize()
            
            # In live mode, periodically refresh data
            current_time = time.time()
            if not app.demo_mode and (current_time - last_data_update) >= app.update_interval:
                await reset_aircraft()
                last_data_update = current_time
            
            writer.write("\x1b[H")
            
            # Animate or display current aircraft
            current_aircraft = aircraft_ref['data']
            if current_aircraft:
                if app.demo_mode:
                    app._animate_demo_aircraft(current_aircraft)
                
                # Filter aircraft based on session-specific display mode
                mode = session_display_mode[0]
                
                if mode == 'closest' and airport_info:
                    from adsb_data import calculate_distance
                    airport_lat = airport_info['lat']
                    airport_lon = airport_info['lon']
                    limit = DISPLAY_CONFIG.get('display_aircraft_limit', 5)
                    
                    aircraft_with_pos = [a for a in current_aircraft if a.latitude is not None and a.longitude is not None]
                    sorted_aircraft = sorted(aircraft_with_pos, 
                                           key=lambda x: calculate_distance(airport_lat, airport_lon, x.latitude, x.longitude))
                    filtered_aircraft = sorted_aircraft[:limit]
                elif mode in ['high', 'medium', 'low']:
                    filtered_aircraft = []
                    for aircraft in current_aircraft:
                        if aircraft.altitude is not None:
                            if mode == 'high' and aircraft.altitude > 25000:
                                filtered_aircraft.append(aircraft)
                            elif mode == 'medium' and 10000 <= aircraft.altitude <= 25000:
                                filtered_aircraft.append(aircraft)
                            elif mode == 'low' and aircraft.altitude < 10000:
                                filtered_aircraft.append(aircraft)
                else:
                    filtered_aircraft = current_aircraft
                
                # Pass airport info to renderer
                airport_display_info = {
                    'lat': airport_info['lat'],
                    'lon': airport_info['lon'],
                    'code': airport_code
                } if airport_info else None
                renderer.total_aircraft_count = len(current_aircraft)
                display_output = renderer.render_to_string(filtered_aircraft, show_info=True, airport_info=airport_display_info)
            else:
                # No aircraft data
                airport_display_info = {
                    'lat': airport_info['lat'],
                    'lon': airport_info['lon'],
                    'code': airport_code
                } if airport_info else None
                renderer.total_aircraft_count = 0
                display_output = renderer.render_to_string([], show_info=True, airport_info=airport_display_info)
            
            lines = display_output.split('\n')
            for i, line in enumerate(lines):
                output_line = process_colored_line(line, terminal_width, config.get('use_colors', True))
                if i == len(lines) - 1 and not line:
                    continue
                writer.write(output_line)
            await writer.drain()

            # Check for force update or sleep
            if force_update.is_set():
                force_update.clear()
            else:
                await asyncio.sleep(0.1 if app.demo_mode else 1.0)

    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        print(f"Client {peername} disconnected: {e}")
    except asyncio.CancelledError:
        print("Terminal session cancelled.")
    except Exception as e:
        print(f"Error in terminal session for {peername}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"Closing connection for {peername}")
        rtask.cancel()
        input_task.cancel()
        if not writer.is_closing():
            try:
                writer.write("\x1b[?25h")  # Show cursor
                if protocol == 'telnet':
                    writer.close()
                # SSH writer close is handled differently
            except Exception:
                pass
