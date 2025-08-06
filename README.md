# ADS-B Terminal Radar

A remote-accessible terminal-based aircraft radar display that serves real-time ADS-B tracking data via Telnet and SSH. Connect from anywhere to view live aircraft positions in a retro ASCII art interface.

**Note:** This is a proof-of-concept project that demonstrates remote terminal-based ADS-B visualization. While functional, it's not intended for production use and likely won't receive significant updates beyond its current state.

## Features

- 🌐 **Remote Access**: Connect via Telnet (port 8023) or SSH (port 8025)
- 🛩️ Real-time aircraft tracking from ADS-B Exchange API
- 📡 Airport-centric view with configurable radius
- 🎨 ASCII art radar display with aircraft symbols
- 🌈 Color-coded aircraft by altitude
- 🛤️ Aircraft trail visualization
- 📊 Live aircraft information panel
- 🎮 Demo mode with simulated aircraft for testing
- 🖥️ Automatic terminal size detection and resize handling
- ⚙️ Fully configurable via YAML

## Quick Start

### Prerequisites

- Python 3.7 or higher
- Internet connection (for ADS-B Exchange API)

### Installation

```bash
git clone https://github.com/leemmcc/adsbterminal
cd adsbterminal
pip install -r requirements.txt
```

## Remote Access Setup

### Running the Server

The recommended way to run the server is using the combined mode, which starts both Telnet and SSH servers:

```bash
python combined_server.py
```

This starts:
- **Telnet server on port 8023** - Simple, no authentication required
- **SSH server on port 8025** - Secure, accepts any username/password

### Connecting to the Server

#### Via Telnet (Simple)
```bash
telnet your-server-ip 8023
```

#### Via SSH (Secure)
```bash
ssh -p 8025 anyuser@your-server-ip
# Password: anything (authentication is not enforced)
```

### Remote Access Features

- **Automatic Terminal Size Detection**: The display adapts to your terminal size
- **Terminal Resize Support**: Resize your terminal window and press 'r' to refresh
- **Multi-client Support**: Multiple users can connect simultaneously
- **Session Persistence**: Each session maintains its own display settings
- **Low Bandwidth**: Uses efficient terminal control codes

### Interactive Controls

Once connected, use these keyboard commands:

- `r` - **Refresh display**: Re-detects terminal size and clears trails
- `t` - **Toggle display mode**: Cycles through different views
  - `all` - Show all aircraft in range
  - `closest` - Show only the 5 nearest aircraft
  - `high` - Aircraft above 25,000 feet
  - `medium` - Aircraft between 10,000-25,000 feet  
  - `low` - Aircraft below 10,000 feet
- `q` - **Quit session**: Disconnect from server


## Configuration

Edit `config.yaml` to customize your setup:

```yaml
# Server Configuration
telnet_port: 8023        # Telnet server port
ssh_port: 8025           # SSH server port

# Display Configuration  
airport: 'RDU'           # Airport code (RDU, JFK, LAX, ORD, ATL, DFW, DEN, SEA, SFO, BOS, IAD, CLT, LAS, PHX, MIA)
radius: 25               # Search radius in nautical miles
demomode: false          # Set to true for simulated aircraft

# Terminal Settings
terminal_width: null     # Auto-detect if null, or set fixed width
terminal_height: null    # Auto-detect if null, or set fixed height
use_colors: true         # Enable/disable colors
use_unicode_symbols: false  # Use Unicode aircraft symbols

# Update Settings
interval: 1              # Data refresh interval in seconds
trail_length: 15         # Number of trail points to show
```

## Demo Mode

To test without live data, enable demo mode in `config.yaml`:

```yaml
demomode: true
```

This simulates aircraft movements around your configured airport for testing and demonstration purposes.

## Technical Details

### Data Source
The application fetches live aircraft data from the ADS-B Exchange API, which provides global coverage of ADS-B equipped aircraft.

### Terminal Compatibility
- Works with any ANSI-compatible terminal
- Tested with: PuTTY, Windows Terminal, macOS Terminal, iTerm2, Linux terminals
- Minimum recommended terminal size: 80x24
- Optimal terminal size: 120x40 or larger

### Network Requirements
- Outbound HTTPS to api.adsb.lol for aircraft data
- Inbound TCP ports 8023 (Telnet) and 8025 (SSH) for client connections

## Known Limitations

- SSH terminal resize on some clients may require manual refresh (press 'r')
- Telnet connections are unencrypted - use SSH for secure connections
- API rate limits may apply for very frequent updates
- Aircraft data accuracy depends on ADS-B coverage in your selected area

## License

MIT License - feel free to modify and distribute!

---

## Development Notes

This project was created as a proof-of-concept to demonstrate remote terminal-based ADS-B visualization. It was developed with an AI-assisted approach, exploring creative solutions for terminal rendering and remote access. While functional and fun to use, it's not intended for mission-critical applications.

**Happy plane spotting from anywhere!** ✈️📡
