from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional, Tuple

from core.graph_core import PowerGridGraph
from core.models import Edge, Node


VoltageLevel = Literal["HV", "MV", "LV"]


@dataclass(frozen=True)
class ConductorParams:
    """
    Parâmetros elétricos típicos para um nível de tensão.

    Atributos:
        resistivity:
            Resistividade elétrica do material do condutor em ohm·metro.
            Usamos valores típicos aproximados (por exemplo, alumínio).
        cross_section_area:
            Área de seção transversal do condutor em metros quadrados.
            Valores maiores indicam condutores mais grossos e, portanto,
            menor resistência para o mesmo comprimento.
    """
    resistivity: float
    cross_section_area: float


# Resistividade aproximada do alumínio (ohm·m).
RHO_ALUMINIUM = 2.82e-8

# Parâmetros típicos por nível de tensão.
# Os valores de área são aproximados e servem como parâmetros
# relativos entre HV/MV/LV, não como projeto elétrico real.
CONDUCTOR_BY_LEVEL = {
    "HV": ConductorParams(
        resistivity=RHO_ALUMINIUM,
        cross_section_area=300e-6,  # ~300 mm²
    ),
    "MV": ConductorParams(
        resistivity=RHO_ALUMINIUM,
        cross_section_area=150e-6,  # ~150 mm²
    ),
    "LV": ConductorParams(
        resistivity=RHO_ALUMINIUM,
        cross_section_area=70e-6,   # ~70 mm²
    ),
}


def _infer_edge_voltage(graph: PowerGridGraph, edge: Edge) -> Optional[float]:
    """
    Infere uma tensão típica para uma aresta a partir dos nós que
    ela conecta.

    Estratégia:

        1. Obtém os nós de origem e destino (`from_node` e `to_node`).
        2. Se algum dos nós possui `nominal_voltage` definido, usa
           o primeiro valor não-nulo encontrado.
        3. Caso nenhum dos nós possua `nominal_voltage`, retorna None,
           indicando que não é possível determinar a tensão típica
           da aresta.

    Parâmetros:
        graph:
            Grafo físico contendo nós e arestas.
        edge:
            Aresta cuja tensão típica será inferida.

    Retorno:
        Valor de tensão em volts (float) ou None se não houver dados.
    """
    from_node: Optional[Node] = graph.get_node(edge.from_node_id)
    to_node: Optional[Node] = graph.get_node(edge.to_node_id)

    candidates = []
    if from_node is not None and from_node.nominal_voltage is not None:
        candidates.append(from_node.nominal_voltage)
    if to_node is not None and to_node.nominal_voltage is not None:
        candidates.append(to_node.nominal_voltage)

    if not candidates:
        return None

    # Usa o primeiro valor disponível. Em cenários em que de fato
    # exista diferença, os nós devem ser ajustados na geração física.
    return float(candidates[0])


def _classify_voltage_level(voltage: float) -> VoltageLevel:
    """
    Classifica um valor de tensão em um dos três níveis lógicos:
    "HV" (alta tensão), "MV" (média tensão) ou "LV" (baixa tensão).

    Regras aproximadas:

        - voltage >= 100 kV  -> "HV"
        - 1 kV <= voltage < 100 kV -> "MV"
        - voltage < 1 kV -> "LV"

    Parâmetros:
        voltage:
            Valor de tensão em volts.

    Retorno:
        String "HV", "MV" ou "LV".
    """
    if voltage >= 100e3:
        return "HV"
    if voltage >= 1e3:
        return "MV"
    return "LV"


def _edge_resistance(
    graph: PowerGridGraph,
    edge: Edge,
) -> Optional[float]:
    """
    Calcula a resistência elétrica aproximada de uma aresta a partir
    do comprimento, da tensão típica e dos parâmetros de condutor
    associados ao nível de tensão.

    Fórmula básica (Lei de Ohm para resistores):

        R = ρ * L / A

    onde:
        ρ  = resistividade do material (ohm·m),
        L  = comprimento do condutor (m),
        A  = área da seção transversal (m²).

    Parâmetros:
        graph:
            Grafo físico da rede.
        edge:
            Aresta cujo valor de resistência será aproximado.

    Retorno:
        Valor de resistência em ohms (float) ou None se não for
        possível inferir tensão ou se os dados da aresta forem
        insuficientes.
    """
    if edge.length is None:
        return None

    length = float(edge.length)
    if length <= 0.0:
        return 0.0

    voltage = _infer_edge_voltage(graph, edge)
    if voltage is None or voltage <= 0.0:
        return None

    level = _classify_voltage_level(voltage)
    params = CONDUCTOR_BY_LEVEL[level]

    resistance = params.resistivity * length / params.cross_section_area
    return resistance


def estimate_edge_loss(
    graph: PowerGridGraph,
    edge: Edge,
    power: float,
) -> float:
    """
    Estima a perda de potência (ou custo proporcional) ao transportar
    uma potência `power` através de uma aresta específica.

    Modelo utilizado (trifásico simplificado):

        - Consideramos um sistema trifásico balanceado com fator de
          potência aproximadamente igual a 1. Então:

              I ≈ P / (√3 · V)

          onde:
              I = corrente de linha (A),
              P = potência aparente (W) aproximada pela potência ativa,
              V = tensão de linha (V).

        - A perda resistiva no trecho é dada por:

              P_loss = I² · R

          onde R é a resistência do trecho (ohms).

    Observações:
        - O sistema assume que `power` pode vir em kW (comum em
          simuladores de distribuição) ou Watts. Se o valor for muito
          pequeno (< 1000) e a tensão alta (> 1000), assume-se kW e
          converte-se para Watts para o cálculo físico.
          (Correção 1.4: Inconsistência de unidades).

        - Quando o valor de tensão ou resistência não puder ser
          inferido (por falta de dados), a função retorna um custo
          proporcional ao comprimento, para não bloquear o roteamento.

        - O valor retornado é um custo relativo usado pelo algoritmo
          de roteamento (A* / Dijkstra); não se destina a dimensionar
          equipamentos na realidade.

    Parâmetros:
        graph:
            Grafo físico contendo a topologia da rede.
        edge:
            Aresta pela qual a potência será transportada.
        power:
            Potência que se deseja transportar pelo trecho.

    Retorno:
        Estimativa de perda de potência em unidades compatíveis com P
        (convertida se necessário).
        Se não for possível calcular de forma física, retorna um
        custo proporcional ao comprimento do trecho.
    """
    if edge.length is None:
        # Sem comprimento, não há como estimar custo físico;
        # retorna um custo neutro.
        return 0.0

    length = float(edge.length)
    if power <= 0.0:
        # Sem potência a transportar, consideramos custo nulo.
        return 0.0

    voltage = _infer_edge_voltage(graph, edge)
    resistance = _edge_resistance(graph, edge)

    if voltage is None or voltage <= 0.0 or resistance is None:
        # Falha em inferir parâmetros físicos; usa custo proporcional
        # ao produto potência x comprimento apenas como heurística.
        return abs(power) * length

    # Conversão de Unidades (Correção 1.4)
    # Se potência parece estar em kW (pequena) e tensão em Volts (grande), convertemos.
    # Ex: power=100 (kW), voltage=13800 (V).
    # Limiar heurístico: power < 1MW e voltage > 1kV.
    power_watts = abs(power)
    if power_watts < 10000.0 and voltage > 1000.0:
         power_watts *= 1000.0

    # Corrente aproximada em sistema trifásico balanceado.
    current = power_watts / (math.sqrt(3.0) * voltage)

    # Perda resistiva aproximada.
    loss = (current ** 2) * resistance
    return loss
