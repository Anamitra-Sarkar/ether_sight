# ETHER-SIGHT: Real-Time BLE Radar Scanner

<p align="center">
  <strong>Visualize all nearby invisible Bluetooth Low Energy devices on a Radar Scope</strong>
</p>

---

## Overview

**ETHER-SIGHT** is a real-time Bluetooth Low Energy (BLE) radar scanner that visualizes nearby BLE devices on a polar radar plot. Devices are positioned based on their signal strength (RSSI), converted to an estimated distance, with a simulated angle for stable on-screen positioning.

### Features

- 🔍 **Real-time BLE scanning** using the `bleak` library
- 📡 **RSSI to distance conversion** using the log-distance path loss model
- 📊 **Dark mode radar visualization** with green grid on black background
- 🔺 **Device differentiation**: Red triangles for named devices, green dots for unknown
- 🌅 **Fade effect**: Devices fade out over 5 seconds when they stop broadcasting
- 🖥️ **Cross-platform**: Works on Linux (including Zorin) and Windows

## Screenshots

When running, the radar displays:
- **Red Triangles (▲)**: Named devices (e.g., "Anamitra's iPhone")
- **Green Dots (●)**: Unknown devices (showing partial MAC address)

## Requirements

- Python 3.8+
- Linux (tested on Zorin OS) or Windows 10/11
- Bluetooth adapter

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/Anamitra-Sarkar/ether_sight.git
   cd ether_sight
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Live Scanning Mode

```bash
# On Linux, you may need root privileges:
sudo python main.py

# On Windows (run as Administrator if needed):
python main.py
```

### Demo Mode

Run with simulated devices (no Bluetooth required):
```bash
python main.py --demo
```

### Verbose Mode

Enable detailed logging:
```bash
python main.py --verbose
```

### Command Line Options

```
usage: main.py [-h] [--demo] [-v]

ETHER-SIGHT: Real-Time BLE Radar Scanner

optional arguments:
  -h, --help     show this help message and exit
  --demo         Run in demo mode with simulated devices
  -v, --verbose  Enable verbose logging

Examples:
  python main.py           # Run with live BLE scanning
  python main.py --demo    # Run with simulated devices
  sudo python main.py      # Run with elevated permissions (Linux)

Legend:
  Red Triangle  = Named device (e.g., "Anamitra's iPhone")
  Green Dot     = Unknown device (MAC address only)
```

## Architecture

### Core Components

#### 1. `scanner.py` - BLE Scanner Module
- **Async BLE Scanning**: Continuous discovery using `bleak` library
- **RSSI to Distance Conversion**: Uses the log-distance path loss formula:
  ```
  Distance = 10 ^ ((TxPower - RSSI) / (10 * N))
  ```
  - TxPower = -59 dBm (reference RSSI at 1 meter)
  - N = 2 (path loss exponent for free space)
- **Stable Angle Assignment**: MD5 hash of MAC address generates consistent angles
- **Device Tracking**: Maintains device list with timestamps for fade effects

#### 2. `radar_ui.py` - Radar Visualization Module
- **Matplotlib Polar Plot**: Dark mode radar with concentric distance rings
- **Color Scheme**:
  - Background: Black (`#000000`)
  - Grid: Green (`#00FF00`)
  - Named devices: Red triangles
  - Unknown devices: Green dots
- **Animation**: 100ms refresh rate with rotating sweep line
- **Fade Effect**: 5-second fade-out for lost devices

#### 3. `main.py` - Application Entry Point
- **Thread Management**: Scanner runs in background thread
- **Signal Handling**: Graceful shutdown on Ctrl+C
- **Permission Handling**: Clear error messages for permission issues
- **Demo Mode**: Simulated devices for testing without Bluetooth

## Troubleshooting

### Permission Denied (Linux)

If you see "Permission denied" errors:

```bash
# Option 1: Run with sudo
sudo python main.py

# Option 2: Add user to bluetooth group (permanent fix)
sudo usermod -a -G bluetooth $USER
# Then log out and back in
```

### No Bluetooth Adapter Found

Ensure your Bluetooth adapter is enabled:
```bash
# Linux
sudo systemctl start bluetooth
bluetoothctl power on

# Windows
# Enable Bluetooth in Settings > Bluetooth & devices
```

### Missing Dependencies

```bash
pip install -r requirements.txt
```

## Distance Estimation

The RSSI-to-distance conversion uses the **log-distance path loss model**:

```
Distance (meters) = 10 ^ ((TxPower - RSSI) / (10 * N))
```

Where:
- **TxPower** = -59 dBm (typical BLE reference power at 1 meter)
- **N** = 2 (path loss exponent for free space)
- **RSSI** = Received Signal Strength Indicator (in dBm)

> ⚠️ **Note**: This is an estimation. Actual distances may vary due to obstacles, interference, and environmental factors.

## Triangulation (Simulation)

Since we have only one antenna, true triangulation isn't possible. Instead:
- Each device's **angle** is derived from a hash of its MAC address
- This provides **stable positioning** on the radar (same device = same angle)
- Only the **distance** (radius) updates in real-time based on RSSI

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

ETHER-SIGHT Team

---

<p align="center">
  <sub>Built with 📡 by the ETHER-SIGHT Team</sub>
</p>
