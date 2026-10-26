import numpy as np


def ruido_correlacionado(semilla, paso, forma, tau_pasos):
    """Ruido normal estándar que cambia despacio: función PURA de (semilla, paso), sin estado.

    Cada `tau_pasos` pasos hay un campo aleatorio independiente y entre dos campos se mezcla con cos/sen (la varianza se
    conserva). Al ser función del reloj, el patrón de lluvia no se reinicia aunque se recree la simulación (la lupa) y las
    celdas no cambian de estado en cada paso (eso era lo que hacía parpadear el agua fina)."""
    k, frac = divmod(float(paso) / float(tau_pasos), 1.0)
    k = int(k)
    z0 = np.random.default_rng([abs(int(semilla)), k]).standard_normal(forma)
    if frac < 1e-12:
        return z0
    z1 = np.random.default_rng([abs(int(semilla)), k + 1]).standard_normal(forma)
    ang = 0.5 * np.pi * frac
    return np.cos(ang) * z0 + np.sin(ang) * z1


class RainRule:
    """Lluvia por gotas (modo original): cae como máximo una gota por columna y por paso."""

    def __init__(self, drops_per_step=0, amount_per_drop=0.0, seed=None):
        if drops_per_step < 0 or int(drops_per_step) != drops_per_step:
            raise ValueError("drops_per_step debe ser un entero no negativo")
        if not np.isfinite(amount_per_drop) or amount_per_drop < 0:
            raise ValueError("amount_per_drop debe ser un número no negativo")

        self.drops_per_step = int(drops_per_step)
        self.amount_per_drop = amount_per_drop
        self.rng = np.random.default_rng(seed)

    def apply(self, current, blocked_cells=(), step=None):
        updated = current.copy()
        added = 0.0
        if self.drops_per_step > updated.shape[1]:
            raise ValueError(
                "No puede caer más de una gota por columna en cada paso"
            )
        columns = self.rng.choice(
            updated.shape[1],
            size=self.drops_per_step,
            replace=False,
        )

        for column in columns:
            if isinstance(blocked_cells, np.ndarray) and blocked_cells[0, column]:
                continue
            amount = min(
                self.amount_per_drop,
                1.0 - updated[0, column],
            )
            updated[0, column] += amount
            added += amount

        return updated, added


class UniformRainRule:
    """Lluvia calibrada en mm/h, repartida entre todas las columnas.

    Cada paso, cada columna recibe  u = intensidad * dt / dz  unidades de agua, con un ruido
    relativo opcional (noise). El agua se deposita directamente sobre el agua acumulada
    (del piso hacia arriba), así que llega a la superficie en el mismo paso.
    La intensidad se puede cambiar en cualquier momento con set_intensity().
    """

    def __init__(self, scale, intensity_mm_h=0.0, noise=0.0, seed=None, tau_steps=0):
        if not np.isfinite(noise) or noise < 0:
            raise ValueError("rain_noise debe ser un número no negativo")
        self.scale = scale
        self.noise = float(noise)
        self.seed = 0 if seed is None else int(seed)
        self.tau_steps = float(tau_steps)       # > 0: ruido que cambia despacio, función del paso (ver ruido_correlacionado)
        self.rng = np.random.default_rng(seed)
        self.intensity_mm_h = 0.0
        self.set_intensity(intensity_mm_h)

    def set_intensity(self, intensity_mm_h):
        if not np.isfinite(intensity_mm_h) or intensity_mm_h < 0:
            raise ValueError("La intensidad de lluvia debe ser un número no negativo (mm/h)")
        self.intensity_mm_h = float(intensity_mm_h)

    @property
    def units_per_step(self):
        return self.scale.rain_units_per_step(self.intensity_mm_h)

    def apply(self, current, blocked_cells=(), step=None):
        updated = current.copy()
        rows, columns = updated.shape
        per_column = self.units_per_step
        if per_column <= 0:
            return updated, 0.0

        if self.noise > 0:
            if self.tau_steps > 0 and step is not None:
                z = ruido_correlacionado(self.seed, step, columns, self.tau_steps)
            else:
                z = self.rng.standard_normal(columns)
            factors = np.clip(1.0 + self.noise * z, 0.0, None)
            remaining = per_column * factors
        else:
            remaining = np.full(columns, per_column)

        added = 0.0
        for row in range(rows - 1, -1, -1):  # del piso hacia arriba
            put = np.minimum(1.0 - updated[row], remaining)
            if isinstance(blocked_cells, np.ndarray):
                if blocked_cells.shape != updated.shape:
                    raise ValueError("blocked_cells debe tener la misma forma que current")
                put[blocked_cells[row]] = 0.0
            updated[row] += put
            remaining = remaining - put
            added += float(put.sum())
            if remaining.max() <= 1e-15:
                break
        return updated, added
