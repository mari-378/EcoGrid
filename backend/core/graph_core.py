from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .models import Edge, Node


@dataclass
class NeighborInfo:
    """
    Informação de vizinhança de um nó no grafo.

    Esta estrutura é utilizada para retornar vizinhos de um nó de forma
    conveniente, incluindo tanto o identificador do nó vizinho quanto a
    aresta que realiza a conexão.

    Atributos:
        neighbor_id:
            Identificador do nó vizinho conectado.
        edge:
            Aresta que conecta o nó original ao nó vizinho.
    """

    neighbor_id: str
    edge: Edge


class PowerGridGraph:
    """
    Grafo físico da rede elétrica.

    Esta classe mantém os nós e arestas que compõem a rede elétrica
    simulada em uma estrutura de grafo. O objetivo é oferecer operações
    básicas para:

    - adicionar e remover nós;
    - adicionar e remover arestas;
    - consultar nós e arestas;
    - obter vizinhos de um nó;
    - iterar sobre todos os elementos do grafo.

    O grafo é armazenado com:

    - um dicionário de nós (`nodes`), indexado por `node.id`;
    - um dicionário de arestas (`edges`), indexado por `edge.id`;
    - uma lista de adjacência (`adjacency`), que mapeia `node_id` para o
      conjunto de `edge.id` incidentes naquele nó.

    Esta estrutura serve de base para as etapas de planejamento da rede
    (transmissão, MV, LV, robustez) e para exportação dos dados em CSV.
    """

    def __init__(self) -> None:
        """
        Inicializa um grafo vazio, sem nós nem arestas.

        A estrutura interna é composta por três dicionários:

        - `nodes`: armazena instâncias de `Node` indexadas por `node.id`;
        - `edges`: armazena instâncias de `Edge` indexadas por `edge.id`;
        - `adjacency`: mapeia cada `node_id` para um conjunto de `edge.id`
          que incidem naquele nó.

        Todos os dicionários são inicialmente vazios.
        """
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        self.adjacency: Dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Operações sobre nós
    # ------------------------------------------------------------------

    def add_node(self, node: Node) -> None:
        """
        Adiciona um nó ao grafo.

        Se já existir um nó com o mesmo identificador, ele será substituído.
        A lista de adjacência para o nó é criada caso ainda não exista.

        Parâmetros:
            node:
                Instância de `Node` a ser adicionada ao grafo. O campo
                `node.id` é usado como chave no dicionário interno.

        Efeitos colaterais:
            - Atualiza `self.nodes[node.id]` com o nó fornecido.
            - Garante a existência de `self.adjacency[node.id]` como um
              conjunto vazio, caso ainda não exista.
        """
        self.nodes[node.id] = node
        if node.id not in self.adjacency:
            self.adjacency[node.id] = set()

    def get_node(self, node_id: str) -> Optional[Node]:
        """
        Recupera um nó pelo seu identificador.

        Parâmetros:
            node_id:
                Identificador do nó buscado.

        Retorno:
            - Instância de `Node` correspondente a `node_id`, se existir.
            - `None` se não houver nó cadastrado com esse identificador.
        """
        return self.nodes.get(node_id)

    def remove_node(self, node_id: str) -> None:
        """
        Remove um nó do grafo, juntamente com todas as arestas incidentes.

        Parâmetros:
            node_id:
                Identificador do nó a ser removido.

        Comportamento:
            - Se o nó não existir, a função não faz nada.
            - Se o nó existir:
                - todas as arestas incidentes são removidas;
                - o nó é removido de `self.nodes`;
                - a entrada correspondente em `self.adjacency` é apagada.

        Complexidade:
            A remoção é proporcional ao grau do nó, pois todas as arestas
            incidentes precisam ser removidas da estrutura interna.
        """
        if node_id not in self.nodes:
            return

        # Copia a lista de arestas incidentes para evitar modificar o conjunto
        # enquanto iteramos sobre ele.
        incident_edges = list(self.adjacency.get(node_id, set()))

        for edge_id in incident_edges:
            self.remove_edge(edge_id)

        # Remove o nó e sua lista de adjacência.
        self.nodes.pop(node_id, None)
        self.adjacency.pop(node_id, None)

    def iter_nodes(self) -> Iterable[Node]:
        """
        Itera sobre todos os nós do grafo.

        Retorno:
            Um iterador sobre as instâncias de `Node` armazenadas em
            `self.nodes`. A ordem de iteração segue a ordem do dicionário
            interno, que costuma refletir a ordem de inserção em versões
            recentes do Python.
        """
        return self.nodes.values()

    # ------------------------------------------------------------------
    # Operações sobre arestas
    # ------------------------------------------------------------------

    def add_edge(self, edge: Edge) -> None:
        """
        Adiciona uma aresta ao grafo.

        A aresta deve referenciar nós já existentes por meio de
        `edge.from_node_id` e `edge.to_node_id`. Se algum dos nós não
        existir, uma exceção `KeyError` é lançada.

        Parâmetros:
            edge:
                Instância de `Edge` a ser adicionada ao grafo. O campo
                `edge.id` é usado como chave no dicionário interno.

        Efeitos colaterais:
            - Atualiza `self.edges[edge.id]` com a aresta fornecida.
            - Adiciona `edge.id` aos conjuntos de adjacência de
              `from_node_id` e `to_node_id`.

        Exceções:
            KeyError:
                Lançada se `edge.from_node_id` ou `edge.to_node_id` não
                existirem em `self.nodes`.
        """
        if edge.from_node_id not in self.nodes:
            raise KeyError(f"from_node_id '{edge.from_node_id}' não encontrado no grafo")
        if edge.to_node_id not in self.nodes:
            raise KeyError(f"to_node_id '{edge.to_node_id}' não encontrado no grafo")

        self.edges[edge.id] = edge

        if edge.from_node_id not in self.adjacency:
            self.adjacency[edge.from_node_id] = set()
        if edge.to_node_id not in self.adjacency:
            self.adjacency[edge.to_node_id] = set()

        self.adjacency[edge.from_node_id].add(edge.id)
        self.adjacency[edge.to_node_id].add(edge.id)

    def get_edge(self, edge_id: str) -> Optional[Edge]:
        """
        Recupera uma aresta pelo seu identificador.

        Parâmetros:
            edge_id:
                Identificador da aresta buscada.

        Retorno:
            - Instância de `Edge` correspondente a `edge_id`, se existir.
            - `None` se não houver aresta cadastrada com esse identificador.
        """
        return self.edges.get(edge_id)

    def remove_edge(self, edge_id: str) -> None:
        """
        Remove uma aresta do grafo.

        A remoção atualiza tanto o dicionário de arestas quanto as listas
        de adjacência dos nós de origem e destino.

        Parâmetros:
            edge_id:
                Identificador da aresta a ser removida.

        Comportamento:
            - Se a aresta não existir, a função não faz nada.
            - Se existir:
                - a aresta é removida de `self.edges`;
                - o identificador é removido dos conjuntos em
                  `self.adjacency[from_node_id]` e `self.adjacency[to_node_id]`,
                  caso esses nós ainda existam.
        """
        edge = self.edges.pop(edge_id, None)
        if edge is None:
            return

        if edge.from_node_id in self.adjacency:
            self.adjacency[edge.from_node_id].discard(edge.id)
        if edge.to_node_id in self.adjacency:
            self.adjacency[edge.to_node_id].discard(edge.id)

    def iter_edges(self) -> Iterable[Edge]:
        """
        Itera sobre todas as arestas do grafo.

        Retorno:
            Um iterador sobre as instâncias de `Edge` armazenadas em
            `self.edges`. A ordem de iteração segue a ordem do dicionário
            interno.
        """
        return self.edges.values()

    # ------------------------------------------------------------------
    # Consultas de vizinhança
    # ------------------------------------------------------------------

    def neighbors(self, node_id: str) -> List[NeighborInfo]:
        """
        Retorna a lista de vizinhos de um nó.

        Cada vizinho é representado por uma instância de `NeighborInfo`,
        que contém:

        - o identificador do nó vizinho;
        - a aresta que conecta os dois nós.

        Parâmetros:
            node_id:
                Identificador do nó cujos vizinhos se deseja obter.

        Retorno:
            Lista de `NeighborInfo` descrevendo todos os nós diretamente
            conectados ao nó informado. Se o nó não existir ou não tiver
            arestas incidentes, a lista retornada será vazia.
        """
        if node_id not in self.adjacency:
            return []

        result: List[NeighborInfo] = []
        for edge_id in self.adjacency[node_id]:
            edge = self.edges.get(edge_id)
            if edge is None:
                continue
            if edge.from_node_id == node_id:
                neighbor_id = edge.to_node_id
            else:
                neighbor_id = edge.from_node_id

            result.append(NeighborInfo(neighbor_id=neighbor_id, edge=edge))

        return result

    def degree(self, node_id: str) -> int:
        """
        Retorna o grau de um nó no grafo.

        O grau é definido como o número de arestas incidentes ao nó,
        contando conexões de transmissão, MV e LV igualmente.

        Parâmetros:
            node_id:
                Identificador do nó cujo grau se deseja obter.

        Retorno:
            Número de arestas incidentes ao nó. Se o nó não existir ou não
            possuir entrada em `adjacency`, o grau retornado será zero.
        """
        return len(self.adjacency.get(node_id, set()))


__all__: Sequence[str] = ["NeighborInfo", "PowerGridGraph"]
