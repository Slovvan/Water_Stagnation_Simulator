"""
Reglas del simulador de agua vectorizadas con numpy.

- gravity_Rule y lateral_Flow_Rule tienen la MISMA interfaz que en gravity_rule.py,
  asi que se pueden usar como reemplazo directo (diferencia maxima verificada: 2.2e-16).
- UniformRainRule es una lluvia repartida en todas las columnas (con ruido opcional),
  que separa la intensidad del tamano de gota.
- sub_steps (en step_physics) repite gravedad + lateral varias veces por paso de lluvia.
"""
import numpy as np


class gravity_Rule:
    def __init__(self, flow_rate=1.0):
        self.flow_rate = flow_rate

    def apply(self, current, blocked_targets=()):
        flow = np.minimum(np.minimum(current[:-1], 1.0 - current[1:]), self.flow_rate)
        for (row, column) in blocked_targets:          # celda destino bloqueada
            if 1 <= row < current.shape[0]:
                flow[row - 1, column] = 0.0
        updated = current.copy()
        updated[:-1] -= flow
        updated[1:] += flow
        return updated


class lateral_Flow_Rule:
    def __init__(self, flow_rate=1.0):
        self.flow_rate = flow_rate

    def apply(self, current, step, supported_cells=()):
        rows, columns = current.shape
        updated = current.copy()
        left_cols = np.arange(step % 2, columns - 1, 2)
        if left_cols.size == 0:
            return updated
        right_cols = left_cols + 1

        # una celda esta "soportada" si la de abajo esta llena o es una celda de soporte
        full_below = np.zeros((rows, columns), dtype=bool)
        full_below[:-1] = current[1:] >= 1.0
        for (row, column) in supported_cells:
            if row >= 1:
                full_below[row - 1, column] = True
        active = full_below[:, left_cols] | full_below[:, right_cols]
        active[-1, :] = True                           # el piso siempre sostiene

        left, right = current[:, left_cols], current[:, right_cols]
        diff = left - right
        flow = np.minimum(np.abs(diff) / 2.0, self.flow_rate) * np.sign(diff) * active
        updated[:, left_cols] = left - flow
        updated[:, right_cols] = right + flow
        return updated


class UniformRainRule:
    """Cada columna recibe `intensity` por paso, con ruido relativo `noise` (0 = uniforme)."""

    def __init__(self, intensity=0.0, noise=0.0, seed=None):
        self.intensity, self.noise = intensity, noise
        self.rng = np.random.default_rng(seed)

    def apply(self, current):
        updated = current.copy()
        columns = updated.shape[1]
        amounts = self.intensity * (1.0 + self.noise * self.rng.standard_normal(columns))
        amounts = np.clip(amounts, 0.0, 1.0 - updated[0])
        updated[0] += amounts
        return updated, float(amounts.sum())


def step_physics(grid, step, gravity, lateral, supported_cells=(), sub_steps=1):
    """Gravedad + flujo lateral, repetidos `sub_steps` veces por paso."""
    for k in range(sub_steps):
        grid = gravity.apply(grid)
        grid = lateral.apply(grid, step * sub_steps + k, supported_cells=supported_cells)
    return grid