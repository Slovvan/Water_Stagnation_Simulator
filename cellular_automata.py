from water.water_class import water_cellular_automata
from water.water_animation import animate


def main():
    simulation = water_cellular_automata(
        grid_size=40,
        time_steps=10090,
        rain_steps=100,
        rain_drops_per_step=19,
        rain_amount_per_drop=0.2,
        rain_seed=40,
        drain_column=20,
        drain_rate=0.5,
        drain_lateral_rate=1,
    )

    animate(simulation)


if __name__ == "__main__":
    main()
