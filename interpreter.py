def interpretar_respuesta(data):
    # Si el backend devolvió None (hubo un error), avisamos
    if data is None:
        return None
    
    # Si el backend devolvió un error explícito
    if data.get("status") != "ok":
        print(f"El backend devolvió un error: {data.get('mensaje', 'desconocido')}")
        return None
    
    # Si todo está bien, devolvemos la lista de tareas del plan
    return data["plan"]