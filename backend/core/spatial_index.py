from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class _PointRecord:
    """
    Registro interno de um ponto indexado.

    Esta estrutura é usada apenas dentro do índice espacial para armazenar
    o identificador lógico do ponto e suas coordenadas cartesianas. Ela
    não substitui a classe `Node` do grafo, apenas evita dependência
    direta do módulo `core.models` e mantém o índice genérico.
    """

    item_id: str
    x: float
    y: float


class SpatialIndex:
    """
    Índice espacial simples em memória para consultas de vizinhança 2D.

    Esta classe oferece uma interface básica para localizar elementos em
    uma região bidimensional com base em coordenadas cartesianas (x, y).
    Ela é usada pelas etapas de planejamento da rede para encontrar nós
    próximos (por exemplo, subestações de transmissão próximas entre si
    ou pontos consumidores próximos de subestações de distribuição).

    Implementação atual:
        A implementação é propositalmente simples e baseada em busca
        linear: todos os pontos armazenados são percorridos a cada
        consulta. Isso garante corretude e facilita a leitura e a
        manutenção do código. Em cenários com um número muito grande de
        nós, pode ser desejável substituir esta implementação por uma
        estrutura mais avançada (como kd-tree ou grade espacial). Essa
        troca pode ser feita evoluindo este módulo sem impactar o código
        das demais etapas, desde que a interface pública seja mantida.

    Uso típico:
        1. Criar uma instância de `SpatialIndex`.
        2. Inserir todos os pontos com `insert(item_id, x, y)`.
        3. Chamar `build()` (no momento é um no-op, mas preservado para
           compatibilidade futura).
        4. Utilizar `k_nearest` ou `radius_search` para encontrar
           vizinhos.

    As distâncias retornadas são euclidianas e calculadas diretamente
    sobre as coordenadas fornecidas na inserção, sem qualquer tipo de
    projeção ou normalização adicional.
    """

    def __init__(self) -> None:
        """
        Inicializa um índice espacial vazio.

        Nenhum ponto é cadastrado neste momento. Os pontos devem ser
        inseridos via `insert` antes de qualquer consulta. O método
        `build` pode ser chamado após todas as inserções para permitir
        implementações futuras que exijam uma fase de construção
        explícita.
        """
        self._points: Dict[str, _PointRecord] = {}

    # ------------------------------------------------------------------
    # Operações básicas
    # ------------------------------------------------------------------

    def insert(self, item_id: str, x: float, y: float) -> None:
        """
        Insere ou atualiza um ponto no índice espacial.

        Se já existir um ponto com o mesmo identificador, suas
        coordenadas são sobrescritas. Não há limite de quantidade de
        pontos, além da memória disponível.

        Args:
            item_id:
                Identificador lógico do ponto. Normalmente corresponde
                ao `id` de um nó do grafo ou a outro identificador
                estável usado nas etapas de planejamento.
            x:
                Coordenada cartesiana X do ponto.
            y:
                Coordenada cartesiana Y do ponto.
        """
        self._points[item_id] = _PointRecord(item_id=item_id, x=x, y=y)

    def build(self) -> None:
        """
        Finaliza a construção do índice espacial.

        Na implementação atual, este método não realiza nenhuma
        operação, pois a busca é feita de forma linear sobre os pontos
        armazenados. Ele é mantido para compatibilidade com possíveis
        implementações futuras que exijam uma fase de construção (por
        exemplo, criação de uma kd-tree ou estrutura de grade).
        """
        # Implementação linear não requer passo de construção.
        return

    def clear(self) -> None:
        """
        Remove todos os pontos do índice espacial.

        Após a limpeza, o índice volta ao estado inicial. Qualquer
        consulta de vizinhança realizada antes de novas inserções
        retornará coleções vazias.
        """
        self._points.clear()

    def __len__(self) -> int:
        """
        Retorna a quantidade de pontos armazenados no índice.

        Returns:
            Número total de pontos atualmente indexados.
        """
        return len(self._points)

    # ------------------------------------------------------------------
    # Consultas de vizinhança
    # ------------------------------------------------------------------

    def k_nearest(
        self,
        x: float,
        y: float,
        k: int,
        max_distance: Optional[float] = None,
    ) -> List[Tuple[str, float]]:
        """
        Retorna até k pontos mais próximos de uma coordenada de consulta.

        A busca é realizada percorrendo todos os pontos armazenados e
        calculando a distância euclidiana até a coordenada fornecida. Os
        resultados são ordenados pela distância crescente e truncados em
        `k` itens. Opcionalmente, um raio máximo pode ser informado para
        filtrar pontos muito distantes.

        Args:
            x:
                Coordenada X do ponto de consulta.
            y:
                Coordenada Y do ponto de consulta.
            k:
                Número máximo de vizinhos a serem retornados. Se o índice
                contiver menos pontos do que `k`, todos os pontos
                disponíveis serão retornados.
            max_distance:
                Distância máxima permitida para considerar um ponto como
                vizinho. Se `None`, não há limite explícito além de `k`.

        Returns:
            Uma lista de tuplas `(item_id, distancia)` ordenada pela
            distância crescente até o ponto de consulta. A lista pode ter
            tamanho menor que `k` se existirem poucos pontos cadastrados
            ou se `max_distance` for restritivo.
        """
        if k <= 0 or not self._points:
            return []

        results: List[Tuple[str, float]] = []
        for record in self._points.values():
            d = hypot(record.x - x, record.y - y)
            if max_distance is not None and d > max_distance:
                continue
            results.append((record.item_id, d))

        results.sort(key=lambda t: t[1])
        if len(results) > k:
            results = results[:k]
        return results

    def radius_search(
        self,
        x: float,
        y: float,
        radius: float,
    ) -> List[Tuple[str, float]]:
        """
        Retorna todos os pontos contidos em um raio ao redor de uma
        coordenada de consulta.

        A busca é realizada percorrendo linearmente todos os pontos
        armazenados e calculando a distância euclidiana até a coordenada
        fornecida. Apenas os pontos cuja distância for menor ou igual ao
        raio informado são retornados.

        Args:
            x:
                Coordenada X do ponto de consulta.
            y:
                Coordenada Y do ponto de consulta.
            radius:
                Raio máximo de busca, na mesma unidade das coordenadas
                cartesianas armazenadas (por exemplo, metros ou unidades
                normalizadas na área de estudo).

        Returns:
            Uma lista de tuplas `(item_id, distancia)` contendo todos os
            pontos dentro do raio especificado, ordenados pela distância
            crescente até o ponto de consulta. Se nenhum ponto for
            encontrado, uma lista vazia é retornada.
        """
        if radius < 0 or not self._points:
            return []

        results: List[Tuple[str, float]] = []
        for record in self._points.values():
            d = hypot(record.x - x, record.y - y)
            if d <= radius:
                results.append((record.item_id, d))

        results.sort(key=lambda t: t[1])
        return results

    # ------------------------------------------------------------------
    # Utilidades adicionais
    # ------------------------------------------------------------------

    def items(self) -> Iterable[Tuple[str, float, float]]:
        """
        Itera sobre todos os pontos armazenados no índice.

        Returns:
            Um iterador de tuplas `(item_id, x, y)` que permite inspecionar
            diretamente os dados armazenados no índice espacial. Este
            método é útil para depuração, geração de relatórios e testes.
        """
        for record in self._points.values():
            yield record.item_id, record.x, record.y


__all__ = ["SpatialIndex"]
