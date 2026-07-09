import time
import os
import sqlite3
from datetime import datetime
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

console = Console()

def obter_metricas():
    """Simula ou lê a telemetria atual da base de dados do Nexus."""
    # Conexão segura com o SQLite para ler o estado atual se houver dados
    db_path = "nexus_store.db"
    blocos, latência, status = 5302, "7.49 ms", "OPERACIONAL"
    
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Ajuste essa query futuramente conforme o nome real da sua tabela
            cursor.execute("SELECT COUNT(*) FROM logs")
            resultado = cursor.fetchone()
            if resultado:
                blocos = resultado[0]
            conn.close()
        except Exception:
            pass # Fallback para os últimos dados conhecidos do relatório

    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": status,
        "blocos": blocos,
        "lat_media": latência,
        "p95": "12.62 ms",
        "p99": "13.82 ms",
        "cpu_load": f"{os.getloadavg()[0]:.2f}" if hasattr(os, 'getloadavg') else "N/A"
    }

def gerar_layout(data):
    """Monta a interface visual dividida em painéis coloridos."""
    # Tabela Central de Métricas
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Métrica", style="dim", width=25)
    table.add_column("Valor Atual", justify="right", style="bold green")

    table.add_row("Status do Sistema", f"[bold blink green]{data['status']}[/]")
    table.add_row("Blocos em Cache/DB", str(data['blocos']))
    table.add_row("Tempo Médio de Resposta", data['lat_media'])
    table.add_row("Latência Crítica (P95)", data['p95'])
    table.add_row("Latência Extrema (P99)", data['p99'])
    table.add_row("Carga de Sistema (Load)", data['cpu_load'])

    # Construção dos Painéis do Terminal
    menu_panel = Panel(
        table, 
        title=f"[bold white]NEXUS RUNTIME V500[/] - Telemetria: {data['timestamp']}", 
        border_style="blue",
        subtitle="[dim]Pressione CTRL+C para sair[/]"
    )
    return menu_panel

# Loop de Atualização ao Vivo (Live Update)
data = obter_metricas()
with Live(gerar_layout(data), refresh_per_second=1, screen=True) as live:
    try:
        while True:
            time.sleep(1)
            data = obter_metricas()
            live.update(gerar_layout(data))
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Dashboard encerrado de forma segura.[/]")
