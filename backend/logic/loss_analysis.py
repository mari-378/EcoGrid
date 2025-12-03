from __future__ import annotations

import math
from typing import Set, Tuple, List

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex
from physical.energy_loss import get_segment_resistance


def propagate_losses(graph: PowerGridGraph, index: BPlusIndex) -> None:
    """
    Percorre a árvore lógica de cima para baixo (Gerador -> Consumidor),
    calculando e acumulando as perdas energéticas (Técnicas I²R) em cada trecho.

    O valor final é armazenado em `node.energy_loss_pct`.

    Lógica:
        1. Raízes (Usinas) começam com Perda Acumulada = 0.
        2. Para cada filho:
           - Obtém aresta física entre pai e filho.
           - Calcula corrente estimada: I = P_filho / (sqrt(3) * V_nominal).
           - Calcula resistência do trecho: R = get_segment_resistance(edge).
           - Calcula perda local: Loss = I² * R.
           - Acumula: Total_Loss = Pai_Loss + Local_Loss.
           - Calcula % para exibição: (Total_Loss / (Load_Filho + Total_Loss)) * 100.
    """

    # Fila para BFS: (node_id, parent_accumulated_loss_watts)
    queue: List[Tuple[str, float]] = []

    # Inicializa raízes com 0 perda
    roots = index.get_roots()
    for root_id in roots:
        root_node = graph.get_node(root_id)
        if root_node:
            root_node.energy_loss_pct = 0.0
            queue.append((root_id, 0.0))

    while queue:
        parent_id, parent_loss_acc = queue.pop(0)

        children = index.get_children(parent_id)
        for child_id in children:
            child_node = graph.get_node(child_id)
            if not child_node:
                continue

            # 1. Pega aresta entre pai e filho
            # O grafo físico não tem get_edge_between, precisamos procurar na adjacência
            edge = None
            neighbors = graph.neighbors(parent_id)
            for neighbor_info in neighbors:
                if neighbor_info.neighbor_id == child_id:
                    edge = neighbor_info.edge
                    break

            # Se não houver aresta física direta, assumimos perda zero neste "salto"
            # (embora logicamente deva haver conexão física se há relação pai-filho roteada)
            local_loss = 0.0
            if edge:
                # 2. Calcula perda local (Local Joule Effect)
                # Potência que chega ao filho (Load)
                # Se current_load for None, assumimos 0
                power_watts = float(child_node.current_load or 0.0)

                # Para cálculo físico, precisamos converter para Watts se estiver em kW?
                # O sistema parece usar kW como padrão para current_load em logs (ex: "100.00kW").
                # energy_loss.py assume que valores < 10000 e tensão > 1000 => converte.
                # Vamos seguir a lógica do energy_loss.py: estimate_edge_loss faz conversão.
                # Mas aqui estamos reimplementando a lógica específica para Loss Propagation.
                # Vamos assumir que current_load está na mesma unidade que estimate_edge_loss espera (kW ou W misto).
                # Para consistência com a fórmula: I = P / (sqrt(3)*V)
                # Se V é Volts, P deve ser Watts. Se P é kW, I será kA? Não.
                # O padrão do sistema (pela leitura de logs) é kW.
                # V nominal é Volts (13800, 220, etc).

                # Conversão explícita para Watts se parecer kW
                # Se tensão > 1kV (1000V) e carga < 100MW (100000kW), assume kW -> W.
                # Se tensão < 1kV (ex: 220V) e carga pequena, também pode ser kW.
                # Melhor assumir kW sempre, já que é padrão de distribuição/simulação.
                # A menos que seja muito grande.

                voltage = child_node.nominal_voltage

                if voltage and voltage > 0:
                    power_in_watts = power_watts * 1000.0 # Assumindo kW -> W

                    # Corrente I = P / (sqrt(3) * V)
                    # Trifásico
                    current = power_in_watts / (math.sqrt(3.0) * voltage)

                    resistance = get_segment_resistance(graph, edge) or 0.0

                    # Perda = I² * R
                    local_loss = (current ** 2) * resistance

                    # Converte de volta para kW para somar com carga (que está em kW) ??
                    # Não, percentage calculation needs same units.
                    # Load is kW. Loss computed in Watts.
                    # Convert local_loss to kW.
                    local_loss /= 1000.0

            # 3. Acumula
            total_loss = parent_loss_acc + local_loss

            # 4. Calcula % para o Front
            # Load (kW) + Loss (kW) = Total Energy Generated for this node
            current_load_kw = float(child_node.current_load or 0.0)
            energy_required = current_load_kw + total_loss

            pct = 0.0
            if energy_required > 0.000001:
                pct = (total_loss / energy_required) * 100.0

            child_node.energy_loss_pct = round(pct, 2)

            queue.append((child_id, total_loss))
