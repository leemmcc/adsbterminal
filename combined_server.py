"""
Combined server script that runs both telnet and SSH servers for ADS-B Terminal Radar.
This allows clients to connect via either protocol.
"""

import asyncio
import sys
import threading
from terminal_handler import config
from telnet_server import main as telnet_main
from ssh_server import main as ssh_main


def keyboard_monitor(shutdown_event):
    """Monitor keyboard input for shutdown command"""
    print("\nPress 'x' or 's' in this console to shutdown all servers...\n")
    
    try:
        import msvcrt  # Windows
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                if key in ['x', 's']:
                    print("\nShutdown command received from console.")
                    shutdown_event.set()
                    break
    except ImportError:
        # Unix/Linux
        import termios, tty
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            while True:
                key = sys.stdin.read(1).lower()
                if key in ['x', 's']:
                    print("\nShutdown command received from console.")
                    shutdown_event.set()
                    break
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


async def run_combined_servers():
    """Run both telnet and SSH servers concurrently"""
    
    # Get configuration
    telnet_port = config.get('port', 8023)
    ssh_port = config.get('ssh_port', 8024)
    speed = config.get('speed', 10)
    
    print("=" * 60)
    print("ADS-B Terminal Radar - Combined Server Mode")
    print("=" * 60)
    print(f"Demo mode: {config.get('demomode', True)}")
    print(f"Speed: {speed}")
    print(f"Update interval: {config.get('interval', 1)} seconds")
    print(f"Airport: {config.get('airport', 'RDU')}")
    print(f"Radius: {config.get('radius', 25)} nm")
    print("=" * 60)
    
    # Create tasks for both servers
    telnet_task = asyncio.create_task(telnet_main(port=telnet_port, speed=speed))
    ssh_task = asyncio.create_task(ssh_main(port=ssh_port, speed=speed))
    
    # Create shutdown event
    shutdown_event = threading.Event()
    
    # Start keyboard monitor in separate thread
    keyboard_thread = threading.Thread(target=keyboard_monitor, args=(shutdown_event,), daemon=True)
    keyboard_thread.start()
    
    print("\nServers are starting...")
    print(f"\nConnect via Telnet: telnet localhost {telnet_port}")
    print(f"Connect via SSH: ssh -p {ssh_port} guest@localhost")
    print("\n(SSH accepts any username/password for anonymous access)")
    print("\n" + "=" * 60)
    
    try:
        # Wait for either server to complete or shutdown event
        while not shutdown_event.is_set():
            # Check if any server task has completed (error condition)
            done, pending = await asyncio.wait(
                {telnet_task, ssh_task},
                timeout=1.0,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            if done:
                # One of the servers crashed
                for task in done:
                    try:
                        await task
                    except Exception as e:
                        print(f"\nServer error: {e}")
                break
                
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received")
    finally:
        print("\nShutting down all servers...")
        
        # Cancel all server tasks
        telnet_task.cancel()
        ssh_task.cancel()
        
        # Wait for tasks to complete cancellation
        await asyncio.gather(telnet_task, ssh_task, return_exceptions=True)
        
        print("All servers shut down.")


async def main():
    """Main entry point"""
    await run_combined_servers()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
