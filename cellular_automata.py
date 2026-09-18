import numpy as np
import matplotlib.pyplot as plt
import cellpylib as cpl


ca = cpl.init_simple(200)
ca = cpl.evolve(ca, 100, apply_rule=lambda n, c, t: cpl.nks_rule(n, 30), 
                memoize=True)

def main():
    cpl.plot(ca)
if __name__ == "__main__":
    main()