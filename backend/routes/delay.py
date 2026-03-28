from flask import Blueprint, request, jsonify
from services.orchestrator import procesar_atraso, ejecutar_acciones

delay_bp = Blueprint('delay', __name__)

@delay_bp.route('/report-delay', methods=['POST'])
def report_delay():
    data = request.json
    resultado = procesar_atraso(data.get('prompt', ''))
    return jsonify(resultado)

@delay_bp.route('/execute-plan', methods=['POST'])
def execute_plan():
    data = request.json
    resultado = ejecutar_acciones(data.get('actions', []))
    return jsonify(resultado)