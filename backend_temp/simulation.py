# APENAS TESTE INICIAL DE FUNCIONAMENTO!!!!
import copy
from .tree import CURRENT_TREE_STATE, _get_node, _recalculate_all_loads_and_statuses, _update_tree_state

def sim_sobrecarga(id_no):
    """Simula uma sobrecarga: Aumenta a carga para 120% da capacidade."""
    # Criamos uma cópia do estado atual para a simulação
    simulated_tree = copy.deepcopy(CURRENT_TREE_STATE)
    node = _get_node(simulated_tree, id_no)
    logs = [f"Simulação de Sobrecarga iniciada no nó {id_no}."]

    if not node:
        return {"error": f"Nó com ID {id_no} não encontrado para simulação.", "logs": logs}

    cap = node.get("capacity_kw", 0)
    
    if cap <= 0:
        logs.append("Nó não possui capacidade definida. Forçando status para 'overloaded'.")
        nova_carga = 1000 # Valor arbitrário alto
    else:
        # Aumenta a carga para 120% da capacidade
        nova_carga = cap * 1.2
        logs.append(f"Carga do nó {id_no} forçada para {nova_carga:.2f} kW (120% da capacidade).")

    # A sobrecarga só pode ser simulada diretamente se for um nó consumidor.
    # Para transformadores/subestações, a sobrecarga viria dos filhos.
    
    if node["node_type"] == "consumer":
        node["current_load_kw"] = nova_carga
        
        # Recalcula as cargas dos pais (bottom-up) e o status de todos os nós
        recalc_logs = _recalculate_all_loads_and_statuses(simulated_tree)
        logs.extend(recalc_logs)
    
    else:
        # Para nós não-consumidores, forçamos a carga alta nos filhos (se existirem)
        # Se não tiver filhos, forçamos o status
        children = [n for n in simulated_tree if n.get("parent_id") == id_no]
        if children:
            for child in children:
                if child.get("node_type") == "consumer" and child.get("capacity_kw", 0) > 0:
                     child["current_load_kw"] = child["capacity_kw"] * 1.5 # Sobrecarga o filho
            
            recalc_logs = _recalculate_all_loads_and_statuses(simulated_tree)
            logs.extend(recalc_logs)
            logs.append("Sobrecarga propagada aos filhos para afetar o nó pai.")

        else:
            # Não há filhos consumidores, apenas forçamos o status para teste visual
            node["current_load_kw"] = cap * 1.2
            node["status"] = "overloaded"
            logs.append("Nó sem filhos. Status de sobrecarga forçado.")


    return {"tree": simulated_tree, "logs": logs}

def sim_falha_no(id_no):
    """Simula falha de nó: Define o status como 'offline' e carga para 0. Propaga a falha aos filhos."""
    simulated_tree = copy.deepcopy(CURRENT_TREE_STATE)
    node = _get_node(simulated_tree, id_no)
    logs = [f"Simulação de Falha de Nó iniciada no nó {id_no}."]

    if not node:
        return {"error": f"Nó com ID {id_no} não encontrado para simulação.", "logs": logs}

    # A falha causa status offline e perda de carga
    node["current_load_kw"] = 0
    node["status"] = "offline"
    logs.append(f"Nó {id_no} falhou e está offline. Carga zerada.")
    
    # Propaga a falha para os filhos (eles também ficam offline)
    # E zera a carga
    def propagate_failure(node_id):
        children = [n for n in simulated_tree if n.get("parent_id") == node_id]
        for child in children:
            if child["status"] != "offline":
                child["current_load_kw"] = 0
                child["status"] = "offline"
                logs.append(f"Falha propagada: Nó {child['id']} está offline.")
                propagate_failure(child["id"]) # Recursão para descendentes

    propagate_failure(id_no)

    # Recalcula as cargas dos pais restantes (a carga deles diminuiu)
    recalc_logs = _recalculate_all_loads_and_statuses(simulated_tree)
    logs.extend(recalc_logs)

    return {"tree": simulated_tree, "logs": logs}

def sim_pico_consumo(id_no):
    """Simula pico de consumo: Aumenta a carga de todos os consumidores sob o nó para 95% da capacidade."""
    simulated_tree = copy.deepcopy(CURRENT_TREE_STATE)
    node = _get_node(simulated_tree, id_no)
    logs = [f"Simulação de Pico de Consumo iniciada a partir do nó {id_no}."]

    if not node:
        return {"error": f"Nó com ID {id_no} não encontrado para simulação.", "logs": logs}
    
    target_nodes = []

    # 1. Encontra todos os consumidores sob o nó alvo (incluindo o próprio se for consumidor)
    def find_descendants(node_id):
        n = _get_node(simulated_tree, node_id)
        if not n: return

        if n["node_type"] == "consumer":
            target_nodes.append(n)

        children = [n for n in simulated_tree if n.get("parent_id") == node_id]
        for child in children:
            find_descendants(child["id"])

    # Se o próprio nó for consumidor, ele é um alvo. Se não, procuramos nos filhos.
    if node["node_type"] == "consumer":
        target_nodes.append(node)
    
    children_to_check = [n for n in simulated_tree if n.get("parent_id") == id_no]
    for child in children_to_check:
        find_descendants(child["id"])
        
    if not target_nodes:
        logs.append("Nenhum nó consumidor encontrado sob o nó alvo.")
        return {"tree": simulated_tree, "logs": logs}

    # 2. Aplica o pico de consumo (95% da capacidade)
    for consumer in target_nodes:
        cap = consumer.get("capacity_kw", 0)
        if cap > 0:
            new_load = cap * 0.95
            consumer["current_load_kw"] = new_load
            logs.append(f"Consumidor {consumer['id']} subiu a carga para {new_load:.2f} kW (95% cap).")

    # 3. Recalcula todas as cargas e status
    recalc_logs = _recalculate_all_loads_and_statuses(simulated_tree)
    logs.extend(recalc_logs)
    
    return {"tree": simulated_tree, "logs": logs}
