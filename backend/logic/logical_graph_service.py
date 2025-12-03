from __future__ import annotations

from dataclasses import dataclass
import random
from typing import List, Optional, MutableMapping, Sequence, Set

from core.graph_core import PowerGridGraph
from core.models import Node, Edge, NodeType
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
        self.log_buffer: List[str] = []

    def log(self, message: str) -> None:
        self.log_buffer.append(message)

    def consume_logs(self) -> List[str]:
        logs = list(self.log_buffer)
        self.log_buffer.clear()
        return logs

    def check_system_health(self) -> None:
        """
        Executa verificações proativas de saúde da rede:
        1. Percorre todos os nós para verificar se seu pai está sobrecarregado.
           Se estiver, o nó desconecta (simulando perda de conexão por instabilidade).
        2. Tenta reconectar nós órfãos (consumidores e subestações sem pai).
        """
        # 1. Verificação de sobrecarga do pai ("Collector" logic)
        # Iteramos uma cópia para permitir modificações
        all_nodes = list(self.graph.nodes.keys())
        overload_detach_count = 0

        for node_id in all_nodes:
            parent_id = self.index.get_parent(node_id)
            if not parent_id:
                continue

            parent = self.graph.get_node(parent_id)
            if not parent or parent.capacity is None or parent.current_load is None:
                continue

            # Se o pai está sobrecarregado, o filho perde a conexão
            if parent.current_load > parent.capacity:
                self.index.detach_node(node_id)
                node = self.graph.get_node(node_id)
                if node and node.node_type == NodeType.CONSUMER_POINT:
                    self.unsupplied_consumers.add(node_id)

                overload_detach_count += 1
                self.log(f"Instabilidade: Nó {node_id} perdeu conexão com {parent_id} devido a sobrecarga no fornecedor.")

                # Atualiza carga do pai (que reduziu)
                load_aggregation.recompute_node_load_from_children(parent_id, self.graph, self.index)
                load_aggregation.propagate_load_upwards(parent_id, self.graph, self.index)

        if overload_detach_count > 0:
            self.log(f"Saúde da rede: {overload_detach_count} nós desconectados preventivamente devido a sobrecarga de fornecedores.")

        # 2. Tentativa de recuperação
        self.retry_unsupplied_routing()

    def retry_unsupplied_routing(self) -> None:
        """
        Tenta encontrar pai para TODOS os nós sem fornecedor, garantindo
        coleta abrangente de órfãos (consumidores, distribuição, transmissão).

        A estratégia segue uma ordem hierárquica (Transmission -> Distribution -> Consumer)
        para maximizar a chance de reconectar "ilhas" inteiras corretamente.
        """
        count = 0

        # Identifica todos os nós que deveriam ter pai mas não têm (estão como raízes ou fora da B+)
        # Nós válidos para roteamento são aqueles que NÃO são GENERATION_PLANT
        orphans = []

        # 1. Varre todo o grafo para encontrar quem está sem pai lógico
        for node_id, node in self.graph.nodes.items():
            if node.node_type == NodeType.GENERATION_PLANT:
                continue

            parent_id = self.index.get_parent(node_id)
            if parent_id is None:
                # É um órfão (raiz lógica não-Usina ou desconectado)
                orphans.append(node)

        # 2. Ordena por prioridade hierárquica para tentar consertar o "backbone" primeiro
        def routing_priority(n: Node) -> int:
            if n.node_type == NodeType.TRANSMISSION_SUBSTATION:
                return 1
            if n.node_type == NodeType.DISTRIBUTION_SUBSTATION:
                return 2
            if n.node_type == NodeType.CONSUMER_POINT:
                return 3
            return 99

        orphans.sort(key=routing_priority)

        # 3. Tenta reconectar cada órfão
        for node in orphans:
            result = self.change_parent_with_routing(child_id=node.id)
            if result.success:
                count += 1
                # Se for consumidor, remove da lista de não-supridos
                if node.node_type == NodeType.CONSUMER_POINT:
                    self.unsupplied_consumers.discard(node.id)
            else:
                # Se falhar e for consumidor, garante que está na lista
                if node.node_type == NodeType.CONSUMER_POINT:
                    self.unsupplied_consumers.add(node.id)

        if count > 0:
            self.log(f"Recuperação estrutural: {count} nós (consumidores ou subestações) foram reconectados à rede com sucesso.")

    def handle_overload(self, node_id: str) -> None:
        """
        Verifica sobrecarga e realiza load shedding (corte de carga) se necessário.
        Se a carga atual exceder a capacidade, desconecta filhos aleatórios até
        que a situação se regularize.
        """
        node = self.graph.get_node(node_id)
        if node is None or node.capacity is None or node.current_load is None:
            return

        if node.current_load <= node.capacity:
            return

        self.log(f"ALERTA DE SOBRECARGA: {node_id} (Carga: {node.current_load:.2f}kW > Cap: {node.capacity:.2f}kW). Iniciando corte de carga.")

        children = self.index.get_children(node_id)
        # Embaralha para desconectar aleatoriamente
        random.shuffle(children)

        for child_id in children:
            if node.current_load <= node.capacity:
                break

            child = self.graph.get_node(child_id)
            if not child: continue

            # Desconecta o filho (torna-se raiz temporariamente)
            self.index.detach_node(child_id)
            # detach_node já remove da lista de filhos do pai

            # Se for consumidor, registra como não suprido
            if child.node_type == NodeType.CONSUMER_POINT:
                self.unsupplied_consumers.add(child_id)

            self.log(f"Corte de carga: Nó {child_id} desconectado de {node_id} para alívio do sistema.")

            # Recalcula a carga do nó pai (agora menor)
            load_aggregation.recompute_node_load_from_children(node_id, self.graph, self.index)
            # Propaga a redução para cima (opcional, mas bom para consistência)
            load_aggregation.propagate_load_upwards(node_id, self.graph, self.index)

        if node.current_load > node.capacity:
            self.log(f"ALERTA CRÍTICO: {node_id} permanece sobrecarregado ({node.current_load:.2f}kW) mesmo após corte de todos os filhos.")

    # ------------------------------------------------------------------
    # Hidratação do estado lógico (Correção 1.1)
    # ------------------------------------------------------------------

    def hydrate_from_physical(self) -> None:
        """
        Reconstrói o estado lógico (árvore B+ e estados de suprimento)
        a partir da topologia física atual do grafo.

        Estratégia:
            1. Define todas as usinas (GENERATION_PLANT) como raízes.
            2. Itera sobre os demais nós em ordem hierárquica
               (Transmissão -> Distribuição -> Consumo).
            3. Para cada nó, executa `change_parent_with_routing` para
               tentar encontrar o melhor pai lógico disponível.
            4. Se um nó não encontrar pai, ele permanece desconectado
               (ou raiz isolada) e, se for consumidor, é marcado como
               não suprido.
        """
        # 1. Identifica e adiciona raízes (Usinas)
        for node in self.graph.nodes.values():
            if node.node_type == NodeType.GENERATION_PLANT:
                self.index.add_root(node.id)

        # 2. Prepara lista de nós a serem conectados via roteamento
        nodes_to_process = []
        for node in self.graph.nodes.values():
            if node.node_type == NodeType.GENERATION_PLANT:
                continue
            nodes_to_process.append(node)

        # Ordena por prioridade hierárquica
        def priority(n: Node) -> int:
            if n.node_type == NodeType.TRANSMISSION_SUBSTATION:
                return 1
            if n.node_type == NodeType.DISTRIBUTION_SUBSTATION:
                return 2
            if n.node_type == NodeType.CONSUMER_POINT:
                return 3
            return 99

        nodes_to_process.sort(key=priority)

        # 3. Executa roteamento para cada nó
        for node in nodes_to_process:
            self.change_parent_with_routing(child_id=node.id)

        # Log de inicialização
        ts_count = sum(1 for n in self.graph.nodes.values() if n.node_type == NodeType.TRANSMISSION_SUBSTATION)
        ds_count = sum(1 for n in self.graph.nodes.values() if n.node_type == NodeType.DISTRIBUTION_SUBSTATION)
        self.log(f"Rede ligada e inicializada com sucesso. {ts_count} Subestações de Transmissão e {ds_count} Subestações de Distribuição conectadas aos seus fornecedores.")

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

        current_load = float(self.graph.get_node(consumer_id).current_load or 0.0)
        self.log(f"Carga do consumidor {consumer_id} atualizada para {current_load:.2f}kW devido a alterações nos dispositivos.")

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

    def force_overload(self, node_id: str, overload_percentage: float) -> bool:
        """
        Força o status de sobrecarga em um nó interno (não-dispositivo)
        reduzindo sua capacidade para um valor abaixo da carga atual.

        Fórmula aplicada:
            new_capacity = current_load / (1 + overload_percentage)

        Exemplo:
            Se current_load = 100 e overload_percentage = 0.2 (20%),
            new_capacity = 100 / 1.2 = 83.33
            Assim, current_load (100) > capacity (83.33) -> Overload.

        Restrições:
            - Aplica-se apenas a nós com filhos (Subestações e Usinas).
            - Não se aplica a nós do tipo CONSUMER_POINT (dispositivos).
            - Se o nó não tiver carga atual (current_load is None/0),
              a capacidade será definida como 0.0 (se possível).

        Parâmetros:
            node_id:
                Identificador do nó alvo.
            overload_percentage:
                Percentual de sobrecarga desejado (ex: 0.2 para 20%).

        Retorno:
            True se a operação foi aplicada; False se o nó não foi
            encontrado ou se o tipo não for permitido.
        """
        node = self.graph.get_node(node_id)
        if node is None:
            return False

        # Restrição: apenas nós internos (Usinas, Transmissão, Distribuição).
        # Exclui explicitamente consumidores (que contêm dispositivos).
        if node.node_type == NodeType.CONSUMER_POINT:
            return False

        current_load = node.current_load or 0.0

        # Evita divisão por zero ou negativa se porcentagem for <= -1
        divisor = 1.0 + overload_percentage
        if divisor <= 0.001:
            divisor = 0.001

        new_capacity = current_load / divisor

        # Atualiza a capacidade do nó
        node.capacity = new_capacity

        self.log(f"ALERTA: Fornecedor {node_id} teve sua capacidade limitada a {new_capacity:.2f}kW. Iniciando redistribuição de carga.")

        return True

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

            # (DEBUG removido para evitar poluição, ou mantido se útil)
            # print(f"[DEBUG] Failed to find parent via routing for {child_id}...")

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

        self.log(f"Nó {child_id} trocou de fornecedor: saiu de {old_parent_id} para {new_parent_id}.")

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

        self.log(f"Nó {child_id} trocou de fornecedor: saiu de {old_parent_id} para {new_parent_id}.")

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

        if result.success:
            self.log(f"Nó {node.id} ({node.node_type.name}) foi conectado ao fornecedor {result.new_parent_id}.")
        else:
            self.log(f"Nó {node.id} foi adicionado, mas não encontrou um fornecedor compatível e está sem energia.")

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

            if not result.success:
                # Se falhar em encontrar pai:
                # - Se for consumidor, marca como não suprido.
                if child.node_type == NodeType.CONSUMER_POINT:
                    self.unsupplied_consumers.add(child_id)
                # (Correção 1.3: Subestações fantasmas podem ser tratadas aqui se desejado,
                # mas elas se tornam raízes. O método _compute_status na UI deve verificar
                # se a raiz é uma usina para determinar status UNSUPPLIED recursivo.)

        # Remove a estação do índice lógico.
        self.index.remove_node(station_id)
