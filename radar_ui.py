"""
ETHER-SIGHT Radar UI Module

This module provides the matplotlib-based polar radar visualization
for BLE device tracking with dark mode styling and fade effects.
"""

import math
import time
from typing import Dict, List, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from scanner import BLEDevice, DEVICE_TIMEOUT, MAX_DISTANCE

# Use TkAgg backend for interactive display (falls back if not available)
try:
    matplotlib.use('TkAgg')
except Exception:
    pass

# Color scheme
BACKGROUND_COLOR = '#000000'  # Black background
GRID_COLOR = '#00FF00'        # Green grid
NAMED_DEVICE_COLOR = '#FF0000'  # Red for named devices
UNKNOWN_DEVICE_COLOR = '#00FF00'  # Green for unknown devices
TEXT_COLOR = '#00FF00'        # Green text
SWEEP_COLOR = '#003300'       # Dark green for radar sweep

# Visual settings
RADAR_RINGS = 5  # Number of distance rings
ANIMATION_INTERVAL = 100  # Milliseconds between frames
MARKER_SIZE_NAMED = 150  # Size for named device markers
MARKER_SIZE_UNKNOWN = 100  # Size for unknown device markers


class RadarDisplay:
    """
    Matplotlib-based polar radar display for BLE devices.
    """
    
    def __init__(
        self,
        title: str = "ETHER-SIGHT BLE Radar",
        max_distance: float = MAX_DISTANCE,
        figsize: Tuple[int, int] = (10, 10)
    ) -> None:
        """
        Initialize the radar display.
        
        Args:
            title: Window title
            max_distance: Maximum radar range in meters
            figsize: Figure size in inches (width, height)
        """
        self.title = title
        self.max_distance = max_distance
        self.figsize = figsize
        
        self.fig: Optional[Figure] = None
        self.ax: Optional[Axes] = None
        self.animation: Optional[FuncAnimation] = None
        
        self.devices: Dict[str, BLEDevice] = {}
        self._device_plots: Dict[str, object] = {}
        self._device_labels: Dict[str, object] = {}
        self._sweep_line: Optional[object] = None
        self._sweep_angle: float = 0.0
        
        self._setup_plot()
    
    def _setup_plot(self) -> None:
        """Configure the matplotlib figure and axes for radar display."""
        # Create figure with dark background
        self.fig = plt.figure(figsize=self.figsize, facecolor=BACKGROUND_COLOR)
        self.fig.canvas.manager.set_window_title(self.title)
        
        # Create polar subplot
        self.ax = self.fig.add_subplot(111, projection='polar', facecolor=BACKGROUND_COLOR)
        
        # Configure polar plot
        self.ax.set_theta_zero_location('N')  # 0 degrees at top
        self.ax.set_theta_direction(-1)  # Clockwise
        
        # Set radial limits (distance)
        self.ax.set_rlim(0, self.max_distance)
        
        # Configure grid
        self.ax.grid(True, color=GRID_COLOR, linestyle='-', linewidth=0.5, alpha=0.5)
        
        # Set radial ticks (distance rings)
        ring_distances = np.linspace(0, self.max_distance, RADAR_RINGS + 1)[1:]
        self.ax.set_rticks(ring_distances)
        self.ax.set_yticklabels(
            [f'{d:.0f}m' for d in ring_distances],
            color=TEXT_COLOR,
            fontsize=8
        )
        
        # Configure angular ticks
        angles = np.linspace(0, 360, 13)[:-1]  # 0, 30, 60, ... 330
        self.ax.set_thetagrids(
            angles,
            labels=[f'{int(a)}°' for a in angles],
            color=TEXT_COLOR,
            fontsize=8
        )
        
        # Style the spines
        self.ax.spines['polar'].set_color(GRID_COLOR)
        self.ax.spines['polar'].set_linewidth(1)
        
        # Add title
        self.ax.set_title(
            self.title,
            color=TEXT_COLOR,
            fontsize=14,
            fontweight='bold',
            pad=20
        )
        
        # Add legend
        self._add_legend()
        
        # Initialize sweep line
        self._sweep_line, = self.ax.plot(
            [0, 0], [0, self.max_distance],
            color=SWEEP_COLOR,
            linewidth=2,
            alpha=0.7
        )
        
        plt.tight_layout()
    
    def _add_legend(self) -> None:
        """Add a legend explaining the device markers."""
        from matplotlib.lines import Line2D
        
        legend_elements = [
            Line2D(
                [0], [0],
                marker='^',
                color='w',
                markerfacecolor=NAMED_DEVICE_COLOR,
                markersize=12,
                linestyle='None',
                label='Named Device'
            ),
            Line2D(
                [0], [0],
                marker='o',
                color='w',
                markerfacecolor=UNKNOWN_DEVICE_COLOR,
                markersize=10,
                linestyle='None',
                label='Unknown Device'
            ),
        ]
        
        legend = self.ax.legend(
            handles=legend_elements,
            loc='upper right',
            bbox_to_anchor=(1.15, 1.0),
            facecolor=BACKGROUND_COLOR,
            edgecolor=GRID_COLOR,
            labelcolor=TEXT_COLOR,
            fontsize=9
        )
        legend.get_frame().set_alpha(0.8)
    
    def update_devices(self, devices: Dict[str, BLEDevice]) -> None:
        """
        Update the device list for display.
        
        Args:
            devices: Dictionary of MAC address to BLEDevice
        """
        self.devices = devices.copy()
    
    def _calculate_opacity(self, device: BLEDevice) -> float:
        """
        Calculate device opacity based on time since last seen.
        
        Args:
            device: BLE device
        
        Returns:
            Opacity value between 0.0 and 1.0
        """
        elapsed = time.time() - device.last_seen
        if elapsed <= 0:
            return 1.0
        if elapsed >= DEVICE_TIMEOUT:
            return 0.0
        return 1.0 - (elapsed / DEVICE_TIMEOUT)
    
    def _update_frame(self, frame: int) -> List:
        """
        Animation frame update function.
        
        Args:
            frame: Current frame number
        
        Returns:
            List of artists that were modified
        """
        artists = []
        
        # Update sweep line
        self._sweep_angle += 0.1  # Rotate sweep
        if self._sweep_angle >= 2 * math.pi:
            self._sweep_angle = 0
        
        self._sweep_line.set_data(
            [self._sweep_angle, self._sweep_angle],
            [0, self.max_distance]
        )
        artists.append(self._sweep_line)
        
        # Track which devices to remove
        current_macs = set(self.devices.keys())
        displayed_macs = set(self._device_plots.keys())
        
        # Remove devices no longer present
        for mac in displayed_macs - current_macs:
            if mac in self._device_plots:
                self._device_plots[mac].remove()
                del self._device_plots[mac]
            if mac in self._device_labels:
                self._device_labels[mac].remove()
                del self._device_labels[mac]
        
        # Update or add devices
        for mac, device in self.devices.items():
            opacity = self._calculate_opacity(device)
            
            if opacity <= 0:
                # Device has faded out completely
                if mac in self._device_plots:
                    self._device_plots[mac].remove()
                    del self._device_plots[mac]
                if mac in self._device_labels:
                    self._device_labels[mac].remove()
                    del self._device_labels[mac]
                continue
            
            # Determine marker style
            if device.is_named:
                marker = '^'  # Triangle for named devices
                color = NAMED_DEVICE_COLOR
                size = MARKER_SIZE_NAMED
            else:
                marker = 'o'  # Circle for unknown devices
                color = UNKNOWN_DEVICE_COLOR
                size = MARKER_SIZE_UNKNOWN
            
            # Update or create device plot
            if mac in self._device_plots:
                # Update existing
                self._device_plots[mac].set_data([device.angle], [device.distance])
                self._device_plots[mac].set_alpha(opacity)
                artists.append(self._device_plots[mac])
            else:
                # Create new
                plot, = self.ax.plot(
                    device.angle,
                    device.distance,
                    marker=marker,
                    color=color,
                    markersize=math.sqrt(size),
                    alpha=opacity,
                    linestyle='None'
                )
                self._device_plots[mac] = plot
                artists.append(plot)
            
            # Update or create label
            label_text = device.name[:15] if device.name else mac[-8:]
            label_offset = device.distance + (self.max_distance * 0.05)
            
            if mac in self._device_labels:
                # Update existing label
                self._device_labels[mac].set_position((device.angle, label_offset))
                self._device_labels[mac].set_text(label_text)
                self._device_labels[mac].set_alpha(opacity)
            else:
                # Create new label
                label = self.ax.text(
                    device.angle,
                    label_offset,
                    label_text,
                    color=TEXT_COLOR,
                    fontsize=7,
                    alpha=opacity,
                    ha='center',
                    va='bottom'
                )
                self._device_labels[mac] = label
        
        return artists
    
    def start_animation(self, update_callback=None) -> None:
        """
        Start the radar animation.
        
        Args:
            update_callback: Optional callback to get updated device data
        """
        def animation_frame(frame: int) -> List:
            if update_callback:
                devices = update_callback()
                if devices is not None:
                    self.update_devices(devices)
            return self._update_frame(frame)
        
        self.animation = FuncAnimation(
            self.fig,
            animation_frame,
            interval=ANIMATION_INTERVAL,
            blit=False,
            cache_frame_data=False
        )
    
    def show(self) -> None:
        """Display the radar window (blocking)."""
        plt.show()
    
    def close(self) -> None:
        """Close the radar display."""
        if self.animation:
            self.animation.event_source.stop()
        plt.close(self.fig)


def demo_radar() -> None:
    """Demo function showing radar with simulated devices."""
    import random
    
    # Create simulated devices
    demo_devices: Dict[str, BLEDevice] = {}
    
    def create_demo_device(mac: str, name: Optional[str], rssi: int) -> BLEDevice:
        from scanner import rssi_to_distance, mac_to_stable_angle
        return BLEDevice(
            mac_address=mac,
            name=name,
            rssi=rssi,
            distance=rssi_to_distance(rssi),
            angle=mac_to_stable_angle(mac),
            last_seen=time.time()
        )
    
    # Initial demo devices
    demo_devices["AA:BB:CC:DD:EE:01"] = create_demo_device(
        "AA:BB:CC:DD:EE:01", "User's iPhone", -45
    )
    demo_devices["AA:BB:CC:DD:EE:02"] = create_demo_device(
        "AA:BB:CC:DD:EE:02", None, -65
    )
    demo_devices["AA:BB:CC:DD:EE:03"] = create_demo_device(
        "AA:BB:CC:DD:EE:03", "Smart Watch", -55
    )
    
    def update_demo_devices() -> Dict[str, BLEDevice]:
        # Simulate RSSI fluctuations
        for mac, device in demo_devices.items():
            device.rssi += random.randint(-5, 5)
            device.rssi = max(-100, min(-20, device.rssi))
            from scanner import rssi_to_distance
            device.distance = rssi_to_distance(device.rssi)
            device.last_seen = time.time()
        
        # Occasionally add/remove devices
        if random.random() < 0.05:
            new_mac = f"AA:BB:CC:DD:EE:{random.randint(10, 99):02d}"
            if new_mac not in demo_devices:
                demo_devices[new_mac] = create_demo_device(
                    new_mac,
                    random.choice([None, None, None, "New Device"]),
                    random.randint(-80, -40)
                )
        
        return demo_devices.copy()
    
    radar = RadarDisplay(title="ETHER-SIGHT Demo Mode")
    radar.update_devices(demo_devices)
    radar.start_animation(update_callback=update_demo_devices)
    
    print("ETHER-SIGHT Radar - Demo Mode")
    print("=" * 40)
    print("Showing simulated BLE devices")
    print("Close the window to exit")
    
    radar.show()


if __name__ == "__main__":
    demo_radar()
