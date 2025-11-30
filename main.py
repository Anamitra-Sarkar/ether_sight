#!/usr/bin/env python3
"""
ETHER-SIGHT: Real-Time Bluetooth Low Energy (BLE) Radar Scanner

Main entry point that coordinates the BLE scanner and radar UI.

This application visualizes nearby BLE devices on a radar scope based
on their signal strength (RSSI).

Usage:
    python main.py [--demo]
    
    On Linux, you may need to run with sudo:
        sudo python main.py

Author: ETHER-SIGHT Team
License: Apache 2.0
"""

import argparse
import asyncio
import logging
import signal
import sys
import threading
import time
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import local modules
try:
    from scanner import BLERadarScanner, BLEDevice
    from radar_ui import RadarDisplay
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Please ensure scanner.py and radar_ui.py are in the same directory.")
    sys.exit(1)


class EtherSight:
    """
    Main application class coordinating BLE scanning and radar visualization.
    """
    
    def __init__(self, demo_mode: bool = False) -> None:
        """
        Initialize ETHER-SIGHT application.
        
        Args:
            demo_mode: If True, run with simulated devices instead of real scanning
        """
        self.demo_mode = demo_mode
        self.devices: Dict[str, BLEDevice] = {}
        self._devices_lock = threading.Lock()
        self._running = False
        self._scanner: Optional[BLERadarScanner] = None
        self._radar: Optional[RadarDisplay] = None
        self._scan_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def _on_device_update(self, devices: Dict[str, BLEDevice]) -> None:
        """
        Callback for scanner device updates.
        
        Args:
            devices: Updated device dictionary
        """
        with self._devices_lock:
            self.devices = devices.copy()
    
    def _get_devices(self) -> Dict[str, BLEDevice]:
        """
        Get current device dictionary (thread-safe).
        
        Returns:
            Copy of current devices dictionary
        """
        with self._devices_lock:
            return self.devices.copy()
    
    def _run_scanner_loop(self) -> None:
        """Run the async BLE scanner in a separate thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        self._scanner = BLERadarScanner(
            on_device_update=self._on_device_update
        )
        
        try:
            self._loop.run_until_complete(self._scanner.start_scanning())
        except asyncio.CancelledError:
            pass
        except PermissionError:
            # Error already logged in scanner
            self._running = False
        except OSError as e:
            logger.error(f"Scanner error: {e}")
            self._running = False
        finally:
            self._loop.close()
    
    def _handle_shutdown(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received...")
        self.stop()
    
    def start(self) -> None:
        """Start the ETHER-SIGHT application."""
        self._running = True
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        print()
        print("=" * 60)
        print("  ETHER-SIGHT: Real-Time BLE Radar Scanner")
        print("=" * 60)
        print()
        
        if self.demo_mode:
            self._run_demo_mode()
        else:
            self._run_live_mode()
    
    def _run_demo_mode(self) -> None:
        """Run in demo mode with simulated devices."""
        import random
        from scanner import rssi_to_distance, mac_to_stable_angle
        
        print("  Running in DEMO MODE (simulated devices)")
        print("  Close the window or press Ctrl+C to exit")
        print()
        
        # Initialize demo devices
        demo_macs = [
            ("AA:BB:CC:DD:EE:01", "User's iPhone", -45),
            ("AA:BB:CC:DD:EE:02", None, -65),
            ("AA:BB:CC:DD:EE:03", "Smart Watch", -55),
            ("AA:BB:CC:DD:EE:04", "Laptop", -50),
            ("AA:BB:CC:DD:EE:05", None, -75),
        ]
        
        for mac, name, rssi in demo_macs:
            self.devices[mac] = BLEDevice(
                mac_address=mac,
                name=name,
                rssi=rssi,
                distance=rssi_to_distance(rssi),
                angle=mac_to_stable_angle(mac),
                last_seen=time.time()
            )
        
        def update_demo() -> Dict[str, BLEDevice]:
            """Update demo devices with simulated changes."""
            for mac, device in list(self.devices.items()):
                # Simulate RSSI fluctuations
                device.rssi += random.randint(-3, 3)
                device.rssi = max(-100, min(-20, device.rssi))
                device.distance = rssi_to_distance(device.rssi)
                device.last_seen = time.time()
            
            # Occasionally add new devices
            if random.random() < 0.02 and len(self.devices) < 10:
                new_num = random.randint(10, 99)
                new_mac = f"AA:BB:CC:DD:EE:{new_num:02d}"
                if new_mac not in self.devices:
                    names = [None, None, None, "Headphones", "Fitness Band", "Smart TV"]
                    self.devices[new_mac] = BLEDevice(
                        mac_address=new_mac,
                        name=random.choice(names),
                        rssi=random.randint(-80, -40),
                        distance=rssi_to_distance(random.randint(-80, -40)),
                        angle=mac_to_stable_angle(new_mac),
                        last_seen=time.time()
                    )
            
            return self.devices.copy()
        
        # Create and show radar
        self._radar = RadarDisplay(title="ETHER-SIGHT BLE Radar (Demo Mode)")
        self._radar.update_devices(self.devices)
        self._radar.start_animation(update_callback=update_demo)
        
        try:
            self._radar.show()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def _run_live_mode(self) -> None:
        """Run in live mode with actual BLE scanning."""
        print("  Starting BLE Scanner...")
        print("  Scanning for nearby devices...")
        print("  Close the window or press Ctrl+C to exit")
        print()
        
        # Start scanner in background thread
        self._scan_thread = threading.Thread(
            target=self._run_scanner_loop,
            daemon=True
        )
        self._scan_thread.start()
        
        # Give scanner time to initialize
        time.sleep(1)
        
        if not self._running:
            # Scanner failed to start
            print("\nError: BLE Scanner failed to start.")
            print("Please check the error messages above.")
            return
        
        # Create and show radar
        self._radar = RadarDisplay(title="ETHER-SIGHT BLE Radar (Live)")
        self._radar.start_animation(update_callback=self._get_devices)
        
        try:
            self._radar.show()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the application gracefully."""
        self._running = False
        
        # Stop scanner
        if self._scanner and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._scanner.stop_scanning(),
                    self._loop
                )
            except Exception:
                pass
        
        # Close radar
        if self._radar:
            try:
                self._radar.close()
            except Exception:
                pass
        
        # Wait for scan thread
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=2)
        
        logger.info("ETHER-SIGHT stopped")


def check_permissions() -> bool:
    """
    Check if the application has necessary permissions.
    
    Returns:
        True if permissions appear to be sufficient
    """
    if sys.platform.startswith('linux'):
        import os
        if os.geteuid() != 0:
            print()
            print("WARNING: Running without root privileges.")
            print("If scanning fails, try running with sudo:")
            print("  sudo python main.py")
            print()
            return True  # Allow attempt anyway
    return True


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="ETHER-SIGHT: Real-Time BLE Radar Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py           # Run with live BLE scanning
  python main.py --demo    # Run with simulated devices
  sudo python main.py      # Run with elevated permissions (Linux)

Legend:
  Red Triangle  = Named device (e.g., "Anamitra's iPhone")
  Green Dot     = Unknown device (MAC address only)
  
The radar displays devices based on their signal strength (RSSI).
Devices fade out after 5 seconds of no signal.
        """
    )
    
    parser.add_argument(
        '--demo',
        action='store_true',
        help='Run in demo mode with simulated devices'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point.
    
    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    args = parse_arguments()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check dependencies
    try:
        import matplotlib
        import numpy
        from bleak import BleakScanner
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("\nPlease install required packages:")
        print("  pip install -r requirements.txt")
        return 1
    
    # Check permissions (Linux only)
    if not args.demo:
        check_permissions()
    
    # Run application
    try:
        app = EtherSight(demo_mode=args.demo)
        app.start()
        return 0
    except PermissionError:
        print("\n" + "=" * 60)
        print("ERROR: Permission denied for Bluetooth access!")
        print("=" * 60)
        if sys.platform.startswith('linux'):
            print("\nOn Linux, try one of the following:")
            print("  1. Run with sudo: sudo python main.py")
            print("  2. Add user to bluetooth group:")
            print("     sudo usermod -a -G bluetooth $USER")
            print("     (then log out and back in)")
        elif sys.platform == 'win32':
            print("\nOn Windows:")
            print("  1. Enable Bluetooth in Settings")
            print("  2. Grant Bluetooth permissions to Python")
        print()
        return 2
    except OSError as e:
        print(f"\nError: {e}")
        if "bluetooth" in str(e).lower():
            print("\nPlease ensure Bluetooth is enabled on your system.")
        return 3
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 0
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 4


if __name__ == "__main__":
    sys.exit(main())
