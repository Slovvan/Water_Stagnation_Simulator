import numpy as np
from water.drainage_rule import DrainageRule
from water.gravity_rule import gravity_Rule, lateral_Flow_Rule
from water.rain_class import RainRule


class water_cellular_automata:
    def __init__(
        self,
        grid_size,
        time_steps,
        flow_rate=1.0,
        rain_steps=None,
        rain_drops_per_step=0,
        rain_amount_per_drop=0.0,
        rain_seed=None,
        drain_column=None,
        drain_rate=0.0,
        drain_lateral_rate=0.25,
    ):
        if grid_size <= 0:
            raise ValueError("grid_size debe ser mayor que cero")
        if time_steps < 0:
            raise ValueError("time_steps no puede ser negativo")
        if rain_steps is None:
            rain_steps = time_steps
        if rain_steps < 0 or rain_steps > time_steps or int(rain_steps) != rain_steps:
            raise ValueError("rain_steps debe estar entre 0 y time_steps")
        if not 0 < flow_rate <= 1:
            raise ValueError("flow_rate debe estar entre 0 y 1")
        if not np.isfinite(drain_rate) or drain_rate < 0:
            raise ValueError("drain_rate debe ser un número no negativo")
        if not np.isfinite(drain_lateral_rate) or drain_lateral_rate < 0:
            raise ValueError("drain_lateral_rate debe ser un número no negativo")
        if drain_column is not None and not 0 <= drain_column < grid_size:
            raise IndexError("La columna de drenaje está fuera de la cuadrícula")

        self.grid_size = grid_size
        self.time_steps = time_steps
        self.rain_steps = int(rain_steps)
        self.flow_rate = flow_rate
        self.grid = np.zeros((grid_size, grid_size), dtype=float)
        self.current_step = 0
        self.total_rain = 0.0
        self.total_drained = 0.0
        self.rain_rule = RainRule(
            drops_per_step=rain_drops_per_step,
            amount_per_drop=rain_amount_per_drop,
            seed=rain_seed,
        )
        self.gravity_rule = gravity_Rule(flow_rate=self.flow_rate)
        self.lateral_flow_rule = lateral_Flow_Rule(flow_rate=self.flow_rate)
        self.drainage_rule = DrainageRule(
            column=drain_column,
            flow_rate=drain_rate,
            lateral_flow_rate=drain_lateral_rate,
        )

    def add_water(self, row, column, amount):
        if not (0 <= row < self.grid_size and 0 <= column < self.grid_size):
            raise IndexError("La posición está fuera de la cuadrícula")
        if not np.isfinite(amount) or amount < 0 or self.grid[row][column] + amount > 1:
            raise ValueError("El agua de una celda debe quedar entre 0 y 1")

        self.grid[row][column] += amount

    def _apply_rules(self, step):
        drain_support = ()
        if self.drainage_rule.column is not None:
            drain_column = self.drainage_rule.column
            drain_cell = (self.grid_size - 1, drain_column)
            drain_support = (drain_cell,)

        updated = self.gravity_rule.apply(self.grid)
        updated = self.lateral_flow_rule.apply(
            updated,
            step,
            supported_cells=drain_support,
        )
        self.grid = updated

    def cellular_automata_2d(self):
        for step in range(self.time_steps):
            self.step()
        return self.grid

    def step(self):
        if self.current_step < self.rain_steps:
            self.grid, rain_added = self.rain_rule.apply(self.grid)
        else:
            rain_added = 0.0
        self.total_rain += rain_added
        self._apply_rules(self.current_step)
        self.grid, drained = self.drainage_rule.apply(self.grid)
        self.total_drained += drained
        self.current_step += 1
        return self.grid
