from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set


class BPlusIndex:
    """
    Índice lógico baseado em relações pai-filho para a rede.

    Apesar do nome fazer referência a uma árvore B+, esta classe
    implementa a camada **lógica de hierarquia** (pais e filhos) em
    memória, abstrata em relação à estrutura física de dados usada
    internamente. A ideia é que:

        - Do ponto de vista das outras partes do sistema, existe uma
          API estável para navegar e modificar a árvore lógica.
        - A implementação interna pode ser substituída no futuro por
          uma árvore B+ real (por exemplo, otimizada para disco ou para
          buscas por intervalos), sem alterar o restante do código.

    A hierarquia representada aqui é **estritamente uma floresta**:
        - cada nó tem no máximo um pai lógico;
        - um nó pode ter zero ou mais filhos;
        - nós sem pai são considerados raízes.

    Esta classe **não armazena** os dados dos nós (como tipo, carga,
    etc.). Ela guarda apenas a estrutura da árvore (ids e relações).
    Os dados completos dos nós permanecem no grafo físico
    (`PowerGridGraph`).
    """

    def __init__(self) -> None:
        """
        Cria um índice lógico vazio.

        Estruturas internas:

            - _parent:
                mapeia id de nó → id do pai (ou None, se raiz).
            - _children:
                mapeia id de nó → lista de ids de filhos diretos.

        Não há validação automática de aciclicidade além das regras
        aplicadas nos métodos de alto nível (por exemplo, `move_subtree`
        evita tornar um nó filho de um de seus descendentes).
        """
        self._parent: Dict[str, Optional[str]] = {}
        self._children: Dict[str, List[str]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Consultas básicas
    # ------------------------------------------------------------------

    def get_parent(self, node_id: str) -> Optional[str]:
        """
        Retorna o id do pai lógico de um nó ou None se o nó for raiz
        (ou não existir no índice).

        Parâmetros:
            node_id:
                Identificador do nó.

        Retorno:
            - id do pai, se registrado;
            - None, se o nó for raiz ou não estiver presente.
        """
        return self._parent.get(node_id)

    def get_children(self, node_id: str) -> List[str]:
        """
        Retorna a lista de ids dos filhos diretos de um nó.

        Parâmetros:
            node_id:
                Identificador do nó.

        Retorno:
            Lista de ids de filhos diretos. Se o nó não existir ou não
            tiver filhos, uma lista vazia é retornada.
        """
        return list(self._children.get(node_id, []))

    def get_roots(self) -> List[str]:
        """
        Retorna a lista de ids de todos os nós considerados raízes
        lógicas (nós sem pai).

        Um nó é raiz quando:
            - está presente em `_parent` e seu valor é None; ou
            - aparece apenas como pai na estrutura `_children` e nunca
              foi registrado explicitamente com pai.

        Na prática, como as APIs de modificação sempre registram os nós
        em `_parent`, a primeira condição é a mais comum.
        """
        roots: List[str] = []
        for node_id, parent_id in self._parent.items():
            if parent_id is None:
                roots.append(node_id)
        return roots

    # ------------------------------------------------------------------
    # Operações de construção e modificação simples
    # ------------------------------------------------------------------

    def add_root(self, node_id: str) -> None:
        """
        Garante que um nó exista no índice e seja tratado como raiz.

        Comportamento:
            - Se o nó ainda não existir em `_parent`, ele é criado com
              pai None.
            - Se o nó já existir, seu pai é redefinido para None.
            - A lista de filhos, se já existir, é preservada.

        Este método não altera os relacionamentos dos filhos do nó.
        """
        self._parent[node_id] = None
        # Garante que exista uma entrada para filhos, mesmo que vazia.
        self._children.setdefault(node_id, [])

    def set_parent(self, child_id: str, parent_id: Optional[str]) -> None:
        """
        Define o pai lógico de um nó.

        Comportamento:
            - Se `parent_id` for None, o nó passa a ser tratado como
              raiz.
            - Se houver um pai anterior, o nó é removido da lista de
              filhos desse pai.
            - O nó é adicionado à lista de filhos do novo pai, se
              `parent_id` não for None.
            - Se o nó ou o pai não existirem previamente, são
              registrados no índice.

        Importante:
            - Esta função não verifica a existência de ciclos. É
              responsabilidade das camadas superiores garantir que a
              hierarquia permaneça acíclica.
        """
        old_parent = self._parent.get(child_id)

        # Remove o filho da lista do pai anterior, se houver.
        if old_parent is not None:
            children = self._children.get(old_parent, [])
            if child_id in children:
                children.remove(child_id)

        # Atualiza o pai
        self._parent[child_id] = parent_id
        self._children.setdefault(child_id, [])

        # Se houver novo pai, garante que ele exista e adiciona o filho.
        if parent_id is not None:
            self._children.setdefault(parent_id, [])
            if child_id not in self._children[parent_id]:
                self._children[parent_id].append(child_id)

    # ------------------------------------------------------------------
    # Percurso em pré-ordem
    # ------------------------------------------------------------------

    def iter_preorder(
        self,
        root_ids: Optional[Iterable[str]] = None,
    ) -> List[str]:
        """
        Retorna a lista de ids de nós em ordem de pré-ordem (raiz,
        depois subárvores) de acordo com a hierarquia lógica.

        Parâmetros:
            root_ids:
                Conjunto opcional de ids de nós raiz que devem ser
                usados como ponto de partida do percurso. Se não for
                fornecido, todas as raízes conhecidas do índice
                (`get_roots()`) serão utilizadas.

        Retorno:
            Lista de ids de nós na ordem em que devem ser percorridos.

        Observação:
            - A ordem dos filhos é a ordem em que foram adicionados.
            - Em uma implementação baseada numa árvore B+ real, a ordem
              poderia refletir uma ordenação por chave ou por outro
              critério estável.
        """
        if root_ids is None:
            roots = self.get_roots()
        else:
            roots = list(root_ids)

        result: List[str] = []
        visited: Set[str] = set()

        def _dfs(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            result.append(node_id)
            for child in self._children.get(node_id, []):
                _dfs(child)

        for r in roots:
            _dfs(r)

        return result

    # ------------------------------------------------------------------
    # Operações estruturais: mover, destacar, remover
    # ------------------------------------------------------------------

    def move_subtree(self, subtree_root_id: str, new_parent_id: Optional[str]) -> None:
        """
        Move uma subárvore inteira para ficar sob um novo pai lógico.

        Comportamento:
            - O nó `subtree_root_id` passa a ter `new_parent_id` como
              pai (ou None, se for tornado raiz).
            - Todos os filhos do nó permanecem intactos; apenas a
              conexão do nó com seu pai anterior é modificada.
            - Se `new_parent_id` for None, a subárvore passa a ser
              raiz.

        Importante:
            - A função evita que `new_parent_id` seja um descendente
              da própria subárvore, pois isso criaria um ciclo.
              Nesse caso, nenhuma alteração é feita.
        """
        if subtree_root_id == new_parent_id:
            # Não faz sentido tornar um nó pai de si mesmo.
            return

        if new_parent_id is not None and self._is_descendant(
            ancestor_id=subtree_root_id,
            possible_descendant_id=new_parent_id,
        ):
            # Impedir ciclos na hierarquia.
            return

        self.set_parent(subtree_root_id, new_parent_id)

    def detach_node(self, node_id: str) -> None:
        """
        Destaca um nó do seu pai lógico, tornando-o raiz, sem remover
        a subárvore.

        Comportamento:
            - Se o nó tiver pai, ele é removido da lista de filhos
              desse pai.
            - O campo de pai do nó (`_parent[node_id]`) é definido como
              None.
            - Os filhos do nó não são alterados.

        Se o nó não existir no índice, nenhuma alteração é realizada.
        """
        if node_id not in self._parent:
            return

        current_parent = self._parent[node_id]
        if current_parent is not None:
            children = self._children.get(current_parent, [])
            if node_id in children:
                children.remove(node_id)

        self._parent[node_id] = None

    def remove_node(self, node_id: str) -> None:
        """
        Remove um nó do índice e desconecta sua subárvore.

        Comportamento:
            - O nó é removido da lista de filhos do pai, se houver.
            - O nó é removido de `_parent`.
            - A entrada de filhos em `_children` é removida.
            - Os filhos do nó não são deletados; eles permanecem no
              índice, porém:

                - deixam de ter pai registrado (ou seja, se tornam
                  raízes lógicas) **apenas** se ainda apontarem para o
                  nó removido como pai.

        Esta política é intencional para que camadas superiores possam
        decidir o que fazer com os filhos (por exemplo, reatribuir
        pais via roteamento antes ou depois da remoção).
        """
        # Se o nó não estiver registrado, nada a fazer.
        if node_id not in self._parent and node_id not in self._children:
            return

        # Remove da lista de filhos do pai, se houver.
        parent_id = self._parent.get(node_id)
        if parent_id is not None:
            siblings = self._children.get(parent_id, [])
            if node_id in siblings:
                siblings.remove(node_id)

        # Para todos os nós que apontam para este como pai, zera o pai.
        for child_id, parent in list(self._parent.items()):
            if parent == node_id:
                self._parent[child_id] = None

        # Remove o nó do mapeamento de pai.
        self._parent.pop(node_id, None)
        # Remove também sua lista de filhos.
        self._children.pop(node_id, None)

    # ------------------------------------------------------------------
    # Utilitários internos
    # ------------------------------------------------------------------

    def _is_descendant(self, ancestor_id: str, possible_descendant_id: str) -> bool:
        """
        Verifica se `possible_descendant_id` é um descendente (direto ou
        indireto) de `ancestor_id`.

        Esta função é usada para evitar ciclos ao mover subárvores.
        """
        stack: List[str] = [ancestor_id]
        visited: Set[str] = set()

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            for child in self._children.get(current, []):
                if child == possible_descendant_id:
                    return True
                stack.append(child)

        return False
