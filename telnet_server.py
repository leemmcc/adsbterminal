import asyncio
import telnetlib3
import yaml
import sys
import threading
from terminal_handler import handle_terminal_session, config

# Global server reference for shutdown
_server = None
_shutdown_event = None  # Will be created in the async context

async def shell(speed, reader, writer):
    """Telnet shell handler that uses the shared terminal session handler"""
    peername = writer.get_extra_info('peername')
    await handle_terminal_session(reader, writer, speed, peername, protocol='telnet')

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

