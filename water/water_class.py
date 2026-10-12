import matplotlib.pyplot as plt
import numpy as np
import water.gravity_rule as gravity


class water_cellular_automata:
    def __init__(self, grid_size, time_steps, flow_rate=1.0):
        if grid_size <= 0:
            raise ValueError("grid_size debe ser mayor que cero")
        if time_steps < 0:
            raise ValueError("time_steps no puede ser negativo")
        if not 0 < flow_rate <= 1:
            raise ValueError("flow_rate debe estar entre 0 y 1")

        self.grid_size = grid_size
        self.time_steps = time_steps
        self.flow_rate = flow_rate
        self.grid = np.zeros((grid_size, grid_size), dtype=float)
        self.current_step = 0
        self.gravity_rule = gravity.gravity_Rule(flow_rate=self.flow_rate)
        self.lateral_flow_rule = gravity.lateral_Flow_Rule(flow_rate=self.flow_rate)

    def add_water(self, row, column, amount):
        if not (0 <= row < self.grid_size and 0 <= column < self.grid_size):
            raise IndexError("La posición está fuera de la cuadrícula")
        if not np.isfinite(amount) or amount < 0 or self.grid[row][column] + amount > 1:
            raise ValueError("El agua de una celda debe quedar entre 0 y 1")

        self.grid[row][column] += amount

    def _apply_rules(self, step):
        updated = self.gravity_rule.apply(self.grid)
        updated = self.lateral_flow_rule.apply(updated, step)
        self.grid = updated

    def cellular_automata_2d(self):
        for step in range(self.time_steps):
            self.step()
        return self.grid

    def step(self):
        self._apply_rules(self.current_step)
        self.current_step += 1
        return self.grid
        fig, ax = plt.subplots()
        image = ax.imshow(
            self.grid,
            cmap="Blues",
            vmin=0,
            vmax=1,
            interpolation="nearest",
        )
        title = ax.set_title(f"Agua - paso {self.current_step}")
        ax.set_xlabel("Columna")
        ax.set_ylabel("Fila")
        fig.colorbar(image, ax=ax, label="Cantidad de agua")

        first_step = self.current_step

        def initialize():
            image.set_data(self.grid)
            return image, title

        def update(frame):
            target_step = first_step + frame + 1
            while self.current_step < target_step:
                self.step()
            image.set_data(self.grid)
            title.set_text(f"Agua - paso {self.current_step}")
            return image, title

        animation = FuncAnimation(
            fig,
            update,
            init_func=initialize,
            frames=self.time_steps,
            interval=100,
            blit=True,
            repeat=False,
        )
        plt.show()
        return animation
