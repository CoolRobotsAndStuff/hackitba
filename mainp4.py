from rich.console import Console
from communicator import llamar_backend, ejecutar_plan
from interpreter import interpretar_respuesta
from display import mostrar_plan, mostrar_error, mostrar_confirmacion

console = Console()

if __name__ == "__main__":
    console.print("\n[bold yellow]HALeph — AI Workflow Orchestrator[/bold yellow]\n")

    prompt = input("Describí el problema (ej: PROJ-04 se atrasó 3 días, deadline el viernes): ")

    console.print("\n[yellow]⠿ Analizando dependencias...[/yellow]")

    data = llamar_backend(prompt)
    plan = interpretar_respuesta(data)

    if plan is None:
        mostrar_error("No se pudo obtener un plan.")
    else:
        console.print()
        mostrar_plan(plan)

        confirmar = input("\n¿Aplicar cambios? [s/n]: ")
        if confirmar.lower() == "s":
            console.print("\n[yellow]⠿ Ejecutando cambios en Calendar y Jira...[/yellow]")
            resultado = ejecutar_plan(data["actions"])

            if resultado and resultado.get("results"):
                mostrar_confirmacion(resultado["results"])
            else:
                console.print("[green]✓ Listo.[/green]")
        else:
            console.print("[dim]Cambios cancelados.[/dim]")