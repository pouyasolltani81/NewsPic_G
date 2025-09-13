# services/daemon_manager.py
import subprocess
import os
import platform
from typing import List, Dict, Optional

class DaemonManager:
    def __init__(self):
        self.system = platform.system()
        
    def list_services(self) -> List[Dict]:
        """List all daemon services"""
        if self.system == "Darwin":  # macOS
            cmd = ["launchctl", "list"]
        else:  # Linux
            cmd = ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain"]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return self._parse_service_list(result.stdout)
    
    def _parse_service_list(self, output: str) -> List[Dict]:
        """Parse service list output based on system type"""
        services = []
        
        if self.system == "Darwin":  # macOS
            # Parse launchctl list output
            lines = output.strip().split('\n')
            if len(lines) > 0:
                # Skip header line if present
                start_index = 1 if lines[0].startswith('PID') else 0
                
                for line in lines[start_index:]:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        pid = parts[0].strip()
                        status = parts[1].strip()
                        name = parts[2].strip()
                        
                        # Skip system services if needed
                        if name.startswith('com.apple.'):
                            continue
                        
                        services.append({
                            'name': name,
                            'pid': int(pid) if pid != '-' and pid.isdigit() else None,
                            'status': 'running' if pid != '-' and pid.isdigit() else 'stopped',
                            'enabled': True,  # launchctl list only shows loaded services
                            'description': ''
                        })
        else:  # Linux systemd
            # Parse systemctl output
            lines = output.strip().split('\n')
            for line in lines:
                parts = line.split(None, 4)  # Split on whitespace, max 5 parts
                if len(parts) >= 4 and '.service' in parts[0]:
                    name = parts[0].replace('.service', '')
                    loaded = parts[1]
                    active = parts[2]
                    sub = parts[3]
                    
                    # Skip systemd internal services if needed
                    if name.startswith('systemd-'):
                        continue
                    
                    services.append({
                        'name': name,
                        'status': 'running' if active == 'active' else 'stopped',
                        'enabled': loaded == 'loaded',
                        'description': parts[4] if len(parts) > 4 else '',
                        'pid': None  # Would need to query separately
                    })
        
        return services
    
    def get_service_logs(self, service_name: str, lines: int = 50) -> str:
        """Get recent logs for a service"""
        try:
            if self.system == "Darwin":  # macOS
                # Get logs from system log
                cmd = ["log", "show", "--predicate", f'process == "{service_name}"', "--last", f"{lines}m"]
            else:  # Linux
                cmd = ["journalctl", "-u", service_name, "-n", str(lines), "--no-pager"]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout if result.returncode == 0 else "No logs available"
        except Exception as e:
            return f"Error fetching logs: {str(e)}"
    
    def create_service(self, service_name: str, config: Dict) -> bool:
        """Create a new daemon service"""
        if self.system == "Darwin":
            return self._create_launchd_service(service_name, config)
        else:
            return self._create_systemd_service(service_name, config)
    
    def enable_service(self, service_name: str) -> bool:
        """Enable a daemon service"""
        if self.system == "Darwin":
            cmd = ["launchctl", "load", f"/Library/LaunchDaemons/{service_name}.plist"]
        else:
            cmd = ["systemctl", "enable", service_name]
        
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def disable_service(self, service_name: str) -> bool:
        """Disable a daemon service"""
        if self.system == "Darwin":
            cmd = ["launchctl", "unload", f"/Library/LaunchDaemons/{service_name}.plist"]
        else:
            cmd = ["systemctl", "disable", service_name]
        
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def start_service(self, service_name: str) -> bool:
        """Start a daemon service"""
        if self.system == "Darwin":
            cmd = ["launchctl", "start", service_name]
        else:
            cmd = ["systemctl", "start", service_name]
        
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def stop_service(self, service_name: str) -> bool:
        """Stop a daemon service"""
        if self.system == "Darwin":
            cmd = ["launchctl", "stop", service_name]
        else:
            cmd = ["systemctl", "stop", service_name]
        
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def delete_service(self, service_name: str) -> bool:
        """Delete a daemon service"""
        # First stop and disable
        self.stop_service(service_name)
        self.disable_service(service_name)
        
        # Then remove the service file
        if self.system == "Darwin":
            service_file = f"/Library/LaunchDaemons/{service_name}.plist"
        else:
            service_file = f"/etc/systemd/system/{service_name}.service"
        
        try:
            if os.path.exists(service_file):
                os.remove(service_file)
            if self.system == "Linux":
                subprocess.run(["systemctl", "daemon-reload"])
            return True
        except Exception as e:
            print(f"Error deleting service: {e}")
            return False
    
    def _create_launchd_service(self, service_name: str, config: Dict) -> bool:
        """Create a launchd plist file"""
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{service_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{config['command']}</string>
    </array>
    <key>RunAtLoad</key>
    <{'true' if config.get('run_at_load', True) else 'false'}/>
    <key>KeepAlive</key>
    <{'true' if config.get('keep_alive', True) else 'false'}/>
    <key>StandardOutPath</key>
    <string>/var/log/{service_name}.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/{service_name}.error.log</string>
</dict>
</plist>"""
        
        plist_path = f"/Library/LaunchDaemons/{service_name}.plist"
        try:
            with open(plist_path, 'w') as f:
                f.write(plist_content)
            os.chmod(plist_path, 0o644)
            return True
        except Exception as e:
            print(f"Error creating launchd service: {e}")
            return False
    
    def _create_systemd_service(self, service_name: str, config: Dict) -> bool:
        """Create a systemd service file"""
        service_content = f"""[Unit]
Description={config.get('description', service_name)}
After=network.target

[Service]
Type=simple
ExecStart={config['command']}
Restart={'always' if config.get('keep_alive', True) else 'no'}
User={config.get('user', 'root')}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        service_path = f"/etc/systemd/system/{service_name}.service"
        try:
            with open(service_path, 'w') as f:
                f.write(service_content)
            subprocess.run(["systemctl", "daemon-reload"])
            return True
        except Exception as e:
            print(f"Error creating systemd service: {e}")
            return False