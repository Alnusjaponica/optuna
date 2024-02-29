import heapq
from typing import List

import numpy as np

import optuna


def _solve_hssp(
    rank_i_loss_vals: np.ndarray,
    rank_i_indices: np.ndarray,
    subset_size: int,
    reference_point: np.ndarray,
) -> np.ndarray:
    """Solve a hypervolume subset selection problem (HSSP) via a greedy algorithm.

    This method is a 1-1/e approximation algorithm to solve HSSP.

    For further information about algorithms to solve HSSP, please refer to the following
    paper:

    - `Greedy Hypervolume Subset Selection in Low Dimensions
       <https://doi.org/10.1162/EVCO_a_00188>`_
    """
    selected_vecs: List[np.ndarray] = []
    selected_indices: List[int] = []
    contributions = [
        (-optuna._hypervolume.WFG().compute(np.asarray([v]), reference_point), v)
        for v in rank_i_loss_vals
    ]
    heapq.heapify(contributions)

    hv_selected = 0.0
    while len(selected_indices) < subset_size:
        candidate = heapq.heappop(contributions)
        max_value, max_index  = candidate
        max_value = -(
                optuna._hypervolume.WFG().compute(np.asarray(selected_vecs + [max_index]), reference_point)
                - hv_selected
            )
        if max_value <= contributions[0][0]:
            selected_index = rank_i_indices[max_index]
            selected_vec = rank_i_loss_vals[max_index]
            selected_vecs += [selected_vec]
            selected_indices += [selected_index]
            hv_selected -= max_value
        else:
            heapq.heappush(contributions, (max_value, max_index))

    return np.asarray(selected_indices, dtype=int)
