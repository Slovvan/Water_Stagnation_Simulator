import numpy as np
from procedural_floor.soil_terrain import generate_soil_terrain
from water.water_class import water_cellular_automata
from water.water_animation import animate


def main():
    grid_size = 200
    dz_mm = 10.0   # 1 celda = 10 mm  ->  corte de 2 m x 2 m (sube dz_mm para un corte más ancho, con capas más delgadas)

    # Suelo procedural de Aguascalientes: lomas y valles, grupos WRB con los % del dataset,
    # 4 horizontes + sustrato rocoso, y psi / Ks / porosidad de Rawls por celda.
    soil = generate_soil_terrain(
        grid_size=grid_size,
        dz_mm=dz_mm,
        seed=3,               # cambia la semilla para otro paisaje
        ks_sigma_ln=0.5,      # variabilidad espacial de Ks (0 = suelo uniforme por capa)
        bedrock="fractured",  # 'sealed' = roca impermeable (el agua se acumula sobre ella)
    )
    print(soil.summary())

    # Escala: 1 unidad de agua (celda llena) = dz_mm; 1 paso = 60 s.
    simulation = water_cellular_automata(
        grid_size=grid_size,
        time_steps=1440,            # 24 h simuladas
        rain_steps=180,             # llueve 18 h y luego se ve cómo drena / se estanca
        rain_intensity_mm_h=30.0,   # la barra y los botones la cambian en vivo
        rain_noise=0.3,
        rain_seed=40,
        dz_mm=dz_mm,
        dt_s=60.0,
        substeps=4,
        soil=soil,
        soil_initial_saturation=0.30,   # supuesto de tu dataset (Graficas, Fig. 7)
        edge_runoff=True,               # la escorrentía puede salir por los bordes
        bottom_drain=True,              # percolación profunda por el fondo
    )

    animate(simulation, steps_per_frame=4)


if __name__ == "__main__":
    main()