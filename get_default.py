import subprocess
import jack

def get_default_pipewire_ports(jack_client):
    try:
        # Get default source name
        res = subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True, check=True)
        default_name = res.stdout.strip()
        
        # Get description for the default source
        res = subprocess.run(["pactl", "list", "sources"], capture_output=True, text=True, check=True)
        desc = None
        in_default = False
        for line in res.stdout.splitlines():
            if line.startswith(f"\tName: {default_name}"):
                in_default = True
            elif in_default and line.startswith("\tDescription: "):
                desc = line.split(": ", 1)[1].strip()
                break
                
        if desc:
            available = jack_client.get_ports(is_output=True, is_audio=True)
            # Find ports where client name matches description
            matches = [p.name for p in available if p.name.startswith(f"{desc}:capture")]
            if matches:
                return matches
    except Exception as e:
        print(e)
    return []

c = jack.Client("test2")
print(get_default_pipewire_ports(c))
