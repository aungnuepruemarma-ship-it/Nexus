import subprocess
import json

class Metabolism:
    def get_energy_state(self):
        """Fetches real-world energy state from the device."""
        try:
            result = subprocess.run(["termux-battery-status"], capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            battery_level = data.get("percentage", 50)
            is_charging = data.get("status") == "charging"
            
            # Logic: Energy is 10 if charging, otherwise battery % / 10
            energy = 10 if is_charging else battery_level // 10
            return {
                "energy": max(1, energy),
                "is_charging": is_charging,
                "battery_level": battery_level
            }
        except:
            # Fallback to simulated metabolism
            return {"energy": 10, "is_charging": True, "battery_level": 100}

    def get_thermal_state(self):
        """Monitors CPU temperature if available."""
        try:
            # This is device-specific, typical path:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read().strip()) / 1000
                return temp
        except:
            return 35.0 # Baseline comfortable temperature
