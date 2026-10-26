"""Dibujo de las dos vistas como arreglos NumPy (sin pygame): se pueden probar y guardar como imagen."""
from __future__ import annotations

import numpy as np

from aereo.motor import etiquetar
from core.mapa import Mapa
from corte.medio import _perfil
from water.soil_data import AGS
from water.soil_terrain import MATERIAL_RGB

# --- agua: profundidad [mm] -> color. De azul claro (película fina) a azul marino (charco hondo); sin cian ---
PARADAS_MM = np.array([0.05, 1.0, 5.0, 20.0, 50.0, 100.0])
PARADAS_RGB = np.array([(158, 208, 240), (118, 183, 236), (74, 150, 224), (42, 112, 200), (27, 82, 168), (17, 56, 138)], float)
MARCAS_LEYENDA_MM = (0, 5, 20, 50, 100)
CIELO = np.array([221, 235, 246], float)                          # aire del corte
AGUA_CA = np.array([58, 128, 208], float)                         # agua libre en el autómata (celda llena)
SOMBRA_HUMEDA = np.array([6.0, 12.0, 26.0])                       # el suelo mojado se oscurece (a la mitad) y se azula un poco
HUMEDO = SOMBRA_HUMEDA / 255.0
WET_BLUE = HUMEDO                                                 # nombre anterior
BLUES_X = np.array([0.0, 0.25, 0.5, 0.75, 1.0])                   # (en desuso)


def color_agua_mm(h):
    """Color RGB (0-255) del agua con profundidad h (mm, arreglo)."""
    h = np.clip(np.asarray(h, float), PARADAS_MM[0], PARADAS_MM[-1])
    return np.stack([np.interp(h, PARADAS_MM, PARADAS_RGB[:, k]) for k in range(3)], axis=-1)


def alfa_agua(h):
    """Opacidad del agua según su profundidad (mm): crece de forma continua desde 0 (sin salto en el umbral, que era lo que
    hacía parpadear la película fina): ~0.25 con 0.1 mm, ~0.55 con 1 mm y opaca desde ~6 mm."""
    h = np.maximum(np.asarray(h, float), 0.0)
    return np.clip(0.30 * (1.0 - np.exp(-h / 0.08)) + 0.70 * np.minimum(h / 6.0, 1.0) ** 0.7, 0.0, 1.0)


class AguaVisible:
    """Profundidad de agua SOLO PARA DIBUJAR: media móvil exponencial por paso de simulación.

    La física no se toca. Suaviza el vaivén de un paso a otro (la película fina que entra y sale del umbral y la nivelación
    de los charcos cada 2 pasos). Se actualiza una vez por paso nuevo (no por fotograma), así que en pausa la imagen queda
    quieta y a cualquier velocidad se ve igual. `alfa` = peso del paso más reciente."""

    def __init__(self, alfa: float = 0.35):
        self.alfa, self.H, self.paso = alfa, None, -1

    def reiniciar(self):
        self.H, self.paso = None, -1

    def actualizar(self, H: np.ndarray, paso: int) -> np.ndarray:
        if self.H is None or self.H.shape != H.shape or paso < self.paso or paso - self.paso > 400:
            self.H, self.paso = H.copy(), paso                     # primera vez, reinicio, o salto grande: sin arrastre
        elif paso != self.paso:
            w = 1.0 - (1.0 - self.alfa) ** (paso - self.paso)       # equivale a aplicar la media móvil en cada paso
            self.H += (H - self.H) * w
            self.paso = paso
        return self.H


def mojar(base_rgb255, humedad):
    """Color del suelo con humedad 0..1 (0 = seco: su color; 1 = saturado: la mitad de claro con un matiz azulado)."""
    m = np.asarray(humedad, float)
    m = m[..., None] if m.ndim == np.ndim(base_rgb255) - 1 else m
    return base_rgb255 * (1.0 - 0.5 * m) + SOMBRA_HUMEDA * m


def _blues(v):
    """(en desuso) mezcla cielo -> agua según la fracción v de celda llena."""
    v = np.clip(np.asarray(v, float), 0.0, 1.0)[..., None]
    return (CIELO * (1 - v) + AGUA_CA * v) / 255.0


class VistaAerea:
    """Base de color por suelo + relieve sombreado (calculados una vez por mapa) y agua encima."""

    def __init__(self, mapa: Mapa):
        self.mapa = mapa
        rgb = []
        for c in mapa.codes:
            top = _perfil(c, mapa, AGS)[0][0]
            rgb.append(np.array(MATERIAL_RGB.get(top, (0.5, 0.5, 0.5))) * 255.0)
        self.base = np.array(rgb)[mapa.soil_id]
        gy, gx = np.gradient(mapa.elevacion_m)
        s = gx + gy
        s = s / (np.abs(s).max() + 1e-12)
        self.sombra = np.clip(1.0 + 0.35 * s, 0.7, 1.3)[..., None]

    def imagen(self, H: np.ndarray) -> np.ndarray:
        img = self.base.copy()
        mojado = H > 1e-3
        if mojado.any():
            h = H[mojado]
            alfa = alfa_agua(h)[:, None]                                # película: se ve el suelo; charco: opaco; sin salto
            img[mojado] = img[mojado] * (1 - alfa) + color_agua_mm(h) * alfa
        return np.clip(img * self.sombra, 0, 255).astype(np.uint8)

    def sumideros(self, H: np.ndarray, umbral_mm: float = 5.0, previos=None) -> np.ndarray:
        """(fila, col) de los sumideros: UN punto por charco (celdas conectadas, también en diagonal, con más de `umbral_mm`),
        en la celda de terreno más baja del charco, que es donde se acumula el agua.

        Antes se marcaba cada celda con agua cuyo nivel no superaba el de sus 8 vecinas: en un charco nivelado todas empatan,
        así que se marcaban decenas de celdas por charco y cuáles de ellas cambiaba en cada paso por ruido numérico (la rejilla
        roja parpadeando). Con un punto por charco el conjunto es estable.
        Histéresis: un charco aparece al superar `umbral_mm` y solo desaparece por debajo del 60 % de ese valor; `previos` son
        los sumideros del cálculo anterior."""
        n = H.shape[0]
        base = np.zeros(H.shape, bool)
        if previos is not None and len(previos):
            base[tuple(np.asarray(previos, int).T)] = True
        mascara = (H > umbral_mm) | (base & (H > 0.6 * umbral_mm))
        lab, k = etiquetar(mascara)
        if k == 0:
            return np.zeros((0, 2), int)
        padre = np.arange(k + 1)                                    # unión de componentes que se tocan en diagonal

        def raiz(a):
            while padre[a] != a:
                padre[a] = padre[padre[a]]
                a = padre[a]
            return a
        for dc in (1, -1):
            a = lab[:n - 1, max(0, -dc):n - max(0, dc)]
            b = lab[1:, max(0, dc):n - max(0, -dc)]
            m = (a > 0) & (b > 0) & (a != b)
            for x, y in set(zip(a[m].tolist(), b[m].tolist())):
                padre[raiz(x)] = raiz(y)
        lab = np.array([raiz(i) for i in range(k + 1)])[lab]
        salida = []
        z = self.mapa.elevacion_m
        for e in np.unique(lab[lab > 0]):
            dentro = lab == e
            # pegajoso: si el charco ya tenía marca, se queda en la misma celda mientras siga mojada (así no salta de una
            # celda a otra cuando el charco se parte o se une); si no, la celda de terreno más baja
            zz = np.where(dentro & base, z, np.inf)
            if not np.isfinite(zz).any():
                zz = np.where(dentro, z, np.inf)
            salida.append(np.unravel_index(int(np.argmin(zz)), zz.shape))
        return np.array(sorted(salida), int).reshape(-1, 2)

    @staticmethod
    def barra_leyenda(alto: int = 150) -> np.ndarray:
        """(alto, 1, 3) uint8: 0 mm abajo, 100 mm arriba."""
        mm = np.linspace(100.0, 0.0, alto)
        return np.clip(color_agua_mm(mm), 0, 255).astype(np.uint8)[:, None, :]


def imagen_corte(sim, medio) -> np.ndarray:
    """Detalle de 2 m: aire = cielo; agua libre = azul (más intenso cuanto más llena la celda); suelo = color del material,
    más oscuro y azulado cuanto más saturado."""
    w = sim.grid
    cap = np.where(medio.cap > 0, medio.cap, 1.0)
    S = np.clip(w / cap, 0.0, 1.0)
    suelo = mojar(medio.base_rgb * 255.0, S ** 1.5)
    t = np.clip(w, 0.0, 1.0)[..., None]
    aire = CIELO * (1 - t) + AGUA_CA * t
    img = np.where((medio.kind == 0)[..., None], aire, suelo)
    return np.clip(img, 0, 255).astype(np.uint8)


class Gotas:
    """Gotas dibujadas sobre el corte: solo un efecto visual (la física deposita la lluvia directo en la superficie)."""

    def __init__(self, columnas: int, filas: int, n_max: int = 300, caida: float = 2.5, estela: float = 1.6, seed: int = 1):
        self.columnas, self.filas, self.estela = columnas, filas, estela
        self.rng = np.random.default_rng(seed)
        self.n_max = n_max
        self.x = self.rng.uniform(-0.5, columnas - 0.5, n_max)
        self.y = self.rng.uniform(-0.5, filas - 0.5, n_max)
        self.v = caida * self.rng.uniform(0.8, 1.2, n_max)

    def activas(self, intensidad_mm_h: float, max_mm_h: float = 100.0) -> int:
        if intensidad_mm_h <= 0:
            return 0
        return max(1, int(round(self.n_max * np.sqrt(min(intensidad_mm_h / max_mm_h, 1.0)))))

    def segmentos(self, intensidad_mm_h: float, superficie_y: np.ndarray) -> np.ndarray:
        """(m, 3): x, y_arriba, y_abajo de cada raya, en coordenadas de celda del corte."""
        n = self.activas(intensidad_mm_h)
        if n == 0:
            return np.zeros((0, 3))
        x, y = self.x[:n], self.y[:n]
        y += self.v[:n]
        col = np.clip(np.rint(x).astype(int), 0, self.columnas - 1)
        cayo = y >= superficie_y[col]
        if cayo.any():
            y[cayo] = self.rng.uniform(-4.0, -0.5, int(cayo.sum()))
            x[cayo] = self.rng.uniform(-0.5, self.columnas - 0.5, int(cayo.sum()))
            col = np.clip(np.rint(x).astype(int), 0, self.columnas - 1)
        piso = superficie_y[col]
        arriba = np.maximum(y - self.estela, -0.5)
        abajo = np.maximum(np.minimum(np.maximum(y, -0.5), piso), arriba)
        return np.stack([x, arriba, abajo], axis=1)
