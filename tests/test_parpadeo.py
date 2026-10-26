"""Pruebas de los errores de parpadeo, de la lupa cerrada y de la lluvia que no se reinicia.
   python -m tests.test_parpadeo"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.estado import Controlador
from app.render import AguaVisible, VistaAerea, alfa_agua
from core.escenario import Escenario
from water.rain_class import ruido_correlacionado


def _correr(c, minutos):
    c.motor.avanzar_hasta(minutos)


def test_agua_fina_no_parpadea():
    """Antes: ~6 % de las celdas entraban y salían de 'mojado' en cada paso (ruido de lluvia nuevo en cada paso)."""
    c = Controlador(Escenario())
    _correr(c, 40)
    prev, tog = None, []
    for _ in range(120):
        c.motor.step()
        m = c.motor.H > 0.02
        if prev is not None:
            tog.append(float((m ^ prev).mean() * 100))
        prev = m
    print(f"   celdas que cambian de mojado/seco por paso: {np.mean(tog):.2f} %")
    assert np.mean(tog) < 1.5


def test_imagen_estable_entre_pasos_con_agua_suavizada():
    c = Controlador(Escenario())
    _correr(c, 40)
    va = c.vista_aerea
    crudo, suave = [], []
    prev_c = prev_s = None
    for _ in range(60):
        c.motor.step()
        ic = va.imagen(c.motor.H).astype(int)
        is_ = va.imagen(c.agua_dibujo()).astype(int)
        if prev_c is not None:
            crudo.append(float((np.abs(ic - prev_c).sum(axis=2) > 12).mean()))
            suave.append(float((np.abs(is_ - prev_s).sum(axis=2) > 12).mean()))
        prev_c, prev_s = ic, is_
    print(f"   píxeles que cambian por paso: crudo {100 * np.mean(crudo):.2f} % -> suavizado {100 * np.mean(suave):.2f} %")
    assert np.mean(suave) < np.mean(crudo)
    # en pausa (mismo paso) la imagen no cambia nada
    a = c.agua_dibujo().copy()
    assert np.array_equal(a, c.agua_dibujo())


def test_opacidad_continua_sin_salto_en_el_umbral():
    h = np.linspace(0.0, 10.0, 20001)
    a = alfa_agua(h)
    assert a[0] == 0.0 and np.all(np.diff(a) >= -1e-12) and np.max(np.diff(a)) < 0.01 and a[-1] == 1.0
    assert alfa_agua(0.02) < 0.1                                          # antes saltaba de 0 a 0.30 en 0.02 mm


def test_agua_visible_reinicia_y_no_arrastra_tras_un_salto():
    av = AguaVisible(0.35)
    H = np.zeros((4, 4)); H[1, 1] = 10.0
    assert av.actualizar(H, 0)[1, 1] == 10.0
    H2 = np.zeros((4, 4))
    v = av.actualizar(H2, 1)[1, 1]
    assert abs(v - 10.0 * 0.65) < 1e-9
    assert av.actualizar(H2, 0)[1, 1] == 0.0                              # el reloj retrocedió (reiniciar): sin arrastre


def test_un_sumidero_por_charco_y_estable():
    """Antes: decenas de celdas por charco, y cuáles cambiaba en cada paso (la rejilla roja parpadeando)."""
    c = Controlador(Escenario())
    _correr(c, 40)
    prev, difs, cuentas = None, [], []
    for _ in range(120):
        c.motor.step()
        s = {tuple(x) for x in c.sumideros()}
        if prev is not None:
            difs.append(len(s ^ prev))
        cuentas.append(len(s))
        prev = s
    from aereo.motor import etiquetar
    Hv = c.agua_dibujo()
    lab, k = etiquetar(Hv > 5.0)
    s = c.sumideros()
    print(f"   sumideros: {len(s)} (charcos de 4 vecinas: {k}); cambian por paso: {np.mean(difs):.2f}")
    assert 1 <= len(s) <= k + 2                                           # uno por charco (los de diagonal se unen)
    assert all(Hv[f, col] > 3.0 for f, col in s)                          # cada marca está dentro de un charco
    assert np.mean(difs) < 1.0
    assert c.sumideros() is c.sumideros()                                 # una sola vez por paso


def test_lupa_siempre_cerrada_aunque_el_mapa_tenga_bordes_abiertos():
    c = Controlador(Escenario(bordes_abiertos=True))
    _correr(c, 45)
    f, col = np.unravel_index(np.argmax(c.motor.H), c.motor.H.shape)
    c.seleccion = (int(f), int(col)); c.eje = "col"
    c.abrir_detalle()
    lu = c.lupa
    assert c.esc.bordes_abiertos and lu.sim.surface_rule.open_edges is False
    c.pasos_por_frame = 60
    c.avanzar(1e9)
    assert lu.sim.runoff_mm == 0.0                                        # antes se escapaba agua por los costados de la ventana
    assert abs(lu.sim.mass_balance_error()) < 1e-6
    assert c.motor.paso == lu.sim.current_step                            # un solo reloj


def test_la_lluvia_no_se_reinicia_al_volver_al_detalle():
    c = Controlador(Escenario())
    _correr(c, 30)
    c.seleccion = (50, 70)
    c.abrir_detalle()
    c.pasos_por_frame = 60
    c.avanzar(1e9)
    antes = c.lupa.metricas()["lluvia_mm"]
    paso_antes = c.lupa.sim.current_step
    c.ir_a("aerea")
    c.avanzar(1e9)
    c.ir_a("detalle")
    despues = c.lupa.metricas()["lluvia_mm"]
    esperado = c.motor.intensidad_mm_h * (c.lupa.sim.current_step - paso_antes) * c.esc.dt_s / 3600.0
    print(f"   lluvia en la lupa: antes de salir {antes:.2f} mm, al volver {despues:.2f} mm (esperado +{esperado:.2f})")
    assert despues > antes and abs((despues - antes) - esperado) < 0.6    # sigue de donde iba (antes volvía a 0)
    assert c.lupa.sim.current_step == c.motor.paso


def test_ruido_de_lluvia_es_funcion_del_reloj():
    a = ruido_correlacionado(40, 77, (5, 5), 30)
    b = ruido_correlacionado(40, 77, (5, 5), 30)
    assert np.array_equal(a, b)                                           # misma semilla y paso: mismo patrón, recreado o no
    z = [ruido_correlacionado(40, p, (2000,), 30) for p in range(0, 61)]
    assert abs(np.std(z[10]) - 1.0) < 0.06 and abs(np.std(z[15]) - 1.0) < 0.06      # la varianza se conserva entre campos
    assert np.abs(z[10] - z[11]).mean() < 0.25                            # cambia despacio entre pasos vecinos
    # la lupa con el mismo reloj ve la misma lluvia en el paso 80 al abrirse dos veces
    c = Controlador(Escenario()); _correr(c, 30); c.seleccion = (50, 70)
    c.abrir_detalle(); l1 = c.lupa; c.volver(); c.abrir_detalle(); l2 = c.lupa
    l1.sim.rain_rule.apply(l1.sim.grid, step=80); l2.sim.rain_rule.apply(l2.sim.grid, step=80)
    r1 = l1.sim.rain_rule.apply(l1.sim.grid, blocked_cells=l1.sim.ground, step=80)[1]
    r2 = l2.sim.rain_rule.apply(l2.sim.grid, blocked_cells=l2.sim.ground, step=80)[1]
    assert abs(r1 - r2) < 1e-12


if __name__ == "__main__":
    for f in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        t = time.perf_counter()
        f()
        print(f"OK  {f.__name__}  {time.perf_counter() - t:.1f} s")
    print("Todas las pruebas de parpadeo y lupa cerrada pasaron")
