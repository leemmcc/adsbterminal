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

### Telnet Server Mode

Run as a telnet server to allow remote connections:

```bash
python telnet_server.py
```

Then connect from any telnet client:
```bash
telnet localhost 8023
```

#### Telnet Server Hotkeys
- `r` - Refresh display and clear trails
- `t` - Toggle between showing all aircraft or only the closest aircraft
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

Edit `config.py` to customize settings for your local area and preferences.

## Telnet Server Approach

The Telnet server mode allows remote connections to view and interact with the ASCII radar display. This mode is ideal for shared and remote environments.

### Features

- Start the server using `python telnet_server.py`.
- Connect using any telnet client at `telnet localhost 8023`.
- Control display with hotkeys:
  - `r`: Refresh the display and clear trails.
  - `t`: Toggle between displaying all aircraft and only the closest aircraft (default 10).
  - `q`: Quit current session.
  - `x` or `s`: Shutdown the server completely.

## Architecture

- `main.py`: Application entry point and command-line interface
- `adsb_data.py`: ADS-B data fetching and aircraft tracking
- `ascii_renderer.py`: ASCII art rendering and display
- `config.py`: Configuration settings

## License

MIT License - feel free to modify and distribute!

---

## Development Philosophy

This project was developed with an AI-assisted "vibe coding" approach, allowing for creative and unconventional solutions. AI played a significant role in code suggestions and overall development style.

**Happy plane spotting!** ✈️📡
