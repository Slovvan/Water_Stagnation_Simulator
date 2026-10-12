class gravity_Rule:
    def __init__(self, flow_rate=1.0):
        self.flow_rate = flow_rate

    def apply(self, current, blocked_targets=()):
        rows, columns = current.shape
        updated = current.copy()
        blocked_targets = set(blocked_targets)

        for row in range(rows - 1):
            for column in range(columns):
                if (row + 1, column) in blocked_targets:
                    continue

                water = current[row][column]
                space_below = 1.0 - current[row + 1][column]
                flow = min(water, space_below, self.flow_rate)
                updated[row][column] -= flow
                updated[row + 1][column] += flow

        return updated


class lateral_Flow_Rule:
    def __init__(self, flow_rate=1.0):
        self.flow_rate = flow_rate

    def apply(self, current, step, supported_cells=()):
        rows, columns = current.shape
        updated = current.copy()
        first_column = step % 2
        supported_cells = set(supported_cells)

        for row in range(rows):
            for column in range(first_column, columns - 1, 2):
                if row < rows - 1:
                    left_supported = (
                        current[row + 1][column] >= 1.0
                        or (row + 1, column) in supported_cells
                    )
                    right_supported = (
                        current[row + 1][column + 1] >= 1.0
                        or (row + 1, column + 1) in supported_cells
                    )
                    if not left_supported and not right_supported:
                        continue

                left = updated[row][column]
                right = updated[row][column + 1]
                difference = left - right
                flow = min(abs(difference) / 2.0, self.flow_rate)

                if difference > 0:
                    updated[row][column] -= flow
                    updated[row][column + 1] += flow
                elif difference < 0:
                    updated[row][column] += flow
                    updated[row][column + 1] -= flow    

        return updated
    