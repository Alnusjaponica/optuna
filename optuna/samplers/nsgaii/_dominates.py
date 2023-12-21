from __future__ import annotations

from collections.abc import Callable
from collections.abc import Sequence
import warnings

import numpy as np

from optuna.samplers._base import _CONSTRAINTS_KEY
from optuna.trial import FrozenTrial


def _validate_constraints(
    population: list[FrozenTrial],
    constraints_func: Callable[[FrozenTrial], Sequence[float]] | None = None,
) -> None:
    if constraints_func is None:
        return
    assert len(population) > 0
    num_constraints = len(population[0].system_attrs[_CONSTRAINTS_KEY])
    for _trial in population:
        _constraints = _trial.system_attrs.get(_CONSTRAINTS_KEY)
        if _constraints is None:
            warnings.warn(
                f"Trial {_trial.number} does not have constraint values."
                " It will be dominated by the other trials."
            )
        elif np.any(np.isnan(np.array(_constraints))):
            raise ValueError("NaN is not acceptable as constraint value.")
        elif len(_constraints) != num_constraints:
            raise ValueError("Trials with different numbers of constraints cannot be compared.")


def _evaluate_penalty(population: Sequence[FrozenTrial]) -> np.ndarray:
    """Evaluate feasibility of trials in population.

    Returns:
        A list of feasibility status T/F/None of trials in population, where T/F means
        feasible/infeasible and None means that the trial does not have constraint values.
    """

    penalty: list[float] = []
    for trial in population:
        constraints = trial.system_attrs[_CONSTRAINTS_KEY]
        if constraints is None:
            penalty.append(float("inf"))
        else:
            assert isinstance(constraints, (list, tuple))
            penalty.append(sum(v for v in constraints if v > 0))

    return np.array(penalty)
