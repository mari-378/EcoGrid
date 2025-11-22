from flask import jsonify, request

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Servidor funcionando!", 200

@app.route('/tree', methods=['POST'])
def tree():
    '''endpoint para enviar a árvore completa inicial para o frontend'''

@app.route('/simulation', methods=['POST'])
def simulation():
    '''endpoint para receber os dados da simulação do frontend e retornar os resultados'''
    data = request.get_json()
    if not data:
        return jsonify({"error": "Nenhum dado enviado"}), 400
    
    id_do_no, tipo_de_simulacao  = data.get('id'), data.get('simulation_type')
    if not id_do_no or not tipo_de_simulacao:
        return jsonify({"error": "Parâmetros insuficientes"}), 400
    
    if tipo_de_simulacao == 'overload':
        nova_arvore = sim_sobrecarga(id_do_no)
    elif tipo_de_simulacao == 'node-failure':
        nova_arvore = sim_falha_no(id_do_no)
    elif tipo_de_simulacao == 'consumption-peak':
        nova_arvore = sim_pico_consumo(id_do_no)
    else:
        return jsonify({"error": "Tipo de simulação inválido"}), 400
    
    return jsonify(nova_arvore), 200

@app.route('/change-node', methods=['POST'])
def change_node():
    '''endpoint para alterar um nó específico na árvore'''
    data = request.get_json()
    if not data:
        return jsonify({"error": "Nenhum dado enviado"}), 400
    
    id_do_no = data.get('id')
    if not id_do_no:
        return jsonify({"error": "ID do nó não fornecido"}), 400

    if 'capacity_kw' in data:
        nova_capacidade = data['capacity_kw']
        nova_arvore = alterar_capacidade_no(id_do_no, nova_capacidade)
    elif 'current_load_kw' in data:
        nova_carga = data['current_load_kw']
        nova_arvore = alterar_carga_no(id_do_no, nova_carga)
    elif 'delete_node' in data:
        nova_arvore = deletar_no(id_do_no)
    elif 'new_parent' in data:
        novo_pai = data['new_parent']
        nova_arvore = alterar_pai_no(id_do_no, novo_pai)
    else:
        return jsonify({"error": "Nenhuma ação válida fornecida"}), 400
    
    return jsonify(nova_arvore), 200
    