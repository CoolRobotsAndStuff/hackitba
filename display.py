from rich.table import Table
from rich.console import Console

console = Console()

def mostrar_plan(plan):
    table = Table(title="Plan propuesto por la IA")
    table.add_column("ID")
    table.add_column("Nombre")
    table.add_column("Asignado antes")
    table.add_column("Asignado después")
    table.add_column("Fecha antes")
    table.add_column("Fecha después")

    for tarea in plan:
        estilo = "yellow" if tarea["changed"] else ""
        table.add_row(
            tarea["task_id"],
            tarea["name"],
            tarea["assignee_before"],
            tarea["assignee_after"],
            tarea["date_before"],
            tarea["date_after"],
            style=estilo
        )

    console.print(table)

def mostrar_confirmacion():
    console.print("\n[green]✓ Cambios aplicados en Calendar y Jira[/green]")

def mostrar_error(mensaje):
    console.print(f"\n[red]✗ {mensaje}[/red]")