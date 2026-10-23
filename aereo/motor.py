"""
Motor aéreo incremental (vista en planta). Mismo reloj, datos y unidades que el corte.

Por paso (dt_s):
  1. Lluvia: i·dt (mm) sobre cada celda (con ruido relativo opcional) mientras t < duracion.
  2. Infiltración Green-Ampt con F acumulada: la capacidad del paso sale de integrar dF/dt = Ks(1 + ψΔθ/F),
        g(F) = F − A·ln(1 + F/A),  g(F_nueva) = g(F) + Ks·dt,   A = ψ·Δθ,  Δθ = (1 − S0)·θe
     y se infiltra min(agua disponible en la celda, capacidad). El encharcamiento aparece solo cuando la
     lluvia supera la capacidad, y el agua encharcada o recibida de otras celdas se sigue infiltrando.
     Si el perfil se llena (almacenamiento), solo pasa la fuga del sustrato (k_fondo): exceso de saturación.
  3. Reparto superficial conservativo hacia vecinos más bajos (8 vecinos), con bordes abiertos o cerrados.

Balance (mm·celda):  lluvia = agua superficial + infiltración acumulada + salida por bordes.
El reparto superficial es un reparto rápido por nivel de agua, no un cálculo de velocidad de escorrentía.
"""
from __future__ import annotations

import numpy as np

from core.escenario import Escenario
from core.mapa import Mapa

UMBRAL_CHARCO_MM = 0.02        # primer charco medible (mismo criterio que el corte)
UMBRAL_AREA_MM = 1.0           # área encharcada: > 1 mm
OMEGA = 0.14                   # conductancia del reparto: sum(pesos)·OMEGA < 1 garantiza estabilidad
_D = 1.0 / np.sqrt(2.0)
VECINOS = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
           (-1, -1, _D), (-1, 1, _D), (1, -1, _D), (1, 1, _D)]
assert OMEGA * sum(w for _, _, w in VECINOS) < 1.0


def _g(F, A):
    return F - A * np.log1p(F / A)


def capacidad_ga(F, A, ks_dt):
    """Infiltración máxima del paso (mm) por Green-Ampt: F_nueva − F, con g(F_nueva) = g(F) + Ks·dt.
    g es creciente y convexa: Newton desde sqrt(2·A·T) cae a la derecha de la raíz y converge monótono (4 pasadas
    dan un residuo relativo < 1e-11 en el rango de A y Ks·dt del proyecto)."""
    T = _g(F, A) + ks_dt
    Fn = np.sqrt(2.0 * A * T) + 1e-300
    for _ in range(4):
        Fn = Fn - (_g(Fn, A) - T) * (Fn + A) / Fn
    return np.maximum(Fn - F, 0.0)


class MotorAereo:
    def __init__(self, mapa: Mapa, esc: Escenario):
        self.mapa, self.esc = mapa, esc
        n = mapa.n
        self.n = n
        self.dt_h = esc.dt_s / 3600.0
        self.z = np.asarray(mapa.elevacion_m, float)
        self.ks = np.asarray(mapa.ks_mm_h, float)
        self.A = np.asarray(mapa.psi_mm, float) * (1.0 - esc.s0) * np.asarray(mapa.theta_e, float)
        self.cap = (1.0 - esc.s0) * np.asarray(mapa.almacen_sat_mm, float)   # espacio del perfil [mm]
        self.kb_dt = float(mapa.k_fondo_mm_h) * self.dt_h
        self.rng = np.random.default_rng(esc.semilla_lluvia)
        self.intensidad_mm_h = float(esc.intensidad_mm_h)
        self.duracion_min = float(esc.duracion_min)
        self.paso = 0
        self.H = np.zeros((n, n))          # agua superficial [mm]
        self.F = np.zeros((n, n))          # infiltración acumulada [mm]
        self.D = np.zeros((n, n))          # fuga profunda acumulada [mm] (parte de F)
        self.t_charco = np.full((n, n), np.inf)   # min del primer charco en cada celda
        self.lluvia_cel = 0.0              # lluvia acumulada (mm·celda)
        self.salida_cel = 0.0              # salida por bordes (mm·celda)
        self.pico_sup = 0.0                # mayor agua superficial total (mm·celda)
        self.t_pico_min = 0.0
        self.t_mitad_min = np.nan          # min hasta que el agua superficial baja a la mitad del pico (tras llover)
        self._lp = np.zeros((n + 2, n + 2))
        self._hp = np.empty((n + 2, n + 2))
        idx = np.arange(n)
        self._borde = []                   # por dirección: celdas cuyo vecino cae fuera del mapa
        for dr, dc, _ in VECINOS:
            fuera = np.zeros((n, n), bool)
            if dr == -1: fuera[0, :] = True
            if dr == 1: fuera[-1, :] = True
            if dc == -1: fuera[:, 0] = True
            if dc == 1: fuera[:, -1] = True
            self._borde.append(np.nonzero(fuera))

    # ---- control en vivo ---------------------------------------------------
    def set_intensidad(self, mm_h: float):
        if not np.isfinite(mm_h) or mm_h < 0:
            raise ValueError("La intensidad debe ser un número no negativo (mm/h)")
        self.intensidad_mm_h = float(mm_h)

    def set_duracion(self, minutos: float):
        if not np.isfinite(minutos) or minutos < 0:
            raise ValueError("La duración debe ser un número no negativo (min)")
        self.duracion_min = float(minutos)

    @property
    def tiempo_min(self) -> float:
        return self.paso * self.esc.dt_s / 60.0

    @property
    def llueve(self) -> bool:
        return self.tiempo_min < self.duracion_min

    # ---- física ------------------------------------------------------------
    def _lluvia(self):
        r = self.intensidad_mm_h * self.dt_h
        if r <= 0 or not self.llueve:
            return
        if self.esc.ruido_lluvia > 0:
            f = np.clip(1.0 + self.esc.ruido_lluvia * self.rng.standard_normal(self.H.shape), 0.0, None)
            self.H += r * f
            self.lluvia_cel += r * float(f.sum())
        else:
            self.H += r
            self.lluvia_cel += r * self.n * self.n

    def _infiltrar(self):
        cap_ga = capacidad_ga(self.F, self.A, self.ks * self.dt_h)
        espacio = np.maximum(self.cap - (self.F - self.D), 0.0)
        infil = np.minimum(self.H, np.minimum(cap_ga, espacio + self.kb_dt))
        self.H -= infil
        self.F += infil
        lleno = (self.F - self.D) >= self.cap - 1e-9            # perfil saturado: solo pasa la fuga del sustrato
        fuga = np.where(lleno, np.minimum(self.kb_dt, self.F - self.D), 0.0)
        self.D += fuga

    def _rutear(self):
        n, H, z = self.n, self.H, self.z
        L = z + H * 1e-3
        Lp, Hp = self._lp, self._hp
        Lp[1:-1, 1:-1] = L
        abiertos = self.esc.bordes_abiertos
        deseado, total = [], np.zeros((n, n))
        for (dr, dc, w), ib in zip(VECINOS, self._borde):
            d = np.maximum(L - Lp[1 + dr:1 + dr + n, 1 + dc:1 + dc + n], 0.0) * (1e3 * OMEGA * w)   # mm
            # vecino fuera del mapa: borde abierto -> el nivel de fuera es el del suelo (sale el agua libre); cerrado -> flujo cero
            d[ib] = H[ib] * (OMEGA * w) if abiertos else 0.0
            deseado.append(d)
            total += d
        escala = np.where(total > H, H / np.where(total > 0, total, 1.0), 1.0)    # nunca sale más agua de la que hay
        Hp[:] = 0.0
        saliente = np.zeros((n, n))
        for (dr, dc, _), d in zip(VECINOS, deseado):
            f = d * escala
            saliente += f
            Hp[1 + dr:1 + dr + n, 1 + dc:1 + dc + n] += f
        interior = Hp[1:-1, 1:-1]
        self.salida_cel += float(Hp[0, :].sum() + Hp[-1, :].sum() + Hp[1:-1, 0].sum() + Hp[1:-1, -1].sum())   # lo que cae fuera del mapa
        self.H = H - saliente + interior

    def step(self):
        self._lluvia()
        self._infiltrar()
        t_next = (self.paso + 1) * self.esc.dt_s / 60.0
        nuevo = (self.H > UMBRAL_CHARCO_MM) & np.isinf(self.t_charco)
        if nuevo.any():
            self.t_charco[nuevo] = t_next
        for _ in range(int(self.esc.pasos_ruteo)):
            self._rutear()
        self.paso += 1
        sup = float(self.H.sum())
        if sup > self.pico_sup:
            self.pico_sup, self.t_pico_min = sup, self.tiempo_min
        elif np.isnan(self.t_mitad_min) and not self.llueve and self.pico_sup > 0 and sup <= 0.5 * self.pico_sup:
            self.t_mitad_min = self.tiempo_min - max(self.duracion_min, self.t_pico_min)

    def avanzar(self, pasos: int):
        for _ in range(int(pasos)):
            self.step()

    def avanzar_hasta(self, minutos: float):
        self.avanzar(max(int(round(minutos * 60.0 / self.esc.dt_s)) - self.paso, 0))

    # ---- medidas -----------------------------------------------------------
    def error_balance(self) -> float:
        """Debe ser ~0: lluvia − (agua superficial + infiltración acumulada + salida por bordes)  [mm·celda]."""
        return float(self.lluvia_cel - self.H.sum() - self.F.sum() - self.salida_cel)

    def metricas(self) -> dict:
        m3 = self.mapa.dx_m ** 2 / 1000.0                      # mm·celda -> m³
        n2 = self.n * self.n
        return {
            "tiempo_min": self.tiempo_min,
            "lluvia_mm": self.lluvia_cel / n2,
            "vol_lluvia_m3": self.lluvia_cel * m3,
            "vol_infiltrado_m3": float(self.F.sum()) * m3,
            "vol_almacenado_suelo_m3": float((self.F - self.D).sum()) * m3,
            "vol_fuga_profunda_m3": float(self.D.sum()) * m3,
            "vol_superficial_m3": float(self.H.sum()) * m3,
            "vol_salida_m3": self.salida_cel * m3,
            "prof_max_mm": float(self.H.max()),
            "prof_media_mm": float(self.H.mean()),
            "area_encharcada_pct": 100.0 * float((self.H > UMBRAL_AREA_MM).mean()),
            "primer_charco_min": float(self.t_charco.min()),
            "pico_superficial_mm": self.pico_sup / n2,
            "t_mitad_min": self.t_mitad_min,
            "error_balance_mm_celda": self.error_balance(),
        }


def tp_formula_min(psi_mm: float, ks_mm_h: float, theta_e: float, i_mm_h: float, s0: float = 0.30) -> float:
    """t_p de Green-Ampt (min), la fórmula del documento y del xlsx. Infinito si i <= Ks."""
    if i_mm_h <= ks_mm_h:
        return float("inf")
    return psi_mm * (1 - s0) * theta_e * ks_mm_h / (i_mm_h - ks_mm_h) / i_mm_h * 60.0
