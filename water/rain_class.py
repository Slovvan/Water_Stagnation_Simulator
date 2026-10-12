import numpy as np


class RainRule:
    def __init__(self, drops_per_step=0, amount_per_drop=0.0, seed=None):
        if drops_per_step < 0 or int(drops_per_step) != drops_per_step:
            raise ValueError("drops_per_step debe ser un entero no negativo")
        if not np.isfinite(amount_per_drop) or amount_per_drop < 0:
            raise ValueError("amount_per_drop debe ser un número no negativo")

        self.drops_per_step = int(drops_per_step)
        self.amount_per_drop = amount_per_drop
        self.rng = np.random.default_rng(seed)

    def apply(self, current):
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
            amount = min(
                self.amount_per_drop,
                1.0 - updated[0, column],
            )
            updated[0, column] += amount
            added += amount

        return updated, added