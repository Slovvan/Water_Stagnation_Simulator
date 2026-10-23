# Simulador de encharcamiento: vista aérea + corte (en construcción)

Estado del plan de fusión:

| Fase | Estado |
|---|---|
| 0. Base: estructura, confianzas del xlsx, `cellular_automata.py` con Δt = 10 s y 3 h de tormenta | hecha |
| 1. Núcleo común: `core/escenario.py`, `core/mapa.py` (ruido fractal 2D sin `noise`, suelos continuos con los % del dataset) | hecha |
| 2. Motor aéreo nuevo: `aereo/motor.py` (Green-Ampt con F, almacenamiento, agua que llega se infiltra, bordes, balance) | hecha |
| 3. Optimizar el corte | pendiente |
| 4. Lupa: corte de 2 m desde el mapa aéreo | pendiente |
| 5. Interfaz pygame-ce con botón de vista | hecha |
| 6. Métricas y escenarios en ambos motores | pendiente |
| 7. Documentación | pendiente |

Pruebas: `python -m tests.test_aereo` (o `pytest tests`). Verificación del corte: `python validar_suelo.py`.
Interfaz: `python interfaz.py` (selecciona **Vista aérea** o **Corte 2D**; arrastra las barras para cambiar en vivo la intensidad de lluvia [0–100 mm/h] y su duración [0–600 min]; teclas A/C, espacio para pausar, +/- para velocidad y R para reiniciar).
Ambas vistas avanzan con el mismo reloj y lluvia, pero usan terrenos y motores independientes; el corte todavía no es una sección extraída del mapa aéreo.
Requisitos: `numpy`, `matplotlib` (animación previa del corte) y `pygame-ce`.
