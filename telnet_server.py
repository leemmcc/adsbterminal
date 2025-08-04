import asyncio
import telnetlib3
import yaml
import re
import signal
import time
import threading
import sys
from datetime import datetime
from ascii_renderer import ASCIIRenderer, create_demo_aircraft
from main import ADSBRadarApp
from adsb_api import fetch_aircraft_near_airport, ADSBApiClient, AIRPORTS, calculate_bounds_from_point
from config import PROCESSING_CONFIG, DISPLAY_CONFIG

# Load config file at module level
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

# Global server reference for shutdown
_server = None
_shutdown_event = None  # Will be created in the async context

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
            
            # wcswidth can be slow, but it's correct for unicode
            # For now, we'll stick with len, assuming simple chars
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
                await queue.put(None) # Signal EOF
                break
            await queue.put(char)
        except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
            await queue.put(None) # Signal EOF
            break

async def handle_input(queue, app, on_reset, force_update, session_display_mode):
    """Handles user input from the queue."""
    global _server
    while app.running:
        try:
            char = await asyncio.wait_for(queue.get(), timeout=0.1)
            if char is None: # EOF
                app.running = False
                break

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
                    session_display_mode[0] = 'closest' if session_display_mode[0] == 'all' else 'all'
                    print(f"Display mode changed to: {session_display_mode[0].upper()} (session-specific)")
                    # Force screen update
                    force_update.set()
        except asyncio.TimeoutError:
            continue

async def detect_terminal_size(reader, writer):
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

async def shell(speed, reader, writer):
    peername = writer.get_extra_info('peername')
    print(f"Client connected from {peername}")
    
    # Note: Need to find proper way to disable timeout in telnetlib3

    input_queue = asyncio.Queue()
    
    # Enable character mode and disable echo
    # telnetlib3 handles most telnet negotiation automatically
    # The library works in character mode by default when reading single characters
    
    # Give telnet client time to establish connection
    await asyncio.sleep(0.2)
    
    # --- Terminal Size Detection (before starting reader task) ---
    terminal_width, terminal_height = None, None
    config_width, config_height = config.get('terminal_width'), config.get('terminal_height')

    if config_width and config_height:
        terminal_width, terminal_height = int(config_width), int(config_height)
        print(f"Using configured terminal size: {terminal_width}x{terminal_height}")
    else:
        print(f"Attempting terminal size detection for {peername}...")
        # telnetlib3 handles NAWS negotiation automatically
        await writer.drain()
        await asyncio.sleep(0.1)
        if hasattr(writer, 'get_extra_info') and writer.get_extra_info('columns'):
            terminal_width = writer.get_extra_info('columns')
            terminal_height = writer.get_extra_info('lines')
            print(f"Detected size via NAWS: {terminal_width}x{terminal_height}")

        if not terminal_width:
            print("NAWS failed, trying cursor position query...")
            terminal_width, terminal_height = await detect_terminal_size(reader, writer)
            if terminal_width:
                print(f"Detected size via cursor query: {terminal_width}x{terminal_height}")

    if not terminal_width or not terminal_height:
        # Use a more reasonable default for modern terminals
        # Most modern terminals are wider than 80 columns
        terminal_width, terminal_height = 120, 40
        print(f"All detection methods failed. Using modern default size: {terminal_width}x{terminal_height}")
        print("Tip: You can set custom terminal size in config.yaml by uncommenting terminal_width and terminal_height")
    
    # Start the reader task AFTER terminal size detection
    rtask = asyncio.create_task(reader_task(reader, input_queue))

    # --- App Setup ---
    print(f"Final terminal size: width={terminal_width}, height={terminal_height}")
    # Session-specific display mode (use list to make it mutable)
    session_display_mode = ['all']  # Default to showing all aircraft
    
    DISPLAY_CONFIG.update({
        'terminal_width': terminal_width,
        'terminal_height': terminal_height,
        'demo_mode': config.get('demomode', True),
        'speed_multiplier': speed,
        'use_unicode_symbols': config.get('use_unicode_symbols', False),
        'airport': config.get('airport', 'RDU'),
        'radius': config.get('radius', 25),
        'display_aircraft_limit': config.get('display_aircraft_limit', 10)
    })
    
    # Function to check for terminal resize
    def check_terminal_resize():
        nonlocal terminal_width, terminal_height, renderer
        new_width = writer.get_extra_info('columns')
        new_height = writer.get_extra_info('lines')
        
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
            
            # Force screen update
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
    # Store session display mode in renderer for info panel
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
            print("Re-detecting terminal size...")
            # Try NAWS first
            new_width = writer.get_extra_info('columns')
            new_height = writer.get_extra_info('lines')
            
            if new_width and new_height:
                terminal_width = new_width
                terminal_height = new_height
                print(f"Detected size via NAWS: {terminal_width}x{terminal_height}")
            else:
                # NAWS failed, try cursor position query
                print("NAWS failed, trying cursor position query...")
                # We need to pause the reader task temporarily
                rtask.cancel()
                await asyncio.sleep(0.1)
                
                detected_width, detected_height = await detect_terminal_size(reader, writer)
                if detected_width and detected_height:
                    terminal_width = detected_width
                    terminal_height = detected_height
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
            
            # Clear trails as part of refresh
            clear_trails = True
        
        # If we need to clear trails (including on initial load)
        if clear_trails:
            if tracked_aircraft:
                # Clear trails for all tracked aircraft
                for aircraft in tracked_aircraft.values():
                    aircraft.position_history = []
                if config.get('debug', False):
                    print("Cleared all aircraft trails")
                # If not fetching new data, just update display
                if not refresh_display and not app.demo_mode:
                    # Update the display reference
                    aircraft_ref['data'] = list(tracked_aircraft.values())
                    # Trigger immediate screen update
                    force_update.set()
                    return
        
        # Otherwise, fetch new data as usual
        new_data = await fetch_aircraft()
        
        if app.demo_mode:
            # For demo mode, just use the new data as-is
            aircraft_ref['data'] = new_data
        else:
            # For live mode, maintain position history unless clearing
            current_icaos = set()
            updated_aircraft = []
            
            for new_aircraft in new_data:
                icao = new_aircraft.icao
                current_icaos.add(icao)
                
                # Check if we're already tracking this aircraft
                if icao in tracked_aircraft:
                    # Update existing aircraft while preserving history (unless clearing trails)
                    existing = tracked_aircraft[icao]
                    # Copy position history to new aircraft object (unless clearing trails)
                    if not clear_trails:
                        new_aircraft.position_history = existing.position_history.copy()
                    else:
                        new_aircraft.position_history = []
                    
                    # Debug: Show position changes
                    if existing.latitude and existing.longitude:
                        lat_diff = abs(new_aircraft.latitude - existing.latitude) if new_aircraft.latitude else 0
                        lon_diff = abs(new_aircraft.longitude - existing.longitude) if new_aircraft.longitude else 0
                        if lat_diff > 0 or lon_diff > 0:
                            if config.get('debug', False):
                                print(f"Aircraft {icao} moved: lat_diff={lat_diff:.6f}, lon_diff={lon_diff:.6f}")
                    
                    # Check if position has changed enough to add to history
                    if new_aircraft.latitude and new_aircraft.longitude:
                        # Calculate distance from last position in history
                        should_add = False
                        if not new_aircraft.position_history:
                            should_add = True
                        else:
                            last_lat, last_lon, _ = new_aircraft.position_history[-1]
                            # Use a distance threshold to ensure unique visible points
                            # Adjust this based on your map scale - smaller = more points
                            from adsb_data import calculate_distance
                            dist = calculate_distance(last_lat, last_lon, new_aircraft.latitude, new_aircraft.longitude)
                            if dist > 0.5:  # 0.5 nautical miles minimum between points
                                should_add = True
                                
                        if should_add:
                            new_aircraft.position_history.append((new_aircraft.latitude, new_aircraft.longitude, datetime.now()))
                            # Limit history length
                            max_history = config.get('trail_length', PROCESSING_CONFIG.get('trail_length', 15))
                            if len(new_aircraft.position_history) > max_history:
                                new_aircraft.position_history = new_aircraft.position_history[-max_history:]
                            if config.get('debug', False):
                                print(f"Aircraft {icao} trail grew to {len(new_aircraft.position_history)} unique points")
                else:
                    # New aircraft - add initial position to history (unless clearing trails)
                    if new_aircraft.latitude and new_aircraft.longitude and not clear_trails:
                        new_aircraft.position_history.append((new_aircraft.latitude, new_aircraft.longitude, datetime.now()))
                        if config.get('debug', False):
                            print(f"New aircraft {icao} starting with 1 trail point")
                
                tracked_aircraft[icao] = new_aircraft
                updated_aircraft.append(new_aircraft)
            
            # Remove aircraft that are no longer being tracked
            for icao in list(tracked_aircraft.keys()):
                if icao not in current_icaos:
                    del tracked_aircraft[icao]
                    if config.get('debug', False):
                        print(f"Stopped tracking {icao}")
            
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
    
    # Give the terminal a moment to stabilize and then force a size detection
    await asyncio.sleep(0.5)
    
    # Force a terminal size re-detection before first display
    print("Performing final terminal size detection...")
    new_width = writer.get_extra_info('columns')
    new_height = writer.get_extra_info('lines')
    
    if new_width and new_height and (new_width != terminal_width or new_height != terminal_height):
        terminal_width = new_width
        terminal_height = new_height
        print(f"Updated terminal size: {terminal_width}x{terminal_height}")
        
        # Update display config
        DISPLAY_CONFIG.update({
            'terminal_width': terminal_width,
            'terminal_height': terminal_height
        })
        
        # Recreate renderer with new dimensions
        renderer = ASCIIRenderer()
        print("Renderer recreated with updated dimensions")
    last_data_update = time.time()
    last_keepalive = time.time()
    update_counter = 0
    keepalive_interval = config.get('keepalive_interval', 30)  # Configurable keepalive
    
    try:
        while app.running:
            if writer.is_closing():
                print(f"Client {peername} connection closed.")
                break
            
            # Send periodic keepalive to prevent timeout
            current_time = time.time()
            if keepalive_interval > 0 and current_time - last_keepalive > keepalive_interval:
                try:
                    # Send a NOP telnet command as keepalive
                    # For telnetlib3, we send a simple newline as keepalive
                    writer.write('')
                    await writer.drain()
                    last_keepalive = current_time
                    if config.get('debug', False):
                        print(f"Sent keepalive to {peername} at {datetime.now().strftime('%H:%M:%S')}")
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
                if session_display_mode[0] == 'closest' and airport_info:
                    # Sort by distance and take only the closest
                    from adsb_data import calculate_distance
                    airport_lat = airport_info['lat']
                    airport_lon = airport_info['lon']
                    limit = DISPLAY_CONFIG.get('display_aircraft_limit', 10)
                    
                    # Filter out aircraft without position data
                    aircraft_with_pos = [a for a in current_aircraft if a.latitude is not None and a.longitude is not None]
                    
                    # Sort by distance to airport
                    sorted_aircraft = sorted(aircraft_with_pos, 
                                           key=lambda x: calculate_distance(airport_lat, airport_lon, x.latitude, x.longitude))
                    
                    # Take only the closest aircraft
                    filtered_aircraft = sorted_aircraft[:limit]
                else:
                    # Show all aircraft
                    filtered_aircraft = current_aircraft
                
                # Pass airport info to renderer
                airport_display_info = {
                    'lat': airport_info['lat'],
                    'lon': airport_info['lon'],
                    'code': airport_code
                } if airport_info else None
                display_output = renderer.render_to_string(filtered_aircraft, show_info=True, airport_info=airport_display_info)
            else:
                # No aircraft data
                airport_display_info = {
                    'lat': airport_info['lat'],
                    'lon': airport_info['lon'],
                    'code': airport_code
                } if airport_info else None
                display_output = renderer.render_to_string([], show_info=True, airport_info=airport_display_info)
            
            lines = display_output.split('\n')
            for i, line in enumerate(lines):
                output_line = process_colored_line(line, terminal_width, config.get('use_colors', True))
                # Don't add extra newline after the last line
                if i == len(lines) - 1 and not line:
                    continue
                writer.write(output_line)
            await writer.drain()

            # Check for force update or sleep
            if force_update.is_set():
                force_update.clear()
                # Immediate update, no sleep
            else:
                # Use a shorter sleep interval for smoother updates
                await asyncio.sleep(0.1 if app.demo_mode else 1.0)

    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        print(f"Client {peername} disconnected: {e}")
    except asyncio.CancelledError:
        print("Shell task cancelled.")
    except Exception as e:
        print(f"Error in shell for {peername}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"Closing connection for {peername}")
        rtask.cancel()
        input_task.cancel()
        if not writer.is_closing():
            try:
                writer.write("\x1b[?25h")
                writer.close()
            except Exception:
                pass

def keyboard_monitor(loop, shutdown_event):
    """Monitor keyboard input in server console"""
    print("\nPress 'x' or 's' in this console to shutdown the server...\n")
    
    try:
        import msvcrt  # Windows
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                if key in ['x', 's']:
                    print("\nShutdown command received from console.")
                    # Create a coroutine to set the event
                    async def set_shutdown():
                        shutdown_event.set()
                    asyncio.run_coroutine_threadsafe(set_shutdown(), loop)
                    break
    except ImportError:
        # Unix/Linux - use different approach
        import termios, tty
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            while True:
                key = sys.stdin.read(1).lower()
                if key in ['x', 's']:
                    print("\nShutdown command received from console.")
                    # Create a coroutine to set the event
                    async def set_shutdown():
                        shutdown_event.set()
                    asyncio.run_coroutine_threadsafe(set_shutdown(), loop)
                    break
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

async def main(port=8023, speed=10):
    global _server, _shutdown_event
    print(f"Starting telnet server on port {port}...")
    print(f"Demo mode: {config.get('demomode', True)}, Speed: {config.get('speed', 10)}, Interval: {config.get('interval', 1)}")
    
    # Create shutdown event in the async context
    _shutdown_event = asyncio.Event()
    
    # Get current event loop
    loop = asyncio.get_running_loop()
    
    # Start keyboard monitoring thread
    keyboard_thread = threading.Thread(target=keyboard_monitor, args=(loop, _shutdown_event), daemon=True)
    keyboard_thread.start()
    
    # Create server with no timeout (timeout=None disables it)
    server = await telnetlib3.create_server(
        port=port, 
        shell=lambda r, w: shell(speed, r, w),
        timeout=None  # Disable connection timeout
    )
    _server = server  # Store server reference globally
    for sock in server.sockets:
        print(f"Listening on interface {sock.getsockname()[0]}:{sock.getsockname()[1]}")
    
    try:
        # Create tasks for both server and shutdown monitoring
        server_task = asyncio.create_task(server.serve_forever())
        shutdown_task = asyncio.create_task(_shutdown_event.wait())
        
        # Wait for either server to stop or shutdown event
        done, pending = await asyncio.wait(
            {server_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel any pending tasks
        for task in pending:
            task.cancel()
            
    except asyncio.CancelledError:
        pass
    finally:
        print("\nShutting down server...")
        server.close()
        await server.wait_closed()
        _server = None
        print("Server shutdown complete.")

if __name__ == '__main__':
    import argparse

    port = config.get('port', 8023)
    speed = config.get('speed', 10)
    
    try:
        asyncio.run(main(port=port, speed=speed))
    except KeyboardInterrupt:
        print("Server shut down.")

