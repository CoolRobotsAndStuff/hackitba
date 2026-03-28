from rich.console import Console
from communicator import llamar_backend      # nombre correcto del archivo
from interpreter import interpretar_respuesta
from display import mostrar_plan, mostrar_confirmacion, mostrar_error

console = Console()

if __name__ == "__main__":
    console.print("[bold blue]AI Workflow Orchestrator[/bold blue]")
    
    tarea = input("¿Qué tarea se atrasó? (ej: T-04): ")
    dias = input("¿Cuántos días de atraso?: ")

    console.print("[yellow]⠿ Analizando dependencias...[/yellow]")
    
    # Paso 1: comunicarse con el backend
    data = llamar_backend(tarea, int(dias))
    
    # Paso 2: interpretar la respuesta
    plan = interpretar_respuesta(data)
    
    # Si algo falló, cortamos acá
    if plan is None:
        mostrar_error("No se pudo obtener un plan. Revisá el backend.")
    else:
        # Paso 3: mostrar el plan
        mostrar_plan(plan)
        
        # Paso 4: pedir confirmación
        confirmar = input("\n¿Aplicar cambios? [s/n]: ")
        if confirmar.lower() == "s":
            mostrar_confirmacion()
        else:
            console.print("[dim]Cambios cancelados.[/dim]")
