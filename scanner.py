"""
ETHER-SIGHT BLE Scanner Module

This module handles Bluetooth Low Energy scanning using the bleak library.
It converts RSSI values to estimated distances and manages device tracking.
"""

import asyncio
import hashlib
import math
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants for RSSI to distance conversion
TX_POWER: int = -59  # Reference RSSI at 1 meter (typical BLE)
PATH_LOSS_EXPONENT: float = 2.0  # N value for free space

# Maximum distance to display (meters)
MAX_DISTANCE: float = 50.0

# Device timeout in seconds (for fade effect)
DEVICE_TIMEOUT: float = 5.0


@dataclass
class BLEDevice:
    """Represents a detected BLE device with its properties."""
    
    mac_address: str
    name: Optional[str]
    rssi: int
    distance: float
    angle: float  # Simulated angle (radians)
    last_seen: float
    is_named: bool = field(default=False)
    
    def __post_init__(self) -> None:
        """Initialize is_named based on device name."""
        self.is_named = bool(self.name and self.name.strip())


def rssi_to_distance(rssi: int, tx_power: int = TX_POWER, n: float = PATH_LOSS_EXPONENT) -> float:
    """
    Convert RSSI value to estimated distance in meters.
    
    Uses the log-distance path loss model:
    Distance = 10 ^ ((TxPower - RSSI) / (10 * N))
    
    Args:
        rssi: Received Signal Strength Indicator (dBm)
        tx_power: Reference RSSI at 1 meter (dBm)
        n: Path loss exponent (2 for free space)
    
    Returns:
        Estimated distance in meters (clamped between MIN_DISTANCE and MAX_DISTANCE)
    """
    # Minimum distance to prevent devices from being at center
    MIN_DISTANCE = 0.1
    
    try:
        exponent = (tx_power - rssi) / (10 * n)
        distance = 10 ** exponent
        # Clamp between minimum and maximum distances
        return max(MIN_DISTANCE, min(distance, MAX_DISTANCE))
    except (ValueError, OverflowError):
        return MAX_DISTANCE


def mac_to_stable_angle(mac_address: str) -> float:
    """
    Generate a stable angle (in radians) from a MAC address.
    
    Uses SHA-256 hash to create a deterministic but pseudo-random angle
    for each unique device, ensuring consistent placement on radar.
    
    Args:
        mac_address: Device MAC address string
    
    Returns:
        Angle in radians (0 to 2*pi)
    """
    hash_bytes = hashlib.sha256(mac_address.encode()).digest()
    # Use first 4 bytes to create angle
    hash_int = int.from_bytes(hash_bytes[:4], 'big')
    angle = (hash_int / (2**32)) * 2 * math.pi
    return angle


class BLERadarScanner:
    """
    Async BLE scanner that tracks devices and converts signals to radar coordinates.
    """
    
    def __init__(
        self,
        on_device_update: Optional[Callable[[Dict[str, BLEDevice]], None]] = None,
        scan_interval: float = 0.5
    ) -> None:
        """
        Initialize the BLE Radar Scanner.
        
        Args:
            on_device_update: Callback function called when device list updates
            scan_interval: Time between scan cycles (seconds)
        """
        self.devices: Dict[str, BLEDevice] = {}
        self.on_device_update = on_device_update
        self.scan_interval = scan_interval
        self._running = False
        self._scanner: Optional[BleakScanner] = None
    
    def _detection_callback(
        self,
        device: 'BLEDevice',
        advertisement_data: AdvertisementData
    ) -> None:
        """
        Callback for device detection events.
        
        Args:
            device: Detected BLE device
            advertisement_data: Advertisement data from device
        """
        mac = device.address
        rssi = advertisement_data.rssi if advertisement_data.rssi else -100
        name = advertisement_data.local_name or device.name
        
        distance = rssi_to_distance(rssi)
        angle = mac_to_stable_angle(mac)
        current_time = time.time()
        
        self.devices[mac] = BLEDevice(
            mac_address=mac,
            name=name,
            rssi=rssi,
            distance=distance,
            angle=angle,
            last_seen=current_time
        )
        
        logger.debug(
            f"Device: {name or 'Unknown'} ({mac}) - "
            f"RSSI: {rssi}dBm, Distance: {distance:.2f}m"
        )
    
    def _cleanup_stale_devices(self) -> None:
        """Remove devices that haven't been seen within DEVICE_TIMEOUT."""
        current_time = time.time()
        stale_macs = [
            mac for mac, device in self.devices.items()
            if current_time - device.last_seen > DEVICE_TIMEOUT
        ]
        for mac in stale_macs:
            del self.devices[mac]
            logger.debug(f"Removed stale device: {mac}")
    
    def get_active_devices(self) -> Dict[str, BLEDevice]:
        """
        Get all currently tracked devices with fade information.
        
        Returns:
            Dictionary of MAC address to BLEDevice
        """
        self._cleanup_stale_devices()
        return self.devices.copy()
    
    def get_device_opacity(self, device: BLEDevice) -> float:
        """
        Calculate opacity for fade effect based on time since last seen.
        
        Args:
            device: BLE device to calculate opacity for
        
        Returns:
            Opacity value between 0.0 and 1.0
        """
        elapsed = time.time() - device.last_seen
        if elapsed <= 0:
            return 1.0
        if elapsed >= DEVICE_TIMEOUT:
            return 0.0
        return 1.0 - (elapsed / DEVICE_TIMEOUT)
    
    async def start_scanning(self) -> None:
        """
        Start continuous BLE scanning.
        
        Raises:
            PermissionError: If Bluetooth access is denied
            OSError: If Bluetooth adapter is not available
        """
        self._running = True
        logger.info("Starting BLE Radar Scanner...")
        
        try:
            self._scanner = BleakScanner(
                detection_callback=self._detection_callback
            )
            
            await self._scanner.start()
            logger.info("BLE Scanner started successfully")
            
            while self._running:
                self._cleanup_stale_devices()
                
                if self.on_device_update:
                    self.on_device_update(self.devices.copy())
                
                await asyncio.sleep(self.scan_interval)
                
        except PermissionError as e:
            logger.error("Permission denied for Bluetooth access!")
            if sys.platform.startswith('linux'):
                logger.error(
                    "On Linux, try running with sudo:\n"
                    "  sudo python main.py\n"
                    "Or add your user to the 'bluetooth' group:\n"
                    "  sudo usermod -a -G bluetooth $USER"
                )
            elif sys.platform == 'win32':
                logger.error(
                    "On Windows, ensure Bluetooth is enabled and\n"
                    "the application has Bluetooth permissions in Settings."
                )
            raise
        except OSError as e:
            if "No Bluetooth adapter" in str(e) or "bluetooth" in str(e).lower():
                logger.error(
                    "Bluetooth adapter not found or not available.\n"
                    "Please ensure Bluetooth is enabled on your system."
                )
            raise
        finally:
            if self._scanner:
                try:
                    await self._scanner.stop()
                except Exception:
                    pass
    
    async def stop_scanning(self) -> None:
        """Stop the BLE scanning loop."""
        self._running = False
        if self._scanner:
            try:
                await self._scanner.stop()
            except Exception:
                pass
        logger.info("BLE Scanner stopped")


async def demo_scan(duration: float = 10.0) -> None:
    """
    Demo function to test BLE scanning.
    
    Args:
        duration: How long to scan in seconds
    """
    def print_devices(devices: Dict[str, BLEDevice]) -> None:
        if devices:
            print(f"\n--- {len(devices)} device(s) detected ---")
            for mac, device in devices.items():
                name = device.name or "Unknown"
                print(f"  {name} ({mac}): {device.rssi}dBm, {device.distance:.2f}m")
    
    scanner = BLERadarScanner(on_device_update=print_devices)
    
    try:
        scan_task = asyncio.create_task(scanner.start_scanning())
        await asyncio.sleep(duration)
        await scanner.stop_scanning()
        scan_task.cancel()
        try:
            await scan_task
        except asyncio.CancelledError:
            pass
    except PermissionError:
        print("\nError: Permission denied. Please check the error messages above.")
    except OSError as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    print("ETHER-SIGHT BLE Scanner - Demo Mode")
    print("=" * 40)
    asyncio.run(demo_scan())
