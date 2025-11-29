from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, MutableMapping, Sequence, Set

from backend.core.graph_core import PowerGridGraph
from backend.core.models import Node, Edge, NodeType
from backend.logic.bplus_index import BPlusIndex
from backend.logic.parent_selection import (
    ParentSelectionResult,
    find_best_parent_for_node,
)
from backend.logic import load_aggregation
from backend.physical.device_model import IoTDevice


@dataclass
class ChangeParentResult:
    """
    Resultado de uma operação de troca de pai lógico.

    Atributos:
        success:
            Indica se a operação foi concluída com sucesso.
        child_id:
            Identificador do nó cujo pai foi (ou seria) alterado.
        old_parent_id:
            Identificador do pai anterior, quando existente.
        new_parent_id:
            Identificador do novo pai, quando a operação é bem-sucedida.
        total_cost:
            Custo do caminho físico até o novo pai (quando aplicável).
        reason:
            Mensagem textual resumindo o motivo em caso de falha ou
            descrevendo a decisão tomada em caso de sucesso.
        path:
            Caminho físico (sequência de nós) entre o filho e o novo
            pai escolhido, quando a operação utiliza roteamento.
    """
    success: bool
    child_id: str
    old_parent_id: Optional[str]
    new_parent_id: Optional[str]
    total_cost: float
    reason: Optional[str]
    path: List[str]


def _allowed_parent_types_for(child_type: NodeType) -> Set[NodeType]:
    """
    Define quais tipos de nós são aceitáveis como pai lógico para
    um determinado tipo de nó filho.

    Esta função replica a política usada no módulo de seleção de
    pai (`parent_selection`) para permitir também validações em
    operações de "forçar" troca de pai.

    Parâmetros:
        child_type:
            Tipo do nó filho.

    Retorno:
        Conjunto de tipos permitidos como pai. Pode ser vazio quando
        o tipo não admite pai (usinas, por exemplo).
    """
    if child_type == NodeType.CONSUMER_POINT:
        return {NodeType.DISTRIBUTION_SUBSTATION}
    if child_type == NodeType.DISTRIBUTION_SUBSTATION:
        return {NodeType.TRANSMISSION_SUBSTATION}
    if child_type == NodeType.TRANSMISSION_SUBSTATION:
        return {NodeType.GENERATION_PLANT}
    return set()


def _has_capacity_for_child(parent: Node, child: Node) -> bool:
    """
    Verifica se o nó pai possui capacidade suficiente para acomodar
    a carga do filho, considerando a carga já agregada no pai.

    Regras:
        - Se `parent.capacity` for None, consideramos que não há
          limite explícito de capacidade.
        - Se `child.current_load` for None, a carga incremental é
          considerada zero.
        - Se `parent.current_load` for None, a carga atual é
          considerada zero.

    Parâmetros:
        parent:
            Nó candidato a pai.
        child:
            Nó filho cuja carga será atribuída ao pai.

    Retorno:
        True se a operação não ultrapassar a capacidade declarada
        do pai; False em caso contrário.
    """
    if parent.capacity is None:
        return True

    child_load = child.current_load or 0.0
    parent_load = parent.current_load or 0.0

    return (parent_load + child_load) <= parent.capacity


class LogicalGraphService:
    """
    Serviço responsável por manter a coerência da camada lógica da
    rede sobre o grafo físico.

    Esta classe não cria o grafo físico nem o índice lógico
    (`BPlusIndex`), mas opera sobre eles para:

        - conectar nós recém-inseridos a pais adequados (via A*);
        - remover estações e tentar realocar seus filhos;
        - trocar o pai lógico de nós com ou sem roteamento;
        - atualizar cargas agregadas após mudanças em dispositivos;
        - registrar consumidores sem suprimento adequado.

    Atributos:
        graph:
            Grafo físico da rede.
        index:
            Índice lógico que armazena a hierarquia pai–filho.
        unsupplied_consumers:
            Conjunto de identificadores de nós consumidores que, no
            momento, não possuem pai viável na hierarquia lógica.
    """

    def __init__(self, graph: PowerGridGraph, index: BPlusIndex) -> None:
        self.graph = graph
        self.index = index
        self.unsupplied_consumers: Set[str] = set()

    # ------------------------------------------------------------------
    # Atualização de carga a partir de dispositivos
    # ------------------------------------------------------------------

    def update_load_after_device_change(
        self,
        consumer_id: str,
        node_devices: MutableMapping[str, List[IoTDevice]],
    ) -> None:
        """
        Atualiza a carga do consumidor e de toda a sua cadeia lógica
        após uma alteração em dispositivos IoT ligados a esse nó.

        Esta função usa o módulo `load_aggregation` para:

            1. Recalcular a carga do nó consumidor a partir da
               potência instantânea dos dispositivos associados.
            2. Propagar a atualização para subestações de
               distribuição, subestações de transmissão e usinas,
               de acordo com o índice lógico.

        Parâmetros:
            consumer_id:
                Identificador do nó consumidor afetado.
            node_devices:
                Mapeamento de `node_id` para lista de dispositivos
                conectados. A entrada para `consumer_id` será usada
                para recalcular a carga.
        """
        load_aggregation.update_load_after_device_change(
            consumer_id=consumer_id,
            node_devices=node_devices,
            graph=self.graph,
            index=self.index,
        )

        # Se a carga foi recalculada com sucesso, este consumidor
        # pode ser removido do conjunto de não supridos, desde que
        # ainda possua um pai lógico. A decisão sobre reatribuir ou
        # não o pai é tratada em outras operações.
        parent_id = self.index.get_parent(consumer_id)
        if parent_id is not None and consumer_id in self.unsupplied_consumers:
            self.unsupplied_consumers.discard(consumer_id)

    # ------------------------------------------------------------------
    # Capacidade de nós
    # ------------------------------------------------------------------

    def set_node_capacity(self, node_id: str, new_capacity: float) -> None:
        """
        Define a capacidade máxima de um nó em termos de carga
        agregada.

        Esta operação altera apenas o campo `capacity` do nó na
        camada física. Não executa automaticamente reatribuições de
        filhos ou recalculagem de rotas. A lógica de resposta a
        sobrecargas pode ser tratada externamente, por exemplo,
        chamando operações de roteamento quando necessário.

        Parâmetros:
            node_id:
                Identificador do nó cuja capacidade será alterada.
            new_capacity:
                Novo valor de capacidade máxima.
        """
        node = self.graph.get_node(node_id)
        if node is None:
            return
        node.capacity = new_capacity

    # ------------------------------------------------------------------
    # Operações de troca de pai (com e sem roteamento)
    # ------------------------------------------------------------------

    def change_parent_with_routing(self, child_id: str) -> ChangeParentResult:
        """
        Tenta encontrar, via roteamento (Dijkstra/A*), um novo pai
        lógico adequado para `child_id`, respeitando compatibilidade
        de tipos e capacidade do pai.

        Fluxo resumido:

            1. Usa `find_best_parent_for_node` para buscar o candidato
               de menor custo físico.
            2. Verifica se o pai encontrado tem capacidade para
               acomodar a carga do filho.
            3. Se a operação for viável, atualiza o índice lógico,
               recalcula cargas dos pais anterior e novo, e propaga
               para os ancestrais.
            4. Atualiza o conjunto de `unsupplied_consumers` quando
               o nó é consumidor e não encontra pai.

        Parâmetros:
            child_id:
                Identificador do nó cujo pai será recalculado.

        Retorno:
            Instância de `ChangeParentResult` descrevendo o resultado.
        """
        child = self.graph.get_node(child_id)
        if child is None:
            return ChangeParentResult(
                success=False,
                child_id=child_id,
                old_parent_id=None,
                new_parent_id=None,
                total_cost=float("inf"),
                reason="child node not found",
                path=[],
            )

        old_parent_id = self.index.get_parent(child_id)

        # 1) Busca do melhor pai via rota física.
        ps_result: ParentSelectionResult = find_best_parent_for_node(
            graph=self.graph,
            child_id=child_id,
        )

        if ps_result.parent_id is None:
            # Não há pai compatível; marca consumidor como não suprido.
            if child.node_type == NodeType.CONSUMER_POINT:
                self.unsupplied_consumers.add(child_id)

            return ChangeParentResult(
                success=False,
                child_id=child_id,
                old_parent_id=old_parent_id,
                new_parent_id=None,
                total_cost=float("inf"),
                reason="no compatible parent found via routing",
                path=[],
            )

        new_parent_id = ps_result.parent_id
        if old_parent_id == new_parent_id:
            # Nada muda na hierarquia.
            return ChangeParentResult(
                success=True,
                child_id=child_id,
                old_parent_id=old_parent_id,
                new_parent_id=new_parent_id,
                total_cost=ps_result.total_cost,
                reason="parent unchanged (best parent is current parent)",
                path=ps_result.path,
            )

        new_parent = self.graph.get_node(new_parent_id)
        if new_parent is None:
            return ChangeParentResult(
                success=False,
                child_id=child_id,
                old_parent_id=old_parent_id,
                new_parent_id=None,
                total_cost=float("inf"),
                reason="new parent node not found",
                path=ps_result.path,
            )

        # 2) Verificação de capacidade.
        if not _has_capacity_for_child(new_parent, child):
            # Pai encontrado, mas sem capacidade suficiente.
            if child.node_type == NodeType.CONSUMER_POINT:
                self.unsupplied_consumers.add(child_id)

            return ChangeParentResult(
                success=False,
                child_id=child_id,
                old_parent_id=old_parent_id,
                new_parent_id=new_parent_id,
                total_cost=ps_result.total_cost,
                reason="new parent has insufficient capacity",
                path=ps_result.path,
            )

        # 3) Atualiza o índice lógico e recalcula cargas dos pais
        # anterior e novo.
        self.index.set_parent(child_id, new_parent_id)

        # Recalcula carga do pai antigo e do novo pai, propagando
        # para cima em cada cadeia, se eles existirem.
        if old_parent_id is not None:
            load_aggregation.recompute_node_load_from_children(
                node_id=old_parent_id,
                graph=self.graph,
                index=self.index,
            )
            load_aggregation.propagate_load_upwards(
                start_node_id=old_parent_id,
                graph=self.graph,
                index=self.index,
            )

        load_aggregation.recompute_node_load_from_children(
            node_id=new_parent_id,
            graph=self.graph,
            index=self.index,
        )
        load_aggregation.propagate_load_upwards(
            start_node_id=new_parent_id,
            graph=self.graph,
            index=self.index,
        )

        # Consumidores com pai lógico passam a não ser considerados
        # não supridos.
        if child.node_type == NodeType.CONSUMER_POINT:
            self.unsupplied_consumers.discard(child_id)

        return ChangeParentResult(
            success=True,
            child_id=child_id,
            old_parent_id=old_parent_id,
            new_parent_id=new_parent_id,
            total_cost=ps_result.total_cost,
            reason="parent changed via routing",
            path=ps_result.path,
        )

    def force_change_parent(
        self,
        child_id: str,
        new_parent_id: str,
    ) -> ChangeParentResult:
        """
        Força a troca de pai lógico de um nó para um `new_parent_id`
        específico, sem executar roteamento, mas respeitando
        compatibilidade de tipos e capacidade do pai.

        Fluxo:

            1. Verifica existência de filho e novo pai.
            2. Verifica se o tipo do novo pai é permitido para o
               tipo do filho.
            3. Verifica capacidade do novo pai.
            4. Atualiza o índice lógico e recalcula cargas dos pais
               antigo e novo, propagando para os ancestrais.

        Parâmetros:
            child_id:
                Identificador do nó filho.
            new_parent_id:
                Identificador do nó que deve se tornar o novo pai.

        Retorno:
            Instância de `ChangeParentResult` descrevendo o resultado.
        """
        child = self.graph.get_node(child_id)
        new_parent = self.graph.get_node(new_parent_id)

        if child is None:
            return ChangeParentResult(
                success=False,
                child_id=child_id,
                old_parent_id=None,
                new_parent_id=None,
                total_cost=float("inf"),
                reason="child node not found",
                path=[],
            )

        old_parent_id = self.index.get_parent(child_id)

        if new_parent is None:
            return ChangeParentResult(
                success=False,
                child_id=child_id,
                old_parent_id=old_parent_id,
                new_parent_id=None,
                total_cost=float("inf"),
                reason="new parent node not found",
                path=[],
            )

        allowed_types = _allowed_parent_types_for(child.node_type)
        if new_parent.node_type not in allowed_types:
            return ChangeParentResult(
                success=False,
                child_id=child_id,
                old_parent_id=old_parent_id,
                new_parent_id=new_parent_id,
                total_cost=float("inf"),
                reason="incompatible parent type",
                path=[],
            )

        if not _has_capacity_for_child(new_parent, child):
            return ChangeParentResult(
                success=False,
                child_id=child_id,
                old_parent_id=old_parent_id,
                new_parent_id=new_parent_id,
                total_cost=float("inf"),
                reason="new parent has insufficient capacity",
                path=[],
            )

        if old_parent_id == new_parent_id:
            return ChangeParentResult(
                success=True,
                child_id=child_id,
                old_parent_id=old_parent_id,
                new_parent_id=new_parent_id,
                total_cost=0.0,
                reason="parent unchanged (forced parent is current parent)",
                path=[],
            )

        # Atualiza índice lógico.
        self.index.set_parent(child_id, new_parent_id)

        # Recalcula cargas dos pais antigo e novo.
        if old_parent_id is not None:
            load_aggregation.recompute_node_load_from_children(
                node_id=old_parent_id,
                graph=self.graph,
                index=self.index,
            )
            load_aggregation.propagate_load_upwards(
                start_node_id=old_parent_id,
                graph=self.graph,
                index=self.index,
            )

        load_aggregation.recompute_node_load_from_children(
            node_id=new_parent_id,
            graph=self.graph,
            index=self.index,
        )
        load_aggregation.propagate_load_upwards(
            start_node_id=new_parent_id,
            graph=self.graph,
            index=self.index,
        )

        if child.node_type == NodeType.CONSUMER_POINT:
            self.unsupplied_consumers.discard(child_id)

        return ChangeParentResult(
            success=True,
            child_id=child_id,
            old_parent_id=old_parent_id,
            new_parent_id=new_parent_id,
            total_cost=0.0,
            reason="parent changed by force",
            path=[],
        )

    # ------------------------------------------------------------------
    # Inserção de nós com roteamento
    # ------------------------------------------------------------------

    def add_node_with_routing(
        self,
        node: Node,
        edges: Sequence,
    ) -> None:
        """
        Adiciona um novo nó ao grafo físico, conecta as arestas
        informadas e tenta posicionar o nó na hierarquia lógica via
        roteamento.

        Comportamento por tipo:
            - GENERATION_PLANT:
                Inserido no grafo; não recebe pai lógico (raiz).
            - TRANSMISSION_SUBSTATION e DISTRIBUTION_SUBSTATION:
                Inseridos e conectados fisicamente; o serviço tenta
                encontrar um pai lógico compatível via
                `change_parent_with_routing`.
            - CONSUMER_POINT:
                Inserido e conectado; o serviço tenta encontrar
                uma subestação de distribuição como pai. Se não
                houver pai viável, o consumidor é registrado em
                `unsupplied_consumers`.

        Parâmetros:
            node:
                Nó a ser inserido no grafo.
            edges:
                Sequência de arestas físicas a serem adicionadas
                junto com o nó.
        """
        # 1) Adiciona nó e arestas no grafo físico.
        self.graph.add_node(node)
        for edge in edges:
            self.graph.add_edge(edge)

        # 2) Decide se precisa de pai lógico.
        if node.node_type == NodeType.GENERATION_PLANT:
            # Usinas são raízes lógicas por natureza; nenhuma ação
            # adicional é necessária.
            return

        # Para os demais tipos, tentamos achar um pai adequado via roteamento.
        result = self.change_parent_with_routing(child_id=node.id)

        # Se não houver pai viável e o nó for consumidor, garantimos
        # que ele esteja marcado como não suprido.
        if not result.success and node.node_type == NodeType.CONSUMER_POINT:
            self.unsupplied_consumers.add(node.id)

    # ------------------------------------------------------------------
    # Remoção de estações e realocação de filhos
    # ------------------------------------------------------------------

    def remove_station_and_reattach_children(self, station_id: str) -> None:
        """
        Remove uma estação (subestação de transmissão ou de
        distribuição) da hierarquia lógica e tenta realocar seus
        filhos para outras estações compatíveis.

        Fluxo:

            1. Obtém a lista de filhos lógicos da estação.
            2. Para cada filho:
                - desanexa o filho da estação removida;
                - tenta encontrar um novo pai via roteamento;
                - se for consumidor e não houver pai viável, adiciona
                  o filho em `unsupplied_consumers`.
            3. Remove a estação do índice lógico.

        Observação:
            A remoção da estação do grafo físico (nós e arestas)
            deve ser feita externamente, caso desejado, para manter
            a separação entre as camadas lógica e física.
        """
        station = self.graph.get_node(station_id)
        if station is None:
            return

        if station.node_type not in (
            NodeType.TRANSMISSION_SUBSTATION,
            NodeType.DISTRIBUTION_SUBSTATION,
        ):
            # Esta função é específica para remoção de estações.
            return

        children_ids = list(self.index.get_children(station_id))

        # Desanexa filhos e tenta realocá-los.
        for child_id in children_ids:
            self.index.detach_node(child_id)

            child = self.graph.get_node(child_id)
            if child is None:
                continue

            # Tenta encontrar novo pai via roteamento.
            result = self.change_parent_with_routing(child_id=child_id)

            if not result.success and child.node_type == NodeType.CONSUMER_POINT:
                self.unsupplied_consumers.add(child_id)

        # Remove a estação do índice lógico.
        self.index.remove_node(station_id)
