from interpreter import interpretar_respuesta

# Caso 1: respuesta normal y correcta
data_buena = {
    "status": "ok",
    "plan": [
        {
            "task_id": "T-04",
            "name": "Backend Auth",
            "assignee_before": "Juan",
            "assignee_after": "María",
            "date_before": "2025-06-10",
            "date_after": "2025-06-11",
            "changed": True
        }
    ]
}

# Caso 2: el backend devolvió None (error de conexión)
data_none = None

# Caso 3: el backend devolvió un error explícito
data_error = {
    "status": "error",
    "mensaje": "tarea no encontrada"
}

print("--- Caso 1: respuesta correcta ---")
resultado = interpretar_respuesta(data_buena)
print(f"Resultado: {resultado}")

print("\n--- Caso 2: None ---")
resultado = interpretar_respuesta(data_none)
print(f"Resultado: {resultado}")

print("\n--- Caso 3: error del backend ---")
resultado = interpretar_respuesta(data_error)
print(f"Resultado: {resultado}")