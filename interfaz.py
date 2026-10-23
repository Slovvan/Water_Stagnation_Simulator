"""Interfaz Pygame para alternar entre el corte 2D y la vista aérea."""
from __future__ import annotations

import secrets

import numpy as np

from aereo.motor import MotorAereo
from core.escenario import Escenario
from core.mapa import generar_mapa, resumen_mapa
from water.soil_data import AGS, PROFILES
from water.soil_terrain import AIR, SOLID, generate_soil_terrain, get_material, resolve_profile_materials
from water.water_class import water_cellular_automata

ANCHO, ALTO = 1240, 900
PASOS_POR_FOTOGRAMA = (1, 2, 4, 8)
INTENSIDAD_MAX_MM_H = 100.0
DURACION_MAX_MIN = 600.0
DURACION_SIMULACION_MIN = 600.0


def crear_simulaciones(seed=3, intensidad_mm_h=30.0, duracion_min=180.0):
    """Crea ambos motores con reloj, lluvia y semilla comunes."""
    esc = Escenario(
        n=200,
        seed=seed,
        dt_s=10.0,
        duracion_min=duracion_min,
        intensidad_mm_h=intensidad_mm_h,
        ruido_lluvia=0.3,
        semilla_lluvia=40,
    )
    pasos_totales = int(10 * 3600 / esc.dt_s)
    pasos_lluvia = int(esc.duracion_min * 60 / esc.dt_s)
    mapa = generar_mapa(esc)
    motor_aereo = MotorAereo(mapa, esc)

    suelo = generate_soil_terrain(
        grid_size=esc.n, dz_mm=10.0, seed=esc.seed,
        ks_sigma_ln=esc.ks_sigma_ln, bedrock=esc.bedrock,
    )
    motor_corte = water_cellular_automata(
        grid_size=esc.n,
        time_steps=pasos_totales,
        rain_steps=pasos_lluvia,
        rain_intensity_mm_h=esc.intensidad_mm_h,
        rain_noise=esc.ruido_lluvia,
        rain_seed=esc.semilla_lluvia,
        dz_mm=10.0,
        dt_s=esc.dt_s,
        substeps=4,
        soil=suelo,
        soil_initial_saturation=esc.s0,
        edge_runoff=esc.bordes_abiertos,
        bottom_drain=True,
    )
    return mapa, motor_aereo, motor_corte, pasos_totales


def informacion_simulacion(vista, mapa, aereo, corte, seed, intensidad_mm_h, duracion_min):
    """Construye métricas, supuestos y materiales completos para el panel desplazable."""
    filas = [
        f"Semilla de terreno: {seed}  |  semilla lluvia: {aereo.esc.semilla_lluvia}",
        f"Reloj: {aereo.tiempo_min:.1f}/{DURACION_SIMULACION_MIN:.0f} min  |  paso: {aereo.esc.dt_s:g} s",
        f"Lluvia: {intensidad_mm_h:g} mm/h x {duracion_min:g} min  |  ruido: {aereo.esc.ruido_lluvia:.2f}",
        f"Suelo inicial: {aereo.esc.s0:.0%}  |  Ks variable: sigma ln = {aereo.esc.ks_sigma_ln:g}",
        f"Roca: {'fracturada (fuga)' if aereo.esc.bedrock == 'fractured' else 'sellada'}  |  bordes: {'abiertos' if aereo.esc.bordes_abiertos else 'cerrados'}",
    ]
    if vista == "aerea":
        n2 = aereo.n * aereo.n
        metricas = aereo.metricas()
        filas.extend([
            "BALANCE DE AGUA — vista aérea",
            f"Lluvia acumulada: {metricas['lluvia_mm']:.2f} mm promedio",
            f"Absorbida/infiltrada: {aereo.F.sum() / n2:.2f} mm acumulados",
            f"Retenida en suelo: {(aereo.F - aereo.D).sum() / n2:.2f} mm",
            f"Fuga profunda: {aereo.D.sum() / n2:.2f} mm  |  escorrentía: {aereo.salida_cel / n2:.2f} mm",
            f"Agua superficial: {aereo.H.mean():.2f} mm prom.  |  máximo: {aereo.H.max():.2f} mm",
            f"Área encharcada (>1 mm): {metricas['area_encharcada_pct']:.2f}%  |  balance: {metricas['error_balance_mm_celda'] / n2:.2e} mm/celda",
            "MATERIALES DEL MAPA — porcentaje de celdas; Ks superficial",
        ])
        resumen = resumen_mapa(mapa)
        for codigo in mapa.codes:
            mascara = mapa.soil_id == mapa.codes.index(codigo)
            nombre = mapa.nombres.get(codigo, codigo)
            ks = float(mapa.ks_mm_h[mascara].mean()) if mascara.any() else 0.0
            filas.append(
                f"{nombre}: {100.0 * mascara.mean():.1f}%  |  Ks sup. media {ks:.2f} mm/h"
            )
        filas.append(
            f"Asignación dataset: {resumen['con_parametros_pct']:.1f}% con parámetros; "
            f"{resumen['confianza']['N/A']:.1f}% sin equivalente"
        )
        filas.append("PERFILES DE MATERIALES — superficie → fondo")
        for codigo in mapa.codes:
            materiales = resolve_profile_materials(codigo, AGS)
            materiales.append("Roca fracturada")
            filas.append(f"{mapa.nombres.get(codigo, codigo)}: {' → '.join(materiales)}")
    else:
        inicial_mm = corte.scale.depth_mm(corte.initial_water, corte.grid_size)
        absorbida = corte.soil_water_mm - inicial_mm + corte.deep_mm
        filas.extend([
            "BALANCE DE AGUA — corte 2D",
            f"Lluvia acumulada: {corte.rain_mm:.2f} mm",
            f"Absorbida por el suelo: {absorbida:.2f} mm (neto + percolación)",
            f"Agua actualmente en suelo: {corte.soil_water_mm:.2f} mm "
            f"(inicial: {inicial_mm:.2f} mm)",
            f"Agua superficial: {corte.surface_water_mm:.2f} mm",
            f"Percolación profunda: {corte.deep_mm:.2f} mm  |  escorrentía: {corte.runoff_mm:.2f} mm",
            f"Balance de masa: {corte.mass_balance_error() * corte.scale.dz_mm / corte.grid_size:.2e} mm",
            "MATERIALES DEL PERFIL — cobertura, Ks y humedad",
        ])
        for material, _ in corte.soil.legend():
            nombre = material.split(" (Ks ", 1)[0]
            mascara = corte.soil._mat_mask(nombre)
            cantidad = int(mascara.sum())
            ks = get_material(nombre, AGS)[1]
            humedad = (
                float(np.mean(corte.grid[mascara] / corte.soil.cap[mascara]))
                if cantidad else 0.0
            )
            filas.append(
                f"{nombre}: {100.0 * cantidad / corte.grid.size:.1f}% celdas "
                f"| Ks {ks:g} mm/h | saturación {humedad:.0%}"
            )
        filas.append("Capas usadas por grupo de suelo (superficie → fondo):")
        for codigo, materiales in zip(corte.soil.codes, corte.soil.materials):
            nombre = AGS.names.get(codigo, codigo)
            filas.append(f"{nombre}: {' → '.join(materiales)}")
    filas.extend([
        "ALTERACIONES / SUPUESTOS DEL MODELO",
        "Relieve, pendiente y distribución de suelos cambian con la semilla.",
        "Ks tiene variación espacial lognormal; perfiles usan capas por grupo.",
        "El agua se infiltra, se almacena, percola y/o sale según los bordes.",
    ])
    return filas


def actualizar_parametros(aereo, corte, intensidad_mm_h, duracion_min):
    """Actualiza lluvia e intervalo de lluvia en los dos motores activos."""
    aereo.set_intensidad(intensidad_mm_h)
    aereo.set_duracion(duracion_min)
    corte.set_rain_intensity(intensidad_mm_h)
    corte.rain_steps = min(
        int(round(duracion_min * 60.0 / corte.scale.dt_s)),
        corte.time_steps,
    )


def renderizar_aereo(mapa, motor: MotorAereo) -> np.ndarray:
    """Devuelve una imagen RGB del relieve aéreo y el agua superficial."""
    elev = mapa.elevacion_m
    relieve = (elev - elev.min()) / max(float(np.ptp(elev)), 1e-12)
    bajo = np.array([75.0, 133.0, 79.0])
    alto = np.array([164.0, 139.0, 91.0])
    terreno = bajo + relieve[..., None] * (alto - bajo)
    agua = np.array([38.0, 111.0, 221.0])
    cobertura = np.clip(motor.H / 8.0, 0.0, 0.88)[..., None]
    return np.asarray(terreno * (1.0 - cobertura) + agua * cobertura, dtype=np.uint8)


def renderizar_corte(motor: water_cellular_automata) -> np.ndarray:
    """Colorea suelo por material/saturación y el agua libre del corte."""
    suelo = motor.soil
    rgb = np.asarray(suelo.base_rgb, dtype=float) * 255.0
    agua_suelo = np.array([43.0, 116.0, 206.0])
    saturacion = np.divide(
        motor.grid,
        suelo.cap,
        out=np.zeros_like(motor.grid),
        where=suelo.cap > 0,
    )
    mezcla_suelo = (0.72 * np.clip(saturacion, 0.0, 1.0))[..., None]
    rgb = rgb * (1.0 - mezcla_suelo) + agua_suelo * mezcla_suelo

    aire = suelo.kind == AIR
    color_aire = np.array([210.0, 229.0, 241.0])
    ocupacion = np.clip(motor.grid, 0.0, 1.0)[..., None]
    rgb[aire] = (
        color_aire * (1.0 - ocupacion[aire])
        + agua_suelo * ocupacion[aire]
    )
    rgb[suelo.kind == SOLID] = (91.0, 91.0, 98.0)
    return np.asarray(np.clip(rgb, 0.0, 255.0), dtype=np.uint8)


def main():
    import pygame

    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Simulador de encharcamiento")
    reloj = pygame.time.Clock()
    fuente = pygame.font.Font(None, 30)
    fuente_chica = pygame.font.Font(None, 23)

    mapa, aereo, corte, pasos_totales = crear_simulaciones()
    vista = "aerea"
    ejecutando = True
    corriendo = True
    velocidad = 0
    seed = 3
    intensidad_mm_h = aereo.intensidad_mm_h
    duracion_min = aereo.duracion_min
    desplazamiento_info = 0

    rect_vista_aerea = pygame.Rect(770, 155, 300, 48)
    rect_vista_corte = pygame.Rect(770, 213, 300, 48)
    rect_pausa = pygame.Rect(770, 295, 300, 48)
    rect_velocidad = pygame.Rect(770, 353, 300, 48)
    rect_reiniciar = pygame.Rect(770, 411, 300, 48)
    rect_nueva_seed = pygame.Rect(770, 469, 300, 42)
    rect_intensidad = pygame.Rect(770, 555, 300, 24)
    rect_duracion = pygame.Rect(770, 630, 300, 24)
    area_imagen = pygame.Rect(35, 92, 700, 650)
    area_info = pygame.Rect(770, 675, 430, 205)
    parametro_arrastrado = None

    def dibujar_boton(rect, texto, activo=False):
        color = (47, 113, 181) if activo else (63, 73, 86)
        pygame.draw.rect(pantalla, color, rect, border_radius=7)
        etiqueta = fuente_chica.render(texto, True, (255, 255, 255))
        pantalla.blit(etiqueta, etiqueta.get_rect(center=rect.center))

    def ajustar_parametro(nombre, posicion_x):
        nonlocal intensidad_mm_h, duracion_min
        rect = rect_intensidad if nombre == "intensidad" else rect_duracion
        fraccion = np.clip((posicion_x - rect.left) / rect.width, 0.0, 1.0)
        if nombre == "intensidad":
            intensidad_mm_h = round(fraccion * INTENSIDAD_MAX_MM_H)
        else:
            duracion_min = round(fraccion * DURACION_MAX_MIN / 10.0) * 10.0
        actualizar_parametros(aereo, corte, intensidad_mm_h, duracion_min)

    def nueva_semilla():
        nonlocal mapa, aereo, corte, pasos_totales, seed, corriendo, desplazamiento_info
        seed = secrets.randbelow(2**32)
        mapa, aereo, corte, pasos_totales = crear_simulaciones(
            seed=seed,
            intensidad_mm_h=intensidad_mm_h,
            duracion_min=duracion_min,
        )
        corriendo = True
        desplazamiento_info = 0

    def dibujar_deslizador(rect, etiqueta, valor, maximo, unidad):
        pygame.draw.rect(pantalla, (67, 76, 87), rect, border_radius=6)
        progreso = np.clip(valor / maximo, 0.0, 1.0)
        relleno = rect.copy()
        relleno.width = int(rect.width * progreso)
        pygame.draw.rect(pantalla, (56, 139, 212), relleno, border_radius=6)
        pygame.draw.circle(
            pantalla,
            (242, 246, 250),
            (rect.left + int(rect.width * progreso), rect.centery),
            9,
        )
        texto = fuente_chica.render(
            f"{etiqueta}: {valor:g} {unidad}", True, (228, 233, 239)
        )
        pantalla.blit(texto, (rect.left, rect.top - 27))

    while ejecutando:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                ejecutando = False
            elif evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    ejecutando = False
                elif evento.key == pygame.K_a:
                    vista = "aerea"
                elif evento.key == pygame.K_c:
                    vista = "corte"
                elif evento.key == pygame.K_SPACE:
                    corriendo = not corriendo
                elif evento.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    velocidad = min(velocidad + 1, len(PASOS_POR_FOTOGRAMA) - 1)
                elif evento.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    velocidad = max(velocidad - 1, 0)
                elif evento.key == pygame.K_r:
                    mapa, aereo, corte, pasos_totales = crear_simulaciones()
                    seed = 3
                    intensidad_mm_h = aereo.intensidad_mm_h
                    duracion_min = aereo.duracion_min
                    corriendo = True
                    desplazamiento_info = 0
                elif evento.key == pygame.K_n:
                    nueva_semilla()
            elif evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                if rect_nueva_seed.collidepoint(evento.pos):
                    nueva_semilla()
                elif rect_intensidad.inflate(0, 24).collidepoint(evento.pos):
                    parametro_arrastrado = "intensidad"
                    ajustar_parametro(parametro_arrastrado, evento.pos[0])
                elif rect_duracion.inflate(0, 24).collidepoint(evento.pos):
                    parametro_arrastrado = "duracion"
                    ajustar_parametro(parametro_arrastrado, evento.pos[0])
                elif rect_vista_aerea.collidepoint(evento.pos):
                    vista = "aerea"
                elif rect_vista_corte.collidepoint(evento.pos):
                    vista = "corte"
                elif rect_pausa.collidepoint(evento.pos):
                    corriendo = not corriendo
                elif rect_velocidad.collidepoint(evento.pos):
                    velocidad = (velocidad + 1) % len(PASOS_POR_FOTOGRAMA)
                elif rect_reiniciar.collidepoint(evento.pos):
                    mapa, aereo, corte, pasos_totales = crear_simulaciones()
                    intensidad_mm_h = aereo.intensidad_mm_h
                    duracion_min = aereo.duracion_min
                    corriendo = True
                    desplazamiento_info = 0
            elif evento.type == pygame.MOUSEWHEEL:
                if area_info.collidepoint(pygame.mouse.get_pos()):
                    desplazamiento_info = max(0, desplazamiento_info - evento.y * 3)
            elif evento.type == pygame.MOUSEMOTION and parametro_arrastrado:
                if evento.buttons[0]:
                    ajustar_parametro(parametro_arrastrado, evento.pos[0])
            elif evento.type == pygame.MOUSEBUTTONUP and evento.button == 1:
                parametro_arrastrado = None

        if corriendo:
            for _ in range(PASOS_POR_FOTOGRAMA[velocidad]):
                if aereo.paso >= pasos_totales:
                    corriendo = False
                    break
                aereo.step()
                corte.step()

        pantalla.fill((25, 30, 37))
        nombre_vista = "Vista aérea" if vista == "aerea" else "Corte 2D"
        titulo = fuente.render(f"Simulador de encharcamiento — {nombre_vista}", True, (245, 247, 250))
        pantalla.blit(titulo, (35, 28))

        pixeles = renderizar_aereo(mapa, aereo) if vista == "aerea" else renderizar_corte(corte)
        imagen = pygame.surfarray.make_surface(np.transpose(pixeles, (1, 0, 2)))
        imagen = pygame.transform.scale(imagen, area_imagen.size)
        pantalla.blit(imagen, area_imagen.topleft)
        pygame.draw.rect(pantalla, (170, 180, 192), area_imagen, 1)

        minutos = aereo.tiempo_min
        etiqueta_tiempo = fuente.render(
            f"t = {minutos / 60:.2f} h  |  lluvia = {aereo.intensidad_mm_h:g} mm/h",
            True, (228, 233, 239),
        )
        pantalla.blit(etiqueta_tiempo, (770, 92))
        dibujar_boton(rect_vista_aerea, "Vista aérea  [A]", vista == "aerea")
        dibujar_boton(rect_vista_corte, "Corte 2D  [C]", vista == "corte")
        dibujar_boton(rect_pausa, "Pausar  [Espacio]" if corriendo else "Reanudar  [Espacio]")
        dibujar_boton(
            rect_velocidad,
            f"Velocidad: {PASOS_POR_FOTOGRAMA[velocidad]} pasos/fotograma  [+/-]",
        )
        dibujar_boton(rect_reiniciar, "Reiniciar  [R]")
        dibujar_boton(rect_nueva_seed, f"Nueva semilla  [N]  ({seed})")
        dibujar_deslizador(
            rect_intensidad,
            "Intensidad de lluvia",
            intensidad_mm_h,
            INTENSIDAD_MAX_MM_H,
            "mm/h",
        )
        dibujar_deslizador(
            rect_duracion,
            "Duración de lluvia",
            duracion_min,
            DURACION_MAX_MIN,
            "min",
        )

        pygame.draw.rect(pantalla, (38, 45, 54), area_info, border_radius=5)
        pygame.draw.rect(pantalla, (100, 112, 126), area_info, 1, border_radius=5)
        filas_info = informacion_simulacion(
            vista, mapa, aereo, corte, seed, intensidad_mm_h, duracion_min
        )
        filas_envueltas = []
        for texto in filas_info:
            palabras = texto.split()
            linea = ""
            for palabra in palabras:
                candidata = f"{linea} {palabra}".strip()
                if linea and fuente_chica.size(candidata)[0] > area_info.width - 14:
                    filas_envueltas.append(linea)
                    linea = palabra
                else:
                    linea = candidata
            if linea:
                filas_envueltas.append(linea)
        lineas_visibles = max(1, area_info.height // 20)
        max_desplazamiento = max(0, len(filas_envueltas) - lineas_visibles)
        desplazamiento_info = min(desplazamiento_info, max_desplazamiento)
        pantalla.set_clip(area_info)
        fin_info = desplazamiento_info + lineas_visibles
        for indice, texto in enumerate(filas_envueltas[desplazamiento_info:fin_info]):
            y = area_info.top + indice * 20
            color = (129, 193, 235) if texto.isupper() else (211, 218, 226)
            pantalla.blit(fuente_chica.render(texto, True, color), (area_info.left + 7, y))
        pantalla.set_clip(None)
        texto_scroll = fuente_chica.render(
            f"Información/materiales: rueda ({desplazamiento_info + 1}-{min(fin_info, len(filas_envueltas))}/{len(filas_envueltas)})",
            True,
            (156, 169, 183),
        )
        pantalla.blit(texto_scroll, (area_info.left, area_info.bottom + 4))

        pygame.display.flip()
        reloj.tick(30)

    pygame.quit()


if __name__ == "__main__":
    main()
