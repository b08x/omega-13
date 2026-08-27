import sys
from typing import Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt

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
        
        # Auto-record
        table.add_row("Auto-Record", "Enabled", str(c.get_auto_record_enabled()))
        table.add_row("Auto-Record", "Begin Threshold", f"{c.get_auto_record_begin_threshold()} dB")
        
        # Transcription
        table.add_row("Transcription", "Auto-Transcribe", str(c.get_auto_transcribe()))
        table.add_row("Transcription", "Provider", c.get_transcription_provider())
        
        # Output Destinations
        table.add_row("Outputs", "Copy to Clipboard", str(c.get_copy_to_clipboard()))
        table.add_row("Outputs", "Inject to Window", str(c.get_inject_to_active_window()))
        table.add_row("Outputs", "Obsidian Daily Note", str(c.get_write_to_daily_note()))
        
        console.print(table)
        console.print()
        
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
        
        obs = Confirm.ask("Append transcription to Obsidian Daily Note?", default=c.get_write_to_daily_note())
        c.set_write_to_daily_note(obs)
        
        console.print("[green]Output settings updated![/green]\n")
        
    def run(self):
        console.clear()
        console.print(Panel.fit("[bold magenta]Omega-13 Configuration Wizard[/bold magenta]"))
        
        while True:
            self.display_current_config()
            
            console.print("What would you like to configure?")
            console.print("1. Transcription Settings")
            console.print("2. Output Destinations")
            console.print("3. Exit")
            
            choice = Prompt.ask("Select an option", choices=["1", "2", "3"])
            
            if choice == "1":
                self.configure_transcription()
            elif choice == "2":
                self.configure_outputs()
            elif choice == "3":
                console.print("[bold green]Configuration saved! Restart the omega13 daemon to apply changes.[/bold green]")
                break

def run_config_ui():
    config_manager = ConfigManager()
    wizard = ConfigWizard(config_manager)
    wizard.run()

if __name__ == "__main__":
    run_config_ui()
