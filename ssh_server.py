"""
SSH server implementation for ADS-B Terminal Radar.
Provides anonymous SSH access similar to telnet functionality.
"""

import asyncio
import asyncssh
import yaml
import sys
import threading
from terminal_handler import handle_terminal_session, config

# Global server reference for shutdown
_server = None
_shutdown_event = None


# Global speed configuration for SSH sessions
_ssh_speed = 10

class ADSBSSHServer(asyncssh.SSHServer):
    """Custom SSH server for anonymous access"""
    
    def __init__(self):
        pass
    
    def connection_made(self, conn):
        print(f'SSH connection received from {conn.get_extra_info("peername")}')
    
    def connection_lost(self, exc):
        if exc:
            print(f'SSH connection error: {exc}')
        else:
            print('SSH connection closed')
    
    def password_auth_supported(self):
        """Enable password authentication"""
        return True
    
    def validate_password(self, username, password):
        """Accept any username/password for anonymous access"""
        return True
    
    def begin_auth(self, username):
        """Begin authentication process"""
        # Return False to indicate no authentication is required
        return False


async def handle_ssh_client(process):
    """Handle SSH client connection"""
    try:
        # Get connection info
        conn = process.get_extra_info('connection')
        peername = conn.get_extra_info('peername')
        
        # Use global speed configuration
        speed = _ssh_speed
        
        # Set terminal to raw mode for character-at-a-time input
        # This disables line buffering and echo
        process.channel.set_echo(False)
        process.channel.set_line_mode(False)
        
        # Create SSH-compatible reader/writer
        reader = process.stdin
        writer = process.stdout
        
        # Add terminal size detection for SSH
        class SSHWriter:
            def __init__(self, writer, process):
                self._writer = writer
                self._process = process
                
            def write(self, data):
                # SSH writer expects strings, not bytes
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                self._writer.write(data)
                
            async def drain(self):
                await self._writer.drain()
                
            def is_closing(self):
                return self._writer.is_closing()
                
            def close(self):
                self._writer.close()
                
            def get_terminal_size(self):
                """Get terminal size from SSH session"""
                term_size = self._process.get_terminal_size()
                if term_size:
                    return term_size[0], term_size[1]  # columns, rows
                return None, None
        
        ssh_writer = SSHWriter(writer, process)
        
        # Handle the terminal session
        await handle_terminal_session(reader, ssh_writer, speed, peername, protocol='ssh')
        
    except Exception as e:
        print(f'Error handling SSH client: {e}')
        import traceback
        traceback.print_exc()
    finally:
        process.exit(0)


def keyboard_monitor(loop, shutdown_event):
    """Monitor keyboard input in server console"""
    print("\nPress 'x' or 's' in this console to shutdown the SSH server...\n")
    
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


async def start_ssh_server(port=8024, speed=10):
    """Start the SSH server"""
    global _server, _shutdown_event, _ssh_speed
    
    # Set global speed
    _ssh_speed = speed
    
    print(f"Starting SSH server on port {port}...")
    print(f"Demo mode: {config.get('demomode', True)}, Speed: {speed}, Interval: {config.get('interval', 1)}")
    print("SSH server configured for anonymous access - any username/password will work")
    
    # Create shutdown event
    _shutdown_event = asyncio.Event()
    
    # Get current event loop
    loop = asyncio.get_running_loop()
    
    # Start keyboard monitoring thread
    keyboard_thread = threading.Thread(target=keyboard_monitor, args=(loop, _shutdown_event), daemon=True)
    keyboard_thread.start()
    
    # Generate a temporary host key for this session
    # In production, you'd want to save/load a persistent host key
    host_key = asyncssh.generate_private_key('ssh-rsa')
    
    # Create SSH server factory
    def server_factory():
        return ADSBSSHServer()
    
    # Start SSH server
    _server = await asyncssh.create_server(
        server_factory,
        '',  # Listen on all interfaces
        port,
        server_host_keys=[host_key],
        process_factory=handle_ssh_client,
        encoding='utf-8',
        server_version='ADS-B-Terminal-SSH-1.0'
    )
    
    print(f"SSH server listening on port {port}")
    print(f"Connect using: ssh -p {port} guest@localhost")
    print("(Any username/password combination will work)")
    
    try:
        # Wait for shutdown event
        await _shutdown_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        print("\nShutting down SSH server...")
        _server.close()
        await _server.wait_closed()
        _server = None
        print("SSH server shutdown complete.")


async def main(port=8024, speed=10):
    """Main entry point for SSH server"""
    await start_ssh_server(port, speed)


if __name__ == '__main__':
    # Get configuration
    ssh_port = config.get('ssh_port', 8024)
    speed = config.get('speed', 10)
    
    try:
        asyncio.run(main(port=ssh_port, speed=speed))
    except KeyboardInterrupt:
        print("SSH server shut down.")
