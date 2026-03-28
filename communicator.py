import requests

def llamar_backend(task_id, delay_days):
    try:
        respuesta = requests.post(
            "http://localhost:8000/report-delay",
            json={"task_id": task_id, "delay_days": delay_days},
            timeout=10
        )
        return respuesta.json()
    except requests.exceptions.ConnectionError:
        print("Error: no se pudo conectar al backend.")
        return None
    except Exception as e:
        print(f"Error inesperado: {e}")
        return None