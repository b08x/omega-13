import sys
import subprocess
import jack
from typing import Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from omega13.config import ConfigManager

console = Console()

class ConfigWizard:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        
    def display_current_config(self):
        table = Table(title="Current Configuration", show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan")
        table.add_column("Setting", style="green")
        table.add_column("Value", style="yellow")
        
        c = self.config_manager
        
        # Audio
        ports = c.get_input_ports()
        table.add_row("Audio", "Input Ports", str(ports) if ports else "Default System Capture")
        table.add_row("Audio", "Save Path", str(c.get_save_path()))
        
        # Hotkeys
        table.add_row("Hotkeys", "Global Hotkey", str(c.get_global_hotkey()))
        
        # Auto-record
        table.add_row("Auto-Record", "Enabled", str(c.get_auto_record_enabled()))
        table.add_row("Auto-Record", "Begin Threshold", f"{c.get_auto_record_begin_threshold()} dB")
        
        # Transcription
        table.add_row("Transcription", "Auto-Transcribe", str(c.get_auto_transcribe()))
        table.add_row("Transcription", "Provider", c.get_transcription_provider())
        
        # Output Destinations
        table.add_row("Outputs", "Copy to Clipboard", str(c.get_copy_to_clipboard()))
        table.add_row("Outputs", "Inject to Window", str(c.get_inject_to_active_window()))
        table.add_row("Outputs", "Append to Output File", str(c.get_write_to_file()))
        table.add_row("Outputs", "Output File Directory", str(c.get_output_file_directory()) or "Not set")
        
        console.print(table)
        console.print()
        
    def configure_audio(self):
        console.print(Panel("[bold cyan]Audio Settings[/bold cyan]"))
        c = self.config_manager
        
        # Try to get JACK ports
        try:
            client = jack.Client("Omega13_Wizard")
            available_ports = client.get_ports(is_audio=True, is_output=True)
            port_names = [p.name for p in available_ports]
            client.close()
        except Exception as e:
            console.print(f"[red]Error fetching JACK ports: {e}[/red]")
            port_names = []
            
        if not port_names:
            console.print("[yellow]No input ports found or JACK is not running.[/yellow]")
            return
            
        console.print("Available Input Ports:")
        for i, name in enumerate(port_names):
            console.print(f"{i + 1}. {name}")
            
        console.print("Enter the port numbers to use, separated by commas (e.g. '1, 2').")
        console.print("Leave blank to keep current settings or use defaults.")
        
        choice = Prompt.ask("Select ports")
        if choice.strip():
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
                selected_ports = [port_names[i] for i in indices if 0 <= i < len(port_names)]
                if selected_ports:
                    c.set_input_ports(selected_ports)
                    console.print(f"[green]Input ports updated to: {selected_ports}[/green]\n")
                else:
                    console.print("[red]No valid ports selected.[/red]\n")
            except ValueError:
                console.print("[red]Invalid format. Please enter comma-separated numbers.[/red]\n")

    def configure_hotkeys(self):
        console.print(Panel("[bold cyan]Hotkey Settings[/bold cyan]"))
        c = self.config_manager
        
        console.print("Enter the global hotkey combination (e.g. '<ctrl>+<alt>+space').")
        console.print("Leave blank to keep the current hotkey.")
        current_hotkey = c.get_global_hotkey()
        
        new_hotkey = Prompt.ask(f"Global Hotkey", default=current_hotkey)
        if new_hotkey.strip() and new_hotkey != current_hotkey:
            # We don't have a direct set_global_hotkey method on ConfigManager, we need to modify the config dict directly
            c.config["global_hotkey"] = new_hotkey
            c.save_config(c.config)
            console.print(f"[green]Global hotkey updated to: {new_hotkey}[/green]\n")
        
    def configure_transcription(self):
        console.print(Panel("[bold cyan]Transcription Settings[/bold cyan]"))
        c = self.config_manager
        
        auto = Confirm.ask("Enable Auto-Transcription?", default=c.get_auto_transcribe())
        c.set_auto_transcribe(auto)
        
        if auto:
            provider = Prompt.ask("Provider (local or groq)", choices=["local", "groq"], default=c.get_transcription_provider())
            c.set_transcription_provider(provider)
            
            if provider == "local":
                url = Prompt.ask("Local Server URL", default=c.get_transcription_server_url())
                c.set_transcription_server_url(url)
            elif provider == "groq":
                model = Prompt.ask("Groq Model", default=c.get_groq_model())
                c.set_groq_model(model)
                
        console.print("[green]Transcription settings updated![/green]\n")
        
    def configure_outputs(self):
        console.print(Panel("[bold cyan]Output Destinations[/bold cyan]"))
        c = self.config_manager
        
        clip = Confirm.ask("Copy transcription to Clipboard?", default=c.get_copy_to_clipboard())
        c.set_copy_to_clipboard(clip)
        
        inject = Confirm.ask("Type transcription into active window (requires ydotool)?", default=c.get_inject_to_active_window())
        c.set_inject_to_active_window(inject)
        
        file_out = Confirm.ask("Append transcription to a daily markdown file?", default=c.get_write_to_file())
        c.set_write_to_file(file_out)
        
        if file_out:
            current_dir = c.get_output_file_directory()
            new_dir = Prompt.ask("Output Directory (e.g., ~/Documents/Notes)", default=current_dir)
            c.set_output_file_directory(new_dir)
        
        console.print("[green]Output settings updated![/green]\n")
        
    def reload_daemon(self):
        console.print("[yellow]Reloading Omega-13 daemon...[/yellow]")
        try:
            result = subprocess.run(["systemctl", "--user", "restart", "omega13.service"], capture_output=True, text=True)
            if result.returncode == 0:
                console.print("[bold green]Daemon restarted successfully![/bold green]")
            else:
                console.print(f"[red]Failed to restart daemon. You may need to restart it manually.[/red]")
                if result.stderr:
                    console.print(f"[red]Error: {result.stderr}[/red]")
        except Exception as e:
            console.print(f"[red]Could not restart daemon: {e}[/red]")
            
    def run(self):
        console.clear()
        console.print(Panel.fit("[bold magenta]Omega-13 Configuration Wizard[/bold magenta]"))
        
        while True:
            self.display_current_config()
            
            console.print("What would you like to configure?")
            console.print("1. Audio Settings (Input Ports)")
            console.print("2. Hotkey Settings")
            console.print("3. Transcription Settings")
            console.print("4. Output Destinations")
            console.print("5. Exit & Apply (Restart Daemon)")
            console.print("6. Exit Without Applying")
            
            choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6"])
            
            if choice == "1":
                self.configure_audio()
            elif choice == "2":
                self.configure_hotkeys()
            elif choice == "3":
                self.configure_transcription()
            elif choice == "4":
                self.configure_outputs()
            elif choice == "5":
                console.print("[bold green]Configuration saved![/bold green]")
                self.reload_daemon()
                break
            elif choice == "6":
                console.print("[bold green]Configuration saved (but daemon not restarted).[/bold green]")
                break

def run_config_ui():
    config_manager = ConfigManager()
    wizard = ConfigWizard(config_manager)
    wizard.run()

if __name__ == "__main__":
    run_config_ui()
