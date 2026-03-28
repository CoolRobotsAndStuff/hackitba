from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Leer lo que nos mandaron
        largo = int(self.headers['Content-Length'])
        body = json.loads(self.rfile.read(largo))
        
        print(f"Backend falso recibió: {body}")
        
        # Armar una respuesta inventada
        respuesta = {
            "status": "ok",
            "plan": [
                {
                    "task_id": body["task_id"],
                    "name": "Tarea de prueba",
                    "assignee_before": "Juan",
                    "assignee_after": "María",
                    "date_before": "2025-06-10",
                    "date_after": "2025-06-11",
                    "changed": True
                },
                {
                    "task_id": "T-05",
                    "name": "Tarea dependiente",
                    "assignee_before": "María",
                    "assignee_after": "María",
                    "date_before": "2025-06-11",
                    "date_after": "2025-06-13",
                    "changed": True
                }
            ]
        }
        
        # Mandar la respuesta
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(respuesta).encode())
    
    # Silenciar los logs automáticos del servidor
    def log_message(self, format, *args):
        pass

print("Backend falso corriendo en http://localhost:8000")
HTTPServer(('localhost', 8000), Handler).serve_forever()