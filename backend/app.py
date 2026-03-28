from flask import Flask
from flask_cors import CORS
from routes.delay import delay_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(delay_bp)

if __name__ == '__main__':
    app.run(port=8000, debug=True)