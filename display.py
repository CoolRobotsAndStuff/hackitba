from rich.table import Table
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns

console = Console()

def mostrar_plan(plan):
    # Resumen de Claude
    console.print(Panel(
        f"[white]{plan['summary']}[/white]",
        title="[bold]Análisis de la IA[/bold]",
        border_style="yellow"
    ))

    # Orden de tareas antes y después
    before = plan["task_order"].get("before", [])
    after = plan["task_order"].get("after", [])

    order_table = Table(title="Reordenamiento de tareas")
    order_table.add_column("Posición", justify="center")
    order_table.add_column("Antes", style="dim")
    order_table.add_column("Después")

    for i, (b, a) in enumerate(zip(before, after)):
        changed = b != a
        style = "yellow" if changed else ""
        order_table.add_row(
            str(i + 1),
            b,
            f"[yellow]{a}[/yellow]" if changed else a,
            style=style
        )

    console.print(order_table)

    # Acciones concretas
    if plan["acciones"]:
        actions_table = Table(title="Acciones a ejecutar")
        actions_table.add_column("Tarea")
        actions_table.add_column("Acción")
        actions_table.add_column("Nueva fecha")
        actions_table.add_column("Motivo")

        for accion in plan["acciones"]:
            actions_table.add_row(
                accion["task_id"],
                accion["type"].replace("_", " ").title(),
                accion["date_after"],
                accion["name"][:60] + "..." if len(accion["name"]) > 60 else accion["name"],
                style="yellow"
            )

        console.print(actions_table)

def mostrar_error(mensaje):
    console.print(f"\n[red]✗ {mensaje}[/red]")

def mostrar_confirmacion(results):
    for r in results:
        color = "green" if r["success"] else "red"
        console.print(f"[{color}]{r['message']}[/{color}]")
    console.print("[green]✓ Todos los cambios aplicados.[/green]")