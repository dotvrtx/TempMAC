#!/usr/bin/env python3
"""
Privacy & Security Toolkit: MAC Spoofing + Tor Bridge Injection + IP Leak Killswitch

A comprehensive cross-platform tool for:
- MAC address spoofing (Linux, Windows, macOS)
- Tor stealth bridge injection with automatic restart
- Real-time IP leak detection and emergency shutdown

Requires: root/Administrator privileges
"""

import random
import os
import platform
import subprocess
import time
import requests
import ctypes
import sys
import json
import argparse
import shutil
import signal
import logging
import atexit
from pathlib import Path
from datetime import datetime


# ============================================================================
# CONSTANTS
# ============================================================================

REQUEST_TIMEOUT = 10
RETRIES = 3
CONFIG_DIR = Path.home() / '.privacy_toolkit'
MAC_BACKUP_FILE = CONFIG_DIR / 'mac_backup.json'
LOG_FILE = CONFIG_DIR / 'privacy_toolkit.log'

CONFIG_DIR.mkdir(exist_ok=True)
LOG_FILE.touch(exist_ok=True)

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# GLOBALS FOR GRACEFUL SHUTDOWN
# ============================================================================

_mac_manager = None
_killswitch_active = False
_modified_interface = None
_modified_system = None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_system():
    """Get system type: 'Windows', 'Linux', or 'Darwin' (macOS).
    
    Returns:
        str: System type
    """
    return platform.system()


def is_admin():
    """Check if running with admin/root privileges.
    
    Returns:
        bool: True if admin/root
    """
    system = get_system()
    if system == 'Windows':
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    elif system == 'Linux':
        return os.geteuid() == 0
    elif system == 'Darwin':
        return os.geteuid() == 0
    return False


def get_sudo_prefix():
    """Get sudo prefix based on privilege status.
    
    Returns:
        list: [] if root, ['sudo'] if not
    """
    return [] if is_admin() else ['sudo']


def handle_shutdown(signum, frame):
    """Handle graceful shutdown on Ctrl+C."""
    logger.info("\n[*] Shutting down gracefully...")
    
    if _mac_manager and _modified_interface and _modified_system:
        logger.info("[*] Attempting to restore original MAC...")
        _mac_manager.restore_mac(_modified_interface, _modified_system)
    
    sys.exit(0)


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, handle_shutdown)


# ============================================================================
# MAC MANAGEMENT CLASS
# ============================================================================

class MACManager:
    """Manages MAC address backup and restoration."""
    
    def __init__(self, backup_file=MAC_BACKUP_FILE):
        """Initialize MAC Manager.
        
        Args:
            backup_file: Path to MAC backup JSON file
        """
        self.backup_file = backup_file
        self.backup_data = self._load_backup()
    
    def _load_backup(self):
        """Load MAC backup from file."""
        if self.backup_file.exists():
            try:
                with open(self.backup_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load MAC backup: {e}")
        return {}
    
    def _save_backup(self):
        """Save MAC backup to file."""
        try:
            with open(self.backup_file, 'w') as f:
                json.dump(self.backup_data, f, indent=2)
            logger.info(f"[*] MAC backup saved to {self.backup_file}")
        except Exception as e:
            logger.error(f"[-] Failed to save MAC backup: {e}")
    
    def get_current_mac(self, interface, system):
        """Get current MAC address of interface.
        
        Args:
            interface: Interface name
            system: System type
            
        Returns:
            str: MAC address or None
        """
        try:
            if system == 'Linux':
                result = subprocess.run(['ip', 'link', 'show', interface],
                                      capture_output=True, text=True, timeout=5)
                for line in result.stdout.split('\n'):
                    if 'link/ether' in line:
                        return line.split('link/ether')[1].split()[0]
            
            elif system == 'Windows':
                result = subprocess.run(['getmac'],
                                      capture_output=True, text=True, timeout=5)
                if result.stdout:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 0:
                        return lines[0].split()[-1]
            
            elif system == 'Darwin':
                result = subprocess.run(['ifconfig', interface],
                                      capture_output=True, text=True, timeout=5)
                for line in result.stdout.split('\n'):
                    if 'ether' in line:
                        return line.split('ether')[1].strip().split()[0]
        except Exception as e:
            logger.warning(f"Failed to get current MAC: {e}")
        
        return None
    
    def backup_mac(self, interface, system):
        """Back up current MAC address.
        
        Args:
            interface: Interface name
            system: System type
            
        Returns:
            str: Original MAC address
        """
        current_mac = self.get_current_mac(interface, system)
        if current_mac:
            self.backup_data[interface] = {
                'original_mac': current_mac,
                'timestamp': datetime.now().isoformat(),
                'system': system
            }
            self._save_backup()
            logger.info(f"[*] MAC backed up for {interface}: {current_mac}")
            return current_mac
        return None
    
    def restore_mac(self, interface, system):
        """Restore original MAC address.
        
        Args:
            interface: Interface name
            system: System type
            
        Returns:
            bool: Success status
        """
        if interface not in self.backup_data:
            logger.warning(f"[-] No backup found for {interface}")
            return False
        
        original_mac = self.backup_data[interface]['original_mac']
        logger.info(f"[*] Restoring {interface} to original MAC: {original_mac}")
        
        try:
            sudo = get_sudo_prefix()
            
            if system == 'Linux':
                subprocess.run(sudo + ['ip', 'link', 'set', 'dev', interface, 'down'],
                              check=True, timeout=10, capture_output=True)
                time.sleep(1)
                subprocess.run(sudo + ['ip', 'link', 'set', 'dev', interface, 'address', original_mac],
                              check=True, timeout=10, capture_output=True)
                time.sleep(1)
                subprocess.run(sudo + ['ip', 'link', 'set', 'dev', interface, 'up'],
                              check=True, timeout=10, capture_output=True)
                logger.info(f"[+] MAC restored: {original_mac}")
                return True
            
            elif system == 'Windows':
                mac_hex = original_mac.replace(':', '')
                script = (
                    f"$adapterName = '{interface}'; "
                    f"$mac = '{mac_hex}'; "
                    f"$adapter = Get-NetAdapter -Name $adapterName -ErrorAction Stop; "
                    f"$guid = $adapter.InterfaceGuid.Guid; "
                    f"$regPath = 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e972-e325-11ce-bfc1-08002be10318}}'; "
                    f"$entry = Get-ChildItem $regPath | Where-Object {{(Get-ItemProperty $_.PSPath -Name NetCfgInstanceId).NetCfgInstanceId -eq $guid}}; "
                    f"Set-ItemProperty -Path $entry.PSPath -Name NetworkAddress -Value $mac; "
                    f"Disable-NetAdapter -Name $adapterName -Confirm:$false -ErrorAction Stop; "
                    f"Start-Sleep -Seconds 2; "
                    f"Enable-NetAdapter -Name $adapterName -Confirm:$false -ErrorAction Stop"
                )
                subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
                              check=True, timeout=30, capture_output=True)
                logger.info(f"[+] MAC restored: {original_mac}")
                return True
            
            elif system == 'Darwin':
                subprocess.run(sudo + ['ifconfig', interface, 'ether', original_mac],
                              check=True, timeout=10, capture_output=True)
                logger.info(f"[+] MAC restored: {original_mac}")
                return True
        
        except Exception as e:
            logger.error(f"[-] Failed to restore MAC: {e}")
            return False


# ============================================================================
# MAC ADDRESS SPOOFING
# ============================================================================

def generate_mac_colon_format():
    """Generate random MAC address in colon format.
    
    Returns:
        str: MAC address (00:16:3e:xx:xx:xx)
    """
    mac = [0x00, 0x16, 0x3e, random.randint(0x00, 0x7f),
           random.randint(0x00, 0xff), random.randint(0x00, 0xff)]
    return ':'.join(f'{byte:02x}' for byte in mac)


def generate_mac_hex_format():
    """Generate random MAC address in hex format.
    
    Returns:
        str: MAC address (00163exxxxxx)
    """
    mac = [0x00, 0x16, 0x3e, random.randint(0x00, 0x7f),
           random.randint(0x00, 0xff), random.randint(0x00, 0xff)]
    return ''.join(f'{byte:02x}' for byte in mac)


def get_network_interfaces():
    """Get available network interfaces for current OS.
    
    Returns:
        list: Interface names
    """
    system = get_system()
    
    try:
        if system == 'Linux':
            result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                interfaces = []
                for line in result.stdout.split('\n'):
                    if ':' in line and not line.startswith(' '):
                        parts = line.split(':')
                        if len(parts) > 1:
                            interface = parts[1].strip()
                            if interface and interface != 'lo':
                                interfaces.append(interface)
                return interfaces if interfaces else ['eth0', 'wlan0']
        
        elif system == 'Windows':
            result = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                                    'Get-NetAdapter | Select-Object -ExpandProperty Name'],
                                   capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                interfaces = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                return interfaces if interfaces else ['Ethernet']
        
        elif system == 'Darwin':
            result = subprocess.run(['ifconfig', '-l'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                interfaces = [iface for iface in result.stdout.split() if iface != 'lo0']
                return interfaces if interfaces else ['en0']
    
    except Exception as e:
        logger.warning(f"Could not enumerate network interfaces: {e}")
    
    return ['eth0', 'wlan0'] if system == 'Linux' else (['Ethernet'] if system == 'Windows' else ['en0'])


def set_mac_linux(interface, mac_manager):
    """Set MAC address on Linux.
    
    Args:
        interface: Interface name
        mac_manager: MACManager instance
        
    Returns:
        bool: Success status
    """
    mac_address = generate_mac_colon_format()
    logger.info(f"[*] Generated MAC Address: {mac_address}")
    
    # Backup original
    mac_manager.backup_mac(interface, 'Linux')
    
    try:
        sudo = get_sudo_prefix()
        
        # Try macchanger first
        if shutil.which('macchanger'):
            logger.info(f"[*] Using macchanger on {interface}...")
            subprocess.run(sudo + ['macchanger', '-m', mac_address, interface],
                          check=True, timeout=10, capture_output=True)
            logger.info(f"[+] MAC changed via macchanger: {mac_address}")
            return True
        
        # Fallback to ip command
        logger.info(f"[*] Using ip command on {interface}...")
        subprocess.run(sudo + ['ip', 'link', 'set', 'dev', interface, 'down'],
                      check=True, timeout=10, capture_output=True)
        time.sleep(1)
        
        subprocess.run(sudo + ['ip', 'link', 'set', 'dev', interface, 'address', mac_address],
                      check=True, timeout=10, capture_output=True)
        time.sleep(1)
        
        subprocess.run(sudo + ['ip', 'link', 'set', 'dev', interface, 'up'],
                      check=True, timeout=10, capture_output=True)
        
        logger.info(f"[+] MAC changed: {mac_address}")
        return True
    
    except subprocess.CalledProcessError as e:
        logger.error(f"[-] Command failed: {e}")
        return False
    except Exception as e:
        logger.error(f"[-] Unexpected error: {e}")
        return False


def set_mac_windows(adapter_name, mac_manager):
    """Set MAC address on Windows.
    
    Args:
        adapter_name: Adapter name
        mac_manager: MACManager instance
        
    Returns:
        bool: Success status
    """
    mac_address_hex = generate_mac_hex_format()
    logger.info(f"[*] Generated MAC Address: {mac_address_hex}")
    
    # Backup original
    mac_manager.backup_mac(adapter_name, 'Windows')
    
    script = (
        f"$ErrorActionPreference = 'Stop'; "
        f"$adapterName = '{adapter_name}'; "
        f"$mac = '{mac_address_hex}'; "
        f"try {{ "
        f"  $adapter = Get-NetAdapter -Name $adapterName -ErrorAction Stop; "
        f"  $guid = $adapter.InterfaceGuid.Guid; "
        f"  $regPath = 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e972-e325-11ce-bfc1-08002be10318}}'; "
        f"  $entry = Get-ChildItem -Path $regPath | Where-Object {{(Get-ItemProperty $_.PSPath -Name NetCfgInstanceId).NetCfgInstanceId -eq $guid}} | Select-Object -First 1; "
        f"  if (-not $entry) {{ throw 'Adapter not found' }}; "
        f"  Set-ItemProperty -Path $entry.PSPath -Name NetworkAddress -Value $mac; "
        f"  Disable-NetAdapter -Name $adapterName -Confirm:$false -ErrorAction Stop; "
        f"  Start-Sleep -Seconds 2; "
        f"  Enable-NetAdapter -Name $adapterName -Confirm:$false -ErrorAction Stop; "
        f"  Write-Host 'MAC updated'; "
        f"}} catch {{ Write-Error $_.Exception.Message; exit 1 }}"
    )
    
    try:
        logger.info(f"[*] Updating MAC on {adapter_name}...")
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
                               capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"[-] Command failed: {result.stderr}")
            return False
        
        logger.info(f"[+] MAC changed: {mac_address_hex}")
        return True
    
    except Exception as e:
        logger.error(f"[-] Error: {e}")
        return False


def set_mac_macos(interface, mac_manager):
    """Set MAC address on macOS.
    
    Args:
        interface: Interface name
        mac_manager: MACManager instance
        
    Returns:
        bool: Success status
    """
    mac_address = generate_mac_colon_format()
    logger.info(f"[*] Generated MAC Address: {mac_address}")
    
    # Backup original
    mac_manager.backup_mac(interface, 'Darwin')
    
    try:
        sudo = get_sudo_prefix()
        
        logger.info(f"[*] Setting MAC on {interface}...")
        subprocess.run(sudo + ['ifconfig', interface, 'ether', mac_address],
                      check=True, timeout=10, capture_output=True)
        logger.info(f"[+] MAC changed: {mac_address}")
        return True
    
    except Exception as e:
        logger.error(f"[-] Error: {e}")
        return False


def set_mac(interface=None, mac_manager=None):
    """Set MAC address (auto-detect OS).
    
    Args:
        interface: Interface name (auto-detect if None)
        mac_manager: MACManager instance
        
    Returns:
        bool: Success status
    """
    global _modified_interface, _modified_system
    
    if not is_admin():
        logger.error("[-] Requires administrator/root privileges")
        return False
    
    if not mac_manager:
        mac_manager = MACManager()
    
    system = get_system()
    
    if interface is None:
        interfaces = get_network_interfaces()
        interface = interfaces[0] if interfaces else None
    
    if not interface:
        logger.error("[-] No network interface found")
        return False
    
    _modified_interface = interface
    _modified_system = system
    
    if system == 'Linux':
        return set_mac_linux(interface, mac_manager)
    elif system == 'Windows':
        return set_mac_windows(interface, mac_manager)
    elif system == 'Darwin':
        return set_mac_macos(interface, mac_manager)
    else:
        logger.error(f"[-] Unsupported platform: {system}")
        return False


# ============================================================================
# TOR MANAGEMENT
# ============================================================================

def find_torrc_path():
    """Find Tor configuration file path for current OS.
    
    Returns:
        Path: Path to torrc file
    """
    system = get_system()
    
    if system == 'Windows':
        paths = [
            Path.home() / 'AppData' / 'Local' / 'Tor' / 'torrc',
            Path.home() / 'AppData' / 'Roaming' / 'Tor' / 'torrc',
            Path('C:\\Tor\\torrc'),
        ]
    elif system == 'Darwin':
        paths = [
            Path.home() / '.tor' / 'torrc',
            Path('/usr/local/etc/tor/torrc'),
        ]
    else:  # Linux
        paths = [
            Path('/etc/tor/torrc'),
            Path.home() / '.tor' / 'torrc',
            Path('/var/lib/tor/torrc'),
        ]
    
    for path in paths:
        if path.exists():
            return path
    
    return paths[0] if paths else Path('/etc/tor/torrc')


def validate_bridge(bridge_line):
    """Validate bridge configuration line.
    
    Args:
        bridge_line: Bridge configuration line
        
    Returns:
        bool: True if valid
    """
    bridge_line = bridge_line.strip()
    if not bridge_line or bridge_line.startswith('#'):
        return False
    
    valid_prefixes = ('Bridge obfs4', 'Bridge meek', 'Bridge snowflake')
    return any(bridge_line.startswith(prefix) for prefix in valid_prefixes)


def inject(bridge_list, backup_torrc=True):
    """Inject Tor stealth bridges with backup.
    
    Args:
        bridge_list: List of bridge lines
        backup_torrc: Whether to backup torrc
        
    Returns:
        bool: Success status
    """
    if not bridge_list:
        logger.error("[-] No bridges provided")
        return False
    
    # Validate bridges
    invalid_bridges = [b for b in bridge_list if not validate_bridge(b)]
    if invalid_bridges:
        logger.warning(f"[!] {len(invalid_bridges)} invalid bridge(s) skipped")
        bridge_list = [b for b in bridge_list if validate_bridge(b)]
    
    if not bridge_list:
        logger.error("[-] No valid bridges after validation")
        return False
    
    torrc_path = find_torrc_path()
    logger.info(f"[*] Using Tor config: {torrc_path}")
    
    system = get_system()
    if system == 'Linux':
        obfs4_path = '/usr/bin/obfs4proxy'
    elif system == 'Darwin':
        obfs4_path = '/usr/local/bin/obfs4proxy'
    else:  # Windows
        obfs4_path = 'C:\\Tor\\obfs4proxy.exe'
    
    stealth_settings = [
        "UseBridges 1\n",
        f"ClientTransportPlugin obfs4 exec {obfs4_path}\n"
    ]
    stealth_settings.extend(bridge_list)
    
    try:
        if not torrc_path.exists():
            logger.error(f"[-] Tor config not found: {torrc_path}")
            return False
        
        # Backup
        if backup_torrc:
            backup_path = torrc_path.with_suffix('.bak')
            shutil.copy2(torrc_path, backup_path)
            logger.info(f"[*] Backup created: {backup_path}")
        
        with open(torrc_path, 'r') as f:
            lines = f.readlines()
        
        # Remove old config
        new_lines = [
            line for line in lines
            if not (line.strip().startswith('Bridge ') or 
                   line.strip().startswith('UseBridges ') or
                   line.strip().startswith('ClientTransportPlugin '))
        ]
        
        final_config = new_lines + ["\n# Bridge config - auto-added\n"] + stealth_settings
        
        with open(torrc_path, 'w') as f:
            f.writelines(final_config)
        
        logger.info("[+] Tor bridges injected successfully")
        
        # Restart Tor
        if restart_tor():
            logger.info("[+] Tor restarted successfully")
            time.sleep(5)
            
            # Verify
            tor_info = is_tor_active(retries=3)
            if tor_info and tor_info.get('active'):
                logger.info(f"[+] Tor verified - Exit IP: {tor_info.get('exit_ip')}")
                return True
        
        return True
    
    except Exception as e:
        logger.error(f"[-] Failed: {e}")
        return False


def restart_tor():
    """Restart Tor service.
    
    Returns:
        bool: Success status
    """
    system = get_system()
    sudo = get_sudo_prefix()
    
    commands = []
    
    if system == 'Linux':
        commands = [
            sudo + ['systemctl', 'restart', 'tor'],
            sudo + ['service', 'tor', 'restart'],
            sudo + ['killall', '-HUP', 'tor'],
        ]
    elif system == 'Darwin':
        commands = [
            ['brew', 'services', 'restart', 'tor'],
        ]
    elif system == 'Windows':
        commands = [
            ['net', 'stop', 'Tor'],
            ['net', 'start', 'Tor'],
        ]
    
    for cmd in commands:
        try:
            result = subprocess.run(cmd, timeout=15, capture_output=True)
            if result.returncode == 0:
                logger.info(f"[*] Tor restarted with: {' '.join(cmd)}")
                return True
        except Exception as e:
            logger.debug(f"Command failed: {' '.join(cmd)} - {e}")
    
    logger.warning("[!] All restart methods failed - manual restart may be needed")
    return False


# ============================================================================
# TOR LEAK DETECTION
# ============================================================================

def is_tor_active(retries=RETRIES):
    """Verify that Tor routing is active.
    
    Args:
        retries: Number of retries
        
    Returns:
        dict or None: Tor info or None
    """
    for attempt in range(retries):
        try:
            response = requests.get(
                'https://check.torproject.org/api/ip',
                proxies={'https': 'socks5h://127.0.0.1:9050'},
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            is_tor_flag = data.get('is_tor', False)
            exit_ip = data.get('IP')
            country = data.get('country_code', 'XX')
            
            return {
                'active': is_tor_flag,
                'exit_ip': exit_ip,
                'country': country,
                'is_tor': is_tor_flag
            }
        
        except requests.exceptions.Timeout:
            logger.debug(f"Tor API timeout (attempt {attempt + 1}/{retries})")
        except requests.exceptions.ConnectionError:
            logger.debug(f"Tor SOCKS unreachable (attempt {attempt + 1}/{retries})")
        except Exception as e:
            logger.debug(f"Tor API error: {type(e).__name__}")
        
        if attempt < retries - 1:
            time.sleep(2)
    
    return None


def detect_real_leak():
    """Detect REAL IP leak - traffic NOT routing through Tor.
    
    Returns:
        dict: Leak detection result
    """
    tor_status = is_tor_active(retries=1)
    
    if tor_status is None:
        return {
            'leak': True,
            'reason': 'Tor SOCKS proxy unreachable',
            'severity': 'critical'
        }
    
    if not tor_status.get('active'):
        return {
            'leak': True,
            'reason': f"Traffic NOT through Tor (IP: {tor_status.get('exit_ip')})",
            'severity': 'critical'
        }
    
    return {
        'leak': False,
        'reason': f"Tor secure - Exit: {tor_status.get('exit_ip')}",
        'severity': 'ok'
    }


def internet_reachable():
    """Check if internet connection exists.
    
    Returns:
        bool: True if reachable
    """
    try:
        response = requests.get(
            'https://check.torproject.org/api/ip',
            proxies={'https': 'socks5h://127.0.0.1:9050'},
            timeout=REQUEST_TIMEOUT
        )
        return True
    except Exception:
        return False


def should_shutdown(consecutive_leaks, leak_threshold, last_leak_reason):
    """Determine if emergency shutdown needed.
    
    Args:
        consecutive_leaks: Count of consecutive leaks
        leak_threshold: Threshold for shutdown
        last_leak_reason: Reason for last leak
        
    Returns:
        dict: Shutdown decision
    """
    if 'SOCKS proxy unreachable' in last_leak_reason or \
       'Traffic NOT through Tor' in last_leak_reason:
        
        if consecutive_leaks >= leak_threshold:
            return {
                'shutdown': True,
                'reason': f'{last_leak_reason} ({consecutive_leaks} detections)'
            }
    
    return {'shutdown': False, 'reason': 'Not critical'}


# ============================================================================
# INTERFACE SHUTDOWN
# ============================================================================

def disable_interface_linux(interface):
    """Disable network interface on Linux.
    
    Args:
        interface: Interface name
        
    Returns:
        bool: Success status
    """
    try:
        sudo = get_sudo_prefix()
        logger.info(f"[*] Disabling {interface}...")
        subprocess.run(sudo + ['ip', 'link', 'set', interface, 'down'],
                      check=True, timeout=10, capture_output=True)
        logger.info(f"[+] Interface disabled")
        return True
    except Exception as e:
        logger.error(f"[-] Failed: {e}")
        return False


def disable_interface_windows(adapter_name):
    """Disable network adapter on Windows.
    
    Args:
        adapter_name: Adapter name
        
    Returns:
        bool: Success status
    """
    try:
        logger.info(f"[*] Disabling {adapter_name}...")
        script = f"Disable-NetAdapter -Name '{adapter_name}' -Confirm:$false -ErrorAction Stop"
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
                      check=True, timeout=10, capture_output=True)
        logger.info(f"[+] Adapter disabled")
        return True
    except Exception as e:
        logger.error(f"[-] Failed: {e}")
        return False


def disable_interface_macos(interface):
    """Disable network interface on macOS.
    
    Args:
        interface: Interface name
        
    Returns:
        bool: Success status
    """
    try:
        sudo = get_sudo_prefix()
        logger.info(f"[*] Disabling {interface}...")
        subprocess.run(sudo + ['ifconfig', interface, 'down'],
                      check=True, timeout=10, capture_output=True)
        logger.info(f"[+] Interface disabled")
        return True
    except Exception as e:
        logger.error(f"[-] Failed: {e}")
        return False


def trigger_shutdown(interface, system, mac_manager=None):
    """Trigger emergency shutdown.
    
    Args:
        interface: Interface name
        system: System type
        mac_manager: MACManager instance
    """
    logger.error("[!] ====================================")
    logger.error("[!] IP LEAK DETECTED - EMERGENCY SHUTDOWN")
    logger.error("[!] ====================================")
    
    try:
        if system == 'Linux':
            disable_interface_linux(interface)
        elif system == 'Windows':
            disable_interface_windows(interface)
        elif system == 'Darwin':
            disable_interface_macos(interface)
    except Exception as e:
        logger.error(f"[-] Shutdown failed: {e}")


# ============================================================================
# KILLSWITCH
# ============================================================================

def killswitch(interface=None, check_interval=5, leak_threshold=2, cooldown=30, mac_manager=None):
    """Monitor for IP leaks and disable network if detected.
    
    Args:
        interface: Interface name
        check_interval: Check interval in seconds
        leak_threshold: Leaks before shutdown
        cooldown: Cooldown period in seconds
        mac_manager: MACManager instance
    """
    global _killswitch_active
    
    if not is_admin():
        logger.error("[-] Requires administrator/root privileges")
        return False
    
    system = get_system()
    _killswitch_active = True
    
    if interface is None:
        interfaces = get_network_interfaces()
        interface = interfaces[0] if interfaces else None
    
    if not interface:
        logger.error("[-] No network interface found")
        return False
    
    logger.info("[*] ============================================")
    logger.info("[*] IP Leak Killswitch")
    logger.info("[*] ============================================")
    logger.info(f"[*] System: {system}")
    logger.info(f"[*] Interface: {interface}")
    logger.info(f"[*] Leak Threshold: {leak_threshold}")
    logger.info(f"[*] Check Interval: {check_interval}s")
    logger.info("[*] ============================================")
    logger.info("[*] Verifying Tor connection...")
    
    initial_check = is_tor_active(retries=RETRIES)
    
    if initial_check is None:
        logger.error("[-] Tor SOCKS unreachable at startup")
        return False
    
    if not initial_check.get('active'):
        logger.error("[-] NOT connected through Tor at startup")
        return False
    
    logger.info(f"[+] Tor verified - Exit: {initial_check.get('exit_ip')}")
    logger.info("[*] Monitoring for leaks...\n")
    
    consecutive_leaks = 0
    error_cooldown_timer = 0
    last_leak_reason = ""
    check_count = 0
    start_time = time.time()
    
    try:
        while _killswitch_active:
            check_count += 1
            
            try:
                if error_cooldown_timer > 0:
                    logger.info(f"[!] Cooldown: {error_cooldown_timer}s")
                    error_cooldown_timer -= check_interval
                    time.sleep(check_interval)
                    continue
                
                leak_result = detect_real_leak()
                
                if leak_result['leak']:
                    consecutive_leaks += 1
                    severity = leak_result.get('severity', 'warning')
                    reason = leak_result.get('reason', 'Unknown')
                    last_leak_reason = reason
                    
                    logger.warning(f"[!] LEAK #{consecutive_leaks}/{leak_threshold}")
                    logger.warning(f"    [{severity}] {reason}")
                    
                    shutdown_decision = should_shutdown(consecutive_leaks, leak_threshold, reason)
                    
                    if shutdown_decision['shutdown']:
                        trigger_shutdown(interface, system, mac_manager)
                        return False
                else:
                    if consecutive_leaks > 0:
                        logger.info(f"[+] Leak cleared ({consecutive_leaks} was detections)")
                    
                    consecutive_leaks = 0
                    reason = leak_result.get('reason', 'Secure')
                    uptime = int(time.time() - start_time)
                    logger.info(f"[+] Check #{check_count}: {reason} (uptime: {uptime}s)")
                
                time.sleep(check_interval)
            
            except KeyboardInterrupt:
                logger.info("\n[*] Killswitch stopped by user")
                return True
            
            except requests.exceptions.RequestException as e:
                logger.warning(f"[!] Network error: {type(e).__name__}")
                
                if not internet_reachable():
                    logger.info("[!] Internet unreachable - NOT a leak")
                    error_cooldown_timer = cooldown
                    time.sleep(check_interval)
                    continue
                
                consecutive_leaks += 1
                last_leak_reason = f"Tor check failed ({type(e).__name__})"
                
                if consecutive_leaks >= leak_threshold:
                    logger.error(f"[!] Too many errors - triggering shutdown")
                    trigger_shutdown(interface, system, mac_manager)
                    return False
                
                error_cooldown_timer = cooldown
            
            except Exception as e:
                logger.error(f"[-] Unexpected error: {e}")
                error_cooldown_timer = cooldown
    
    except KeyboardInterrupt:
        logger.info("\n[*] Killswitch stopped")
        return True
    
    except Exception as e:
        logger.error(f"[-] CRITICAL error: {e}")
        trigger_shutdown(interface, system, mac_manager)
        return False
    
    finally:
        _killswitch_active = False


# ============================================================================
# CLI
# ============================================================================

def parse_arguments():
    """Parse command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Privacy Toolkit: MAC Spoofing + Tor Bridge Injection + Leak Killswitch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Examples:
  python privacy_toolkit.py --mac
  python privacy_toolkit.py --killswitch
  python privacy_toolkit.py --bridges bridges.txt --mac
  python privacy_toolkit.py --restore-mac --interface eth0
'''
    )
    
    parser.add_argument('--mac', action='store_true', help='Change MAC address')
    parser.add_argument('--interface', type=str, help='Network interface')
    parser.add_argument('--killswitch', action='store_true', help='Start IP leak killswitch')
    parser.add_argument('--bridges', type=str, help='Bridge file (one per line)')
    parser.add_argument('--restore-mac', action='store_true', help='Restore original MAC')
    parser.add_argument('--backup-torrc', action='store_true', default=True, help='Backup torrc')
    parser.add_argument('--check-interval', type=int, default=5, help='Killswitch interval (s)')
    parser.add_argument('--leak-threshold', type=int, default=2, help='Leak threshold')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')
    
    return parser.parse_args()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    setup_signal_handlers()
    
    logger.info(f"[*] Privacy Toolkit Started")
    logger.info(f"[*] System: {get_system()}")
    logger.info(f"[*] Admin: {is_admin()}\n")
    
    args = parse_arguments()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if not (args.mac or args.killswitch or args.bridges or args.restore_mac):
        logger.error("[-] No action specified. Use --help for options")
        sys.exit(1)
    
    mac_manager = MACManager()
    _mac_manager = mac_manager
    
    # Restore MAC
    if args.restore_mac:
        logger.info("[*] ============================================")
        logger.info("[*] MAC Restoration")
        logger.info("[*] ============================================")
        
        interface = args.interface or get_network_interfaces()[0]
        system = get_system()
        
        if mac_manager.restore_mac(interface, system):
            logger.info("[+] MAC restored successfully\n")
        else:
            logger.error("[-] MAC restoration failed\n")
            sys.exit(1)
    
    # MAC spoofing
    if args.mac:
        logger.info("[*] ============================================")
        logger.info("[*] MAC Spoofing")
        logger.info("[*] ============================================")
        
        if set_mac(args.interface, mac_manager):
            logger.info("[+] MAC spoofed successfully\n")
        else:
            logger.error("[-] MAC spoofing failed\n")
            sys.exit(1)
    
    # Tor bridge injection
    if args.bridges:
        logger.info("[*] ============================================")
        logger.info("[*] Tor Bridge Injection")
        logger.info("[*] ============================================")
        
        try:
            with open(args.bridges, 'r') as f:
                bridges = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            if inject(bridges, backup_torrc=args.backup_torrc):
                logger.info("[+] Bridges injected successfully\n")
            else:
                logger.error("[-] Bridge injection failed\n")
                sys.exit(1)
        except FileNotFoundError:
            logger.error(f"[-] Bridge file not found: {args.bridges}\n")
            sys.exit(1)
    
    # Killswitch
    if args.killswitch:
        logger.info("[*] ============================================")
        logger.info("[*] IP Leak Killswitch")
        logger.info("[*] ============================================\n")
        
        if not killswitch(interface=args.interface, check_interval=args.check_interval,
                         leak_threshold=args.leak_threshold, mac_manager=mac_manager):
            logger.error("[-] Killswitch triggered shutdown")
            sys.exit(1)
    
    logger.info("[+] All operations completed successfully")
    sys.exit(0)
