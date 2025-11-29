# APENAS TESTE INICIAL DE FUNCIONAMENTO!!!!
import json

# Árvore inicial (flat list) para simular o estado do sistema
INITIAL_TREE = [
    {
      "id": "GP_001",
      "parent_id": "",
      "node_type": "GENERATION_PLANT",
      "position_x": 100.0,
      "position_y": 200.0,
      "cluster_id": "CLUSTER_A",
      "nominal_voltage": 500000.0,
      "capacity": 5000000.0,
      "current_load": 3200000.0,
      "status": "NORMAL"
    },
    {
      "id": "TS_001",
      "parent_id": "GP_001",
      "node_type": "TRANSMISSION_SUBSTATION",
      "position_x": 110.0,
      "position_y": 210.0,
      "cluster_id": "CLUSTER_A",
      "nominal_voltage": 500000.0,
      "capacity": 2000000.0,
      "current_load": 1600000.0,
      "status": "WARNING"
    },
    {
      "id": "DS_001",
      "parent_id": "TS_001",
      "node_type": "DISTRIBUTION_SUBSTATION",
      "position_x": 120.0,
      "position_y": 215.0,
      "cluster_id": "CLUSTER_A",
      "nominal_voltage": 13800.0,
      "capacity": 800000.0,
      "current_load": 820000.0,
      "status": "OVERLOADED"
    },
    {
      "id": "C_001",
      "parent_id": "DS_001",
      "node_type": "CONSUMER_POINT",
      "position_x": 121.0,
      "position_y": 220.0,
      "cluster_id": "CLUSTER_A",
      "nominal_voltage": 220.0,
      "capacity": 5000.0,
      "current_load": 4200.0,
      "status": "WARNING"
    },
    {
      "id": "C_002",
      "parent_id": "DS_001",
      "node_type": "CONSUMER_POINT",
      "position_x": 122.0,
      "position_y": 222.0,
      "cluster_id": "CLUSTER_A",
      "nominal_voltage": 220.0,
      "capacity": 3000.0,
      "current_load": 3100.0,
      "status": "OVERLOADED"
    },
    {
      "id": "C_003",
      "parent_id": "DS_001",
      "node_type": "CONSUMER_POINT",
      "position_x": 300.0,
      "position_y": 400.0,
      "cluster_id": "CLUSTER_B",
      "nominal_voltage": 220.0,
      "capacity": 4000.0,
      "current_load": 0.0,
      "status": "UNSUPPLIED"
    }
]

# Variável para manter o estado atual da árvore no backend (muito importante para simulação!)
CURRENT_TREE_STATE = list(INITIAL_TREE)

def _get_node(tree, node_id):
    """Retorna o nó pelo ID ou None."""
    return next((n for n in tree if n["id"] == node_id), None)

def _update_tree_state(new_tree):
    """Atualiza o estado global da árvore e retorna a nova árvore e logs."""
    global CURRENT_TREE_STATE
    # Clonamos a lista para evitar side effects (mutação in place)
    CURRENT_TREE_STATE = [dict(node) for node in new_tree]
    # Logs mínimos para o front-end
    return {"tree": CURRENT_TREE_STATE, "logs": ["Estado da árvore atualizado com sucesso."]}

def _recalculate_utilization(node):
    """Recalcula o utilization_ratio e o status de um único nó."""
    if node.get("node_type") == "consumer" and node.get("current_load_kw") == 0:
        node["status"] = "offline"
        node["utilization_ratio"] = 0
        return
        
    cap = node.get("capacity_kw", 1)
    load = node.get("current_load_kw", 0)
    
    if cap <= 0: # Evitar divisão por zero, tratar capacidade inválida como erro ou carga total
        ratio = 1.0 
    else:
        ratio = load / cap
    
    node["utilization_ratio"] = round(ratio, 2)
    
    if ratio > 1.0:
        node["status"] = "overloaded"
    elif ratio >= 0.8:
        node["status"] = "warning"
    elif ratio == 0:
        node["status"] = "offline"
    else:
        node["status"] = "normal"

def _recalculate_all_loads_and_statuses(tree):
    """
    Recalcula as cargas dos pais (bottom-up) e o status de todos os nós.
    Em um sistema real, isso seria muito mais complexo e recursivo.
    Para o teste, apenas atualizaremos o status.
    """
    logs = ["Recálculo de carga e status iniciado. (Simulação simples)"]
    
    # 1. Recalcula a carga dos nós pais (bottom-up)
    
    # Mapeia filhos para pais para uma iteração eficiente
    parent_map = {node["id"]: node["parent_id"] for node in tree}
    # Obtém todos os IDs únicos dos nós pais, excluindo o root (parent_id vazio)
    parent_ids = sorted(list(set(parent_map.values())), key=lambda x: x == "", reverse=True)
    parent_ids = [pid for pid in parent_ids if pid != ""]
    
    # Iterar sobre os pais em ordem reversa (do nível mais baixo para o root)
    for parent_id in reversed(parent_ids):
        parent_node = _get_node(tree, parent_id)
        if not parent_node:
            continue

        # Encontra os filhos (transformadores/consumidores)
        children = [n for n in tree if n.get("parent_id") == parent_id]
        
        # A carga do pai é a soma das cargas dos filhos (simples)
        total_load = sum(child.get("current_load_kw", 0) for child in children)
        
        # Atualiza a carga do pai
        parent_node["current_load_kw"] = total_load
        
        logs.append(f"Carga do nó {parent_id} ({parent_node['id']}) recalculada para {total_load} kW.")


    # 2. Recalcula a utilização e status de todos os nós
    for node in tree:
        _recalculate_utilization(node)
        
    logs.append("Status e utilização de todos os nós recalculados.")
    return logs


def get_initial_tree():
    """Retorna a árvore inicial. Aqui, inicializa o estado."""
    global CURRENT_TREE_STATE
    # Garantir que o estado inicial é carregado e tem o status/utilização corretos
    CURRENT_TREE_STATE = [dict(node) for node in INITIAL_TREE]
    _recalculate_all_loads_and_statuses(CURRENT_TREE_STATE)
    
    return CURRENT_TREE_STATE

def alterar_capacidade_no(id_no, nova_capacidade):
    """Altera a capacidade de um nó e recalcula o estado."""
    new_tree = [dict(node) for node in CURRENT_TREE_STATE]
    node = _get_node(new_tree, id_no)
    logs = [f"Tentativa de alterar a capacidade do nó {id_no} para {nova_capacidade} kW."]

    if not node:
        return {"error": f"Nó com ID {id_no} não encontrado.", "logs": logs}
    
    if nova_capacidade <= 0:
        return {"error": "Capacidade deve ser um valor positivo.", "logs": logs}

    node["capacity_kw"] = nova_capacidade
    
    # Recalcula a utilização e o status (apenas do nó)
    _recalculate_utilization(node)
    logs.append(f"Capacidade do nó {id_no} alterada com sucesso.")
    
    return _update_tree_state(new_tree)

def alterar_carga_no(id_no, nova_carga):
    """Altera a carga de um nó e recalcula o estado (carga afeta os pais)."""
    new_tree = [dict(node) for node in CURRENT_TREE_STATE]
    node = _get_node(new_tree, id_no)
    logs = [f"Tentativa de alterar a carga do nó {id_no} para {nova_carga} kW."]

    if not node:
        return {"error": f"Nó com ID {id_no} não encontrado.", "logs": logs}
    
    if node["node_type"] != "consumer":
        return {"error": f"Carga só pode ser alterada diretamente em nós consumidores. Nó {id_no} é {node['node_type']}.", "logs": logs}
    
    if nova_carga < 0:
        return {"error": "Carga não pode ser negativa.", "logs": logs}

    node["current_load_kw"] = nova_carga
    
    # Recalcula todas as cargas e status, pois a carga de um filho afeta os pais
    recalc_logs = _recalculate_all_loads_and_statuses(new_tree)
    logs.extend(recalc_logs)
    
    return _update_tree_state(new_tree)

def adicionar_no(id_do_pai):
    return # aqui seria a função para adicionar um novo nó

def deletar_no(id_no):
    """Deleta um nó e seus filhos, e recalcula o estado."""
    new_tree = [dict(node) for node in CURRENT_TREE_STATE]
    logs = [f"Tentativa de deletar o nó {id_no} e seus descendentes."]
    
    node_to_delete = _get_node(new_tree, id_no)
    if not node_to_delete:
        return {"error": f"Nó com ID {id_no} não encontrado.", "logs": logs}

    nodes_to_keep = []
    deleted_ids = set()

    # 1. Encontra todos os descendentes para deletar
    def find_descendants(node_id):
        deleted_ids.add(node_id)
        children = [n["id"] for n in new_tree if n.get("parent_id") == node_id]
        for child_id in children:
            find_descendants(child_id)
            
    find_descendants(id_no)
    
    # 2. Filtra a nova árvore
    nodes_to_keep = [n for n in new_tree if n["id"] not in deleted_ids]

    if not nodes_to_keep:
        logs.append("Alerta: A árvore está vazia após a exclusão do nó raiz.")
        
    logs.append(f"Nós deletados: {', '.join(deleted_ids)}")

    # 3. Recalcula as cargas dos pais restantes
    if nodes_to_keep:
        recalc_logs = _recalculate_all_loads_and_statuses(nodes_to_keep)
        logs.extend(recalc_logs)
    
    return _update_tree_state(nodes_to_keep)

def alterar_pai_no(id_no, new_parent_id):
    """Altera o pai de um nó e recalcula o estado."""
    new_tree = [dict(node) for node in CURRENT_TREE_STATE]
    node = _get_node(new_tree, id_no)
    new_parent = _get_node(new_tree, new_parent_id)
    logs = [f"Tentativa de alterar o pai do nó {id_no} para {new_parent_id}."]

    if not node:
        return {"error": f"Nó de origem com ID {id_no} não encontrado.", "logs": logs}
    
    if new_parent_id and not new_parent:
        return {"error": f"Novo pai com ID {new_parent_id} não encontrado.", "logs": logs}
    
    if id_no == new_parent_id:
        return {"error": "Um nó não pode ser pai de si mesmo.", "logs": logs}
    
    # Verifica ciclos (simples: se o nó de origem é ancestral do nó pai)
    current_parent_id = new_parent_id
    while current_parent_id:
        if current_parent_id == id_no:
            return {"error": "Ciclo detectado: O novo pai é um descendente do nó de origem.", "logs": logs}
        ancestor = _get_node(new_tree, current_parent_id)
        current_parent_id = ancestor.get("parent_id") if ancestor else None


    old_parent_id = node["parent_id"]
    node["parent_id"] = new_parent_id
    logs.append(f"Pai do nó {id_no} alterado de {old_parent_id or 'Root'} para {new_parent_id or 'Root'} com sucesso.")

    # Recalcula todas as cargas e status, pois a mudança de pai afeta a carga de ambos os pais
    recalc_logs = _recalculate_all_loads_and_statuses(new_tree)
    logs.extend(recalc_logs)
    
    return _update_tree_state(new_tree)
