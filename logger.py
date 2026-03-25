from rich.console import Console
from rich.panel import Panel
from datetime import datetime

console = Console()

def log_sucesso(mensagem):
    hora = datetime.now().strftime("%H:%M:%S")
    console.print(f"[bold cyan][{hora}][/bold cyan] [bold lime]✅ SUCESSO:[/bold lime] {mensagem}")

def log_erro(mensagem):
    hora = datetime.now().strftime("%H:%M:%S")
    console.print(f"[bold cyan][{hora}][/bold cyan] [bold red]❌ ERRO:[/bold red] {mensagem}")

def log_aviso(mensagem):
    hora = datetime.now().strftime("%H:%M:%S")
    console.print(f"[bold cyan][{hora}][/bold cyan] [bold yellow]⚠️ AVISO:[/bold yellow] {mensagem}")

def log_painel(titulo, mensagem):
    console.print(Panel.fit(mensagem, title=titulo, border_style="bold blue"))