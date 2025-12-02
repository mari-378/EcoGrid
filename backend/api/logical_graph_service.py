from __future__ import annotations

from dataclasses import dataclass
from typing import List, MutableMapping, Optional, Sequence, Set

from core.graph_core import PowerGridGraph, Edge
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex
from logic.parent_selection import (
    ParentSelectionResult,
    find_best_parent_for_node,
)
from logic import load_aggregation
from physical.device_model import IoTDevice


@dataclass
class ChangeParentResult:
    """
    Resultado de uma operação de troca de pai lógico na árvore B+.

    Atributos:
        success:
            Indica se a operação foi aplicada com sucesso.
        child_id:
            Identificador do nó cujo pai foi alterado (ou tentado
            alterar).
        old_parent_id:
            Pai anterior do nó, quando existia.
        new_parent_id:
            Novo pai do nó, quando a operação é bem-sucedida.
        total_cost:
            Custo acumulado do caminho físico entre o nó e o novo pai,
            de acordo com a função de custo usada pelo roteamento.
        reason:
            Texto curto explicando o motivo em caso de falha, ou
            descrevendo o cenário em caso de sucesso.
        path:
            Caminho físico (lista de ids de nós) do filho até o novo pai.
            Pode ser vazio se o caminho não puder ser reconstruído.
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

    Regras usadas:

        - CONSUMER_POINT:
            Pai deve ser DISTRIBUTION_SUBSTATION.
        - DISTRIBUTION_SUBSTATION:
            Pai deve ser TRANSMISSION_SUBSTATION.
        - TRANSMISSION_SUBSTATION:
            Pai deve ser GENERATION_PLANT.
        - GENERATION_PLANT:
            Não possui pai lógico.

    Parâmetros:
        child_type:
            Tipo do nó filho.

    Retorno:
        Conjunto de tipos possíveis de pai. Pode ser vazio se o tipo
        não admitir pai lógico.
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
    Verifica se o nó pai possui capacidade disponível para acomodar
    a carga do filho, considerando a carga atual do pai.

    Política:

        - Se `parent.capacity` for None, o pai é tratado como sem
          limite explícito de capacidade (sempre retorna True).
        - `child.current_load` None é tratado como 0.0.
        - `parent.current_load` None é tratado como 0.0.
        - A operação é considerada válida se:

              parent.current_load + child.current_load <= parent.capacity

    Parâmetros:
        parent:
            Nó candidato a pai.
        child:
            Nó filho cuja carga será adicionada ao pai.

    Retorno:
        True se o pai tiver capacidade suficiente; False em caso contrário.
    """
    if parent.capacity is None:
        return True

    parent_load = float(parent.current_load or 0.0)
    child_load = float(child.current_load or 0.0)

    return (parent_load + child_load) <= float(parent.capacity)


class LogicalGraphService:
    """
    Serviço que encapsula a lógica de alto nível da árvore B+, operando
    sobre o grafo físico.

    Responsabilidades principais:

        - Manter um índice B+ (`BPlusIndex`) com relações pai-filho
          entre os nós físicos.
        - Selecionar pais lógicos usando o grafo físico e o algoritmo
          de caminho mínimo (A* / Dijkstra).
        - Respeitar limitações de capacidade de nós (campo `capacity`).
        - Propagar cargas (`current_load`) ao longo da cadeia de pais
          sempre que um nó consumidor ou subestação tiver mudança de
          carga.
        - Manter a lista de consumidores sem energia adequada
          (`unsupplied_consumers`), quando não há pai viável.

    Atributos:
        graph:
            Grafo físico da rede.
        index:
            Índice B+ com as relações pai-filho.
        unsupplied_consumers:
            Conjunto de ids de nós consumidores que, no momento, não
            têm pai lógico viável.
    """

    def __init__(self, graph: PowerGridGraph, index: BPlusIndex) -> None:
        self.graph = graph
        self.index = index
        self.unsupplied_consumers: Set[str] = set()

    # ------------------------------------------------------------------
    # Operações de carga / dispositivos
    # ------------------------------------------------------------------

    def update_load_after_device_change(
        self,
        consumer_id: str,
        node_devices: MutableMapping[str, Sequence[IoTDevice]],
    ) -> None:
        """
        Atualiza a carga de um nó consumidor e de toda a sua cadeia de
        pais após uma alteração em dispositivos IoT conectados a ele.

        Fluxo:

            1. Usa `load_aggregation.update_load_after_device_change`
               para:
                   - recalcular `current_load` do consumidor somando
                     `current_power` dos dispositivos associados;
                   - propagar a nova carga para cima na hierarquia B+.

            2. Se o consumidor possuir pai lógico, remove o seu id de
               `unsupplied_consumers` (caso estivesse marcado como sem
               energia).

        Parâmetros:
            consumer_id:
                Id do nó consumidor afetado.
            node_devices:
                Mapeamento de ids de nó para listas de `IoTDevice`
                conectados. Apenas a entrada para `consumer_id` é
                utilizada nesta chamada.
        """
        load_aggregation.update_load_after_device_change(
            consumer_id=consumer_id,
            node_devices=node_devices,
            graph=self.graph,
            index=self.index,
        )

        parent_id = self.index.get_parent(consumer_id)
        if parent_id is not None:
            self.unsupplied_consumers.discard(consumer_id)

    def set_node_capacity(self, node_id: str, new_capacity: float) -> None:
        """
        Ajusta a capacidade máxima (`capacity`) de um nó.

        Esta operação altera apenas o campo `capacity` na camada física.
        Qualquer política adicional de reação à mudança de capacidade
        (por exemplo, tentar redistribuir filhos em caso de sobrecarga)
        deve ser tratada por chamadas adicionais de roteamento em nível
        superior.

        Parâmetros:
            node_id:
                Identificador do nó a ser ajustado.
            new_capacity:
                Nova capacidade máxima do nó.
        """
        node = self.graph.get_node(node_id)
        if node is None:
            return
        node.capacity = new_capacity

    # ------------------------------------------------------------------
    # Troca de pai com roteamento
    # ------------------------------------------------------------------

    def change_parent_with_routing(self, child_id: str) -> ChangeParentResult:
        """
        Tenta encontrar um novo pai lógico para `child_id` usando o
        grafo físico e o algoritmo de caminho mínimo (Dijkstra/A*).

        Regras:

            - O tipo do pai deve ser compatível com o tipo do filho,
              conforme `_allowed_parent_types_for`.
            - O pai deve ter capacidade suficiente para acomodar a
              carga do filho, conforme `_has_capacity_for_child`.
            - Em caso de sucesso, atualiza o índice B+ e recalcula a
              carga dos pais antigo e novo, propagando para cima.

        Em caso de falha (nenhum pai viável encontrado), o pai lógico
        atual é mantido e, se o nó for consumidor, seu id é adicionado
        a `unsupplied_consumers`.

        Parâmetros:
            child_id:
                Id do nó cujo pai será recalculado.

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

        # 1) Busca do melhor pai via roteamento físico.
        ps_result: ParentSelectionResult = find_best_parent_for_node(
            graph=self.graph,
            child_id=child_id,
        )

        if ps_result.parent_id is None:
            # Sem pai compatível; marca consumidor como não suprido.
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
            # Pai já é o melhor candidato; nada muda na estrutura.
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

        # 2) Verificação de capacidade do novo pai.
        if not _has_capacity_for_child(new_parent, child):
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

        # 3) Atualiza o índice lógico (B+) e recalcula as cargas.
        self.index.set_parent(child_id, new_parent_id)

        # Recalcula cargas do pai antigo e do novo pai, se houver.
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
        Força a troca de pai lógico de um nó para um pai específico,
        sem usar o algoritmo de roteamento, mas ainda respeitando
        compatibilidade de tipos e capacidade do pai.

        Fluxo:

            1. Verifica existência de filho e novo pai.
            2. Verifica se o tipo do novo pai é permitido para o tipo
               do filho.
            3. Verifica capacidade do novo pai.
            4. Atualiza o índice B+ e recalcula cargas do pai antigo e
               do novo pai, propagando para cima.

        Parâmetros:
            child_id:
                Id do nó filho.
            new_parent_id:
                Id do nó que deve se tornar o novo pai.

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

        # Atualiza índice B+.
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
        edges: Sequence[Edge],
    ) -> None:
        """
        Insere um novo nó no grafo físico e tenta posicioná-lo na
        árvore lógica usando roteamento.

        Comportamento por tipo de nó:

            - GENERATION_PLANT:
                Inserido apenas no grafo físico. Não recebe pai lógico
                (considerado raiz na árvore).

            - TRANSMISSION_SUBSTATION e DISTRIBUTION_SUBSTATION:
                Inseridos no grafo físico com suas arestas, e é feita
                uma chamada a `change_parent_with_routing` para buscar
                um pai lógico adequado (usina ou subestação acima).

            - CONSUMER_POINT:
                Inserido no grafo físico com suas arestas, e é feita
                uma chamada a `change_parent_with_routing` para buscar
                uma subestação de distribuição como pai. Se não houver
                pai viável, o consumidor é marcado em
                `unsupplied_consumers`.

        Parâmetros:
            node:
                Nó físico a ser inserido.
            edges:
                Arestas físicas que conectam o nó à rede existente.
        """
        # 1) Insere nó e arestas no grafo físico.
        self.graph.add_node(node)
        for edge in edges:
            self.graph.add_edge(edge)

        # 2) Decide ação em função do tipo de nó.
        if node.node_type == NodeType.GENERATION_PLANT:
            # Usinas são raízes lógicas; não tentamos encontrar pai.
            return

        # Para demais tipos, tentamos calcular pai lógico via roteamento.
        result = self.change_parent_with_routing(child_id=node.id)

        if (not result.success) and node.node_type == NodeType.CONSUMER_POINT:
            self.unsupplied_consumers.add(node.id)

    # ------------------------------------------------------------------
    # Remoção de estações e realocação de filhos
    # ------------------------------------------------------------------

    def remove_station_and_reattach_children(
        self,
        station_id: str,
        remove_from_graph: bool = True,
    ) -> None:
        """
        Remove uma estação (subestação de transmissão ou distribuição)
        da árvore lógica e tenta realocar seus filhos para outras
        estações compatíveis via roteamento.

        Fluxo:

            1. Obtém a lista de filhos lógicos da estação no índice B+.
            2. Para cada filho:
                   - desanexa o filho da estação removida;
                   - tenta encontrar um novo pai com
                     `change_parent_with_routing`;
                   - se o filho for consumidor e não houver pai viável,
                     adiciona-o a `unsupplied_consumers`.
            3. Remove a estação do índice B+.
            4. Opcionalmente (`remove_from_graph=True`), remove a
               estação do grafo físico.

        Observação:

            - Neste modelo, a remoção física (grafo) ocorre após a
              realocação lógica. Assim, o algoritmo de roteamento ainda
              enxerga a estação durante a busca de novos pais. Se for
              necessário modelar falhas físicas mais rígidas (sem
              permitir que rotas passem temporariamente pela estação
              removida), a política poderá ser refinada em versões
              futuras.

        Parâmetros:
            station_id:
                Id da estação a ser removida.
            remove_from_graph:
                Se True, também remove o nó e suas arestas do grafo
                físico após o ajuste lógico.
        """
        station = self.graph.get_node(station_id)
        if station is None:
            return

        if station.node_type not in (
            NodeType.TRANSMISSION_SUBSTATION,
            NodeType.DISTRIBUTION_SUBSTATION,
        ):
            # Esta rotina é específica para remoção de estações.
            return

        children_ids = list(self.index.get_children(station_id))

        # Desanexa filhos e tenta realocá-los.
        for child_id in children_ids:
            self.index.detach_node(child_id)

            child = self.graph.get_node(child_id)
            if child is None:
                continue

            result = self.change_parent_with_routing(child_id=child_id)

            if (not result.success) and child.node_type == NodeType.CONSUMER_POINT:
                self.unsupplied_consumers.add(child_id)

        # Remove a estação do índice lógico.
        self.index.detach_node(station_id)
        self.index.remove_node(station_id)

        # Opcionalmente, remove do grafo físico.
        if remove_from_graph:
            self.graph.remove_node(station_id)


__all__ = [
    "LogicalGraphService",
    "ChangeParentResult",
]
