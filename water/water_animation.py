from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt

def animate(self):
        fig, ax = plt.subplots()
        image = ax.imshow(
            self.grid,
            cmap="Blues",
            vmin=0,
            vmax=1,
            interpolation="nearest",
        )
        title = ax.set_title("")
        ax.set_xlabel("Columna")
        ax.set_ylabel("Fila")
        if self.drainage_rule.column is not None:
            drain_column = self.drainage_rule.column
            ax.annotate(
                "",
                xy=(drain_column, self.grid_size + 0.35),
                xytext=(drain_column, self.grid_size - 0.45),
                arrowprops={"arrowstyle": "->", "color": "black", "lw": 2},
                annotation_clip=False,
            )
            ax.set_ylim(self.grid_size + 0.7, -0.5)
        fig.colorbar(image, ax=ax, label="Cantidad de agua")

        first_step = self.current_step

        def update_title():
            title.set_text(
                f"Paso {self.current_step} | "
                f"Agua: {self.grid.sum():.2f} | "
                f"Drenada: {self.total_drained:.2f}"
            )

        def initialize():
            image.set_data(self.grid)
            update_title()
            return image, title

        def update(frame):
            target_step = first_step + frame + 1
            while self.current_step < target_step:
                self.step()
            image.set_data(self.grid)
            update_title()
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