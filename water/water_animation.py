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