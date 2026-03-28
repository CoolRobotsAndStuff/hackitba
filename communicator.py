import requests

def llamar_backend(prompt_texto):
    try:
        respuesta = requests.post(
            "http://localhost:8000/report-delay",
            json={"prompt": prompt_texto},
            timeout=10
        )
        return respuesta.json()
    except requests.exceptions.ConnectionError:
        print("Error: no se pudo conectar al backend.")
        return None
    except Exception as e:
        print(f"Error inesperado: {e}")
        return None

def ejecutar_plan(actions):
    try:
        respuesta = requests.post(
            "http://localhost:8000/execute-plan",
            json={"actions": actions},
            timeout=10
        )
        return respuesta.json()
    except Exception as e:
        print(f"Error al ejecutar: {e}")
        return None