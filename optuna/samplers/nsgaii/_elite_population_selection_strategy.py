from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from collections.abc import Sequence
import itertools

import numpy as np

import optuna
from optuna.samplers.nsgaii._dominates import _constrained_dominates
from optuna.samplers.nsgaii._dominates import _validate_constraints
from optuna.study import Study
from optuna.study import StudyDirection
from optuna.study._multi_objective import _fast_non_dominated_sort
from optuna.trial import FrozenTrial


class NSGAIIElitePopulationSelectionStrategy:
    def __init__(
        self,
        *,
        population_size: int,
        constraints_func: Callable[[FrozenTrial], Sequence[float]] | None = None,
    ) -> None:
        if population_size < 2:
            raise ValueError("`population_size` must be greater than or equal to 2.")

        self._population_size = population_size
        self._constraints_func = constraints_func

    def __call__(self, study: Study, population: list[FrozenTrial]) -> list[FrozenTrial]:
        """Select elite population from the given trials by NSGA-II algorithm.

        Args:
            study:
                Target study object.
            population:
                Trials in the study.

        Returns:
            A list of trials that are selected as elite population.
        """
        _validate_constraints(population, self._constraints_func)
        if self._constraints_func is None:
            objective_values = np.array([trial.values for trial in population]) * np.array(
                [-1.0 if d == StudyDirection.MAXIMIZE else 1.0 for d in study.directions]
            )
            domination_ranks = _fast_non_dominated_sort(objective_values)
            population_per_rank: list[list[FrozenTrial]] = [
                [] for _ in range(max(domination_ranks) + 1)
            ]
            for trial, rank in zip(population, domination_ranks):
                population_per_rank[rank].append(trial)
        else:
            population_per_rank = _constrained_fast_non_dominated_sort(
                population, study.directions, _constrained_dominates
            )

        elite_population: list[FrozenTrial] = []
        for individuals in population_per_rank:
            if len(elite_population) + len(individuals) < self._population_size:
                elite_population.extend(individuals)
            else:
                n = self._population_size - len(elite_population)
                _crowding_distance_sort(individuals)
                elite_population.extend(individuals[:n])
                break

        return elite_population


def _calc_crowding_distance(population: list[FrozenTrial]) -> defaultdict[int, float]:
    """Calculates the crowding distance of population.

    We define the crowding distance as the summation of the crowding distance of each dimension
    of value calculated as follows:

    * If all values in that dimension are the same, i.e., [1, 1, 1] or [inf, inf],
      the crowding distances of all trials in that dimension are zero.
    * Otherwise, the crowding distances of that dimension is the difference between
      two nearest values besides that value, one above and one below, divided by the difference
      between the maximal and minimal finite value of that dimension. Please note that:
        * the nearest value below the minimum is considered to be -inf and the
          nearest value above the maximum is considered to be inf, and
        * inf - inf and (-inf) - (-inf) is considered to be zero.
    """

    manhattan_distances: defaultdict[int, float] = defaultdict(float)
    if len(population) == 0:
        return manhattan_distances

    for i in range(len(population[0].values)):
        population.sort(key=lambda x: x.values[i])

        # If all trials in population have the same value in the i-th dimension, ignore the
        # objective dimension since it does not make difference.
        if population[0].values[i] == population[-1].values[i]:
            continue

        vs = [-float("inf")] + [trial.values[i] for trial in population] + [float("inf")]

        # Smallest finite value.
        v_min = next(x for x in vs if x != -float("inf"))

        # Largest finite value.
        v_max = next(x for x in reversed(vs) if x != float("inf"))

        width = v_max - v_min
        if width <= 0:
            # width == 0 or width == -inf
            width = 1.0

        for j in range(len(population)):
            # inf - inf and (-inf) - (-inf) is considered to be zero.
            gap = 0.0 if vs[j] == vs[j + 2] else vs[j + 2] - vs[j]
            manhattan_distances[population[j].number] += gap / width
    return manhattan_distances


def _crowding_distance_sort(population: list[FrozenTrial]) -> None:
    manhattan_distances = _calc_crowding_distance(population)
    population.sort(key=lambda x: manhattan_distances[x.number])
    population.reverse()


def _constrained_fast_non_dominated_sort(
    population: list[FrozenTrial],
    directions: list[optuna.study.StudyDirection],
    dominates: Callable[[FrozenTrial, FrozenTrial, list[optuna.study.StudyDirection]], bool],
) -> list[list[FrozenTrial]]:
    dominated_count: defaultdict[int, int] = defaultdict(int)
    dominates_list = defaultdict(list)

    for p, q in itertools.combinations(population, 2):
        if dominates(p, q, directions):
            dominates_list[p.number].append(q.number)
            dominated_count[q.number] += 1
        elif dominates(q, p, directions):
            dominates_list[q.number].append(p.number)
            dominated_count[p.number] += 1

    population_per_rank = []
    while population:
        non_dominated_population = []
        i = 0
        while i < len(population):
            if dominated_count[population[i].number] == 0:
                individual = population[i]
                if i == len(population) - 1:
                    population.pop()
                else:
                    population[i] = population.pop()
                non_dominated_population.append(individual)
            else:
                i += 1

        for x in non_dominated_population:
            for y in dominates_list[x.number]:
                dominated_count[y] -= 1

        assert non_dominated_population
        population_per_rank.append(non_dominated_population)

    return population_per_rank
