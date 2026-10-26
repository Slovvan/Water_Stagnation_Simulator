# Simulador de encharcamiento: vista aérea + corte

```
pip install -r requirements.txt
python main.py
```

## Manejo
Una sola simulación (el motor aéreo) y tres pestañas arriba: **Mapa**, **Corte lateral** y **Detalle 2 m**.
- **Mapa**: vista aérea de 100 m × 100 m. Clic = elegir la línea del corte (línea amarilla; por defecto el lado derecho),
  flechas = moverla, **L** o "Más agua" = saltar a la línea con más agua, "Línea: columna/fila" = cambiar el eje.
- **Corte lateral** (pestaña o Tab; también doble clic en el mapa): la sección de esa línea **dibujada con el mismo motor**:
  relieve, horizontes, frente de humedad (de la infiltración acumulada), charcos con la superficie horizontal y gotas.
  Es la misma simulación, sin costo extra. La altura está exagerada.
- **Detalle 2 m** (pestaña o tecla D): el autómata del corte original sobre una ventana de 2 m, con motor aparte, que parte del
  estado del mapa al abrirse. No modifica el mapa. Es un sistema **siempre cerrado** (el agua no sale por los costados de la
  ventana, aunque el mapa tenga bordes abiertos) y **comparte el reloj con el mapa**: mientras está abierto, el mapa sigue
  avanzando a la par. La lluvia no se reinicia al volver: su patrón depende del reloj común y el contador de lluvia continúa.
- **Pasa el ratón** sobre un material (en las tres vistas) para ver su popup: grupo de suelo, horizonte, Ks, ψ, θe, profundidad,
  si está mojado y hasta dónde llegó el frente. Sobre los botones y barras aparece su ayuda.
- **Lluvia** (tarjeta de arriba a la derecha): intensidad y duración en vivo; **Continua** = sin límite de duración;
  **Detener / Reanudar** = parar o volver a llover ahora; **+30 min** = prolongarla. **La simulación no se detiene sola**:
  solo con Pausa (Espacio).
- **Velocidad** en minutos simulados por segundo real (0.25 a 60); el resumen muestra la que se logra.
- **Terminar y generar reporte** (o tecla F): pausa y guarda en `reportes/` un HTML con tablas, gráficas y el estado final, más
  un CSV con la serie temporal. Al cerrar la aplicación, si hubo simulación y no se generó un reporte, se guarda uno solo.
- **Ventana**: se abre con un tamaño que cabe en tu pantalla y es redimensionable; minimizar, maximizar y cerrar son los botones
  del sistema (la aplicación no dibuja los suyos). F11 = pantalla completa. Terreno, S0, bordes y roca se aplican con
  **Regenerar terreno**.
- **Sumideros** (anillos rojos del mapa): uno por charco de más de 5 mm, en su celda más baja.
- Espacio = pausa · R = reiniciar · Esc = volver · F11 = pantalla completa.

**Parpadeo.** El ruido de la lluvia entre celdas (`Escenario.ruido_tau_min`, 5 min) cambia despacio en vez de sortearse en cada paso; los charcos se nivelan en cada paso; y el agua que se dibuja es una media móvil de la simulación (no cambia la física ni las cifras).

## Estructura
| Carpeta | Contenido |
|---|---|
| `water/` | Corte vertical (autómata celular), datos de suelo y confianzas del xlsx |
| `core/` | `Escenario` compartido y generador del mapa (ruido fractal 2D, suelos con los % del dataset) |
| `aereo/` | Motor aéreo: Green-Ampt con F acumulada, almacenamiento, reparto superficial, balance de masa |
| `corte/` | Detalle de 2 m: `medio.py` (ventana desde el mapa) y `lupa.py` (inicialización, reloj común, aporte) |
| `app/` | `estado.py` (controlador y serie temporal), `corte_sync.py` (corte lateral), `render.py` (dibujos en NumPy), `reporte.py` (reporte HTML/CSV), `ui.py` (pygame-ce) |
| `tests/` | Pruebas de cada fase |

## Pruebas
```
python -m tests.test_aereo     # motor aéreo
python -m tests.test_lupa      # detalle de 2 m
python -m tests.test_corte     # corte lateral sincronizado
python -m tests.verificar_materiales   # infiltración de cada material frente a Green-Ampt
python -m tests.test_app       # controlador y dibujos
python -m tests.test_parpadeo  # parpadeo del agua fina y de los sumideros, lupa cerrada, lluvia que no se reinicia
python -m tests.test_ui        # recorrido de la interfaz con un pygame SIMULADO (no sustituye una prueba con pygame real)
# tests/pil_pygame.py es una herramienta de desarrollo que dibuja la interfaz con PIL para sacar capturas (vistas_previas/ui_*.png)
python validar_suelo.py        # verificación del corte contra Green-Ampt
```

## Estado del plan
| Fase | Estado |
|---|---|
| 0 Base · 1 Núcleo común · 2 Motor aéreo | hechas |
| 3 Optimizar el corte | **pendiente** |
| 4 Detalle de 2 m | hecha |
| 5 Interfaz con botón de vista y corte sincronizado | hecha (falta probarla con pygame real) |
| 6 Métricas y escenarios en ambos motores · 7 Documentación | pendientes |

## Límites conocidos
- Los bordes abiertos dejan que el terreno continúe con su pendiente: el agua sale solo donde el terreno baja hacia afuera (el lado derecho de la semilla 42 drena). Con bordes cerrados el agua se acumula contra el borde.
- El mapa infiltra con el horizonte superficial y limita por almacenamiento: no ve capas con otra Ks. En Luvisoles (horizonte argílico a ~20 cm) y tormentas de más de ~3 h sobreestima la infiltración (72 frente a 56 mm a las 5 h); en Durisoles el duripán (a ~40 cm) no se alcanza en tormentas normales.
- El reparto del agua superficial es rápido por niveles, no una velocidad real de escorrentía. Los charcos (celdas conectadas con más de 2 mm) se nivelan: su superficie queda horizontal.
- El corte lateral dibuja lo que calcula el mapa: no muestra flujo dentro del suelo ni agua que sale de la línea hacia los lados; para eso está el detalle de 2 m.
- El detalle es un acercamiento de un solo sentido (recibe el aporte del mapa, pero lo que sale de la ventana no vuelve al mapa; el agua libre de la lupa y la del mapa pueden diferir con el tiempo, porque sus motores de infiltración son distintos) y su ventana tiene unos 50 cm de aire sobre el punto más alto: un charco más hondo descarta el agua que no cabe (el panel lo avisa).
- El corte cuesta ~21 ms por paso, así que se ve más lento que el mapa; se optimiza en la fase 3.
