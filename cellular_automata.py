from water.water_class import water_cellular_automata
from water.water_animation import animate

def main():
    simulation = water_cellular_automata(grid_size=30, time_steps=60)
    simulation.add_water(row=2, column=7, amount=1.0)
    animate(simulation)


if __name__ == "__main__":
    main()
