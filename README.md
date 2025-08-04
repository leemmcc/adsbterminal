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

## ADS-B Data Sources

### Supported Sources

1. **dump1090** (most common)
   - URL: `http://localhost:8080/data/aircraft.json`
   - Raspberry Pi FlightAware installations

2. **RTL1090**
   - URL: `http://localhost:31090/data/aircraft.json`

3. **Virtual Radar Server**
   - URL: `http://localhost:8080/VirtualRadar/AircraftList.json`

## Architecture

- `main.py`: Application entry point and command-line interface
- `adsb_data.py`: ADS-B data fetching and aircraft tracking
- `ascii_renderer.py`: ASCII art rendering and display
- `config.py`: Configuration settings

## License

MIT License - feel free to modify and distribute!

---

**Happy plane spotting!** ✈️📡
