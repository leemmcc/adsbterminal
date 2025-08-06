# ADS-B ASCII Art Radar

A Python application that displays aircraft tracking data from ADS-B sources as ASCII art in your terminal. Perfect for aviation enthusiasts who want a retro radar display!

## Features

- 🛩️ Real-time aircraft tracking from ADS-B sources
- 🎨 Multiple ASCII art styles (simple, detailed, classic)
- 🌈 Color-coded aircraft by altitude
- 🛤️ Aircraft trail visualization
- 📊 Live aircraft information display
- 🎮 Demo mode with simulated aircraft
- ⚙️ Configurable display bounds and settings

## Installation

### Prerequisites

- Python 3.7 or higher
- An ADS-B data source (dump1090, RTL1090, Virtual Radar Server, etc.)

### Install Dependencies

```bash
cd adsb-ascii-art
pip install -r requirements.txt
```

## Usage

### Demo Mode (No ADS-B Required)

Try the demo mode first to see how it works:

```bash
python main.py --demo
```

### Server Modes

#### Telnet Server Mode

Run as a telnet server to allow remote connections:

```bash
python telnet_server.py
```

Then connect from any telnet client:
```bash
telnet localhost 8023
```

#### SSH Server Mode

Run as an SSH server for secure connections:

```bash
python ssh_server.py
```

Then connect via SSH (accepts any username/password):
```bash
ssh -p 8025 guest@localhost
```

#### Combined Server Mode (Recommended)

Run both telnet and SSH servers simultaneously:

```bash
python combined_server.py
```

This starts both servers:
- Telnet on port 8023: `telnet localhost 8023`
- SSH on port 8025: `ssh -p 8025 guest@localhost`

#### Server Hotkeys
- `r` - Refresh display and clear trails
- `t` - Toggle display mode (cycles through: all → closest → high → medium → low)
- `q` - Quit current session
- `x` or `s` - Shutdown the server completely

### Live Mode with ADS-B Data

If you have dump1090 or another ADS-B source running:

```bash
# Default (assumes dump1090 on localhost:8080)
python main.py

# Custom data source
python main.py --url http://your-pi:8080/data/aircraft.json

# Custom map bounds (lat_min,lon_min,lat_max,lon_max)
python main.py --bounds 40.5,-74.5,41.5,-73.5

# Different ASCII style
python main.py --style detailed

# Faster updates
python main.py --interval 2
```

### Command Line Options

- `--demo`: Run in demo mode with simulated aircraft
- `--style {simple,detailed,classic}`: Choose ASCII art style
- `--bounds LAT_MIN,LON_MIN,LAT_MAX,LON_MAX`: Set map display bounds
- `--url URL`: Specify ADS-B data source URL
- `--interval N`: Update interval in seconds (default: 5)
- `--verbose`: Enable detailed logging
- `--help`: Show help message

## Configuration

Edit `config.yaml` to customize settings:
- Server ports (telnet and SSH)
- Demo mode on/off
- Airport location and search radius
- Display options (colors, symbols, trail length)
- Terminal size overrides
- Update intervals and speed

## Telnet Server Approach

The Telnet server mode allows remote connections to view and interact with the ASCII radar display. This mode is ideal for shared and remote environments.

### Features

- Start the server using `python telnet_server.py`.
- Connect using any telnet client at `telnet localhost 8023`.
- Control display with hotkeys:
  - `r`: Refresh the display and clear trails.
  - `t`: Toggle display mode - cycles through:
    - **all**: Show all aircraft
    - **closest**: Show only the 10 closest aircraft to the airport
    - **high**: Show only aircraft above 25,000 feet
    - **medium**: Show only aircraft between 10,000-25,000 feet
    - **low**: Show only aircraft below 10,000 feet
  - `q`: Quit current session.
  - `x` or `s`: Shutdown the server completely.

## Architecture

- `main.py`: Application entry point and command-line interface
- `adsb_data.py`: ADS-B data fetching and aircraft tracking
- `ascii_renderer.py`: ASCII art rendering and display
- `terminal_handler.py`: Shared terminal session handler for both telnet and SSH
- `telnet_server.py`: Telnet server implementation
- `ssh_server.py`: SSH server implementation with anonymous access
- `combined_server.py`: Runs both telnet and SSH servers simultaneously
- `config.yaml`: Configuration file for all settings
- `config.py`: Configuration constants and defaults

## License

MIT License - feel free to modify and distribute!

---

## Development Philosophy

This project was developed with an AI-assisted "vibe coding" approach, allowing for creative and unconventional solutions. AI played a significant role in code suggestions and overall development style.

**Happy plane spotting!** ✈️📡
