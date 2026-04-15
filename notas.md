# Crisis Simulator — Nota para Leo

## Qué hay acá

Dos archivos JSON que son el input de contenido para el motor de simulación. Los construimos Lucas y Claude a partir de la arquitectura de subagentes que diseñaste vos.

---

## profiles.json

La biblioteca completa de los 15 agentes. Cada perfil tiene:

- `id` — identificador para referenciar desde las tablas
- `role_universal` — el rol abstracto, independiente del país
- `name_local_argentina` — la instancia local
- `behavior` — lógica de comportamiento, movimiento retórico, dirección y timing en horas
- `activation` — en qué tipos de crisis se activa, con qué intensidad, cuándo guarda silencio
- `sample_phrases` — frases tipo por escenario (para alimentar el prompt de cada subagente)
- `agents_it_activates` / `agents_it_irritates` — efectos sobre otros agentes
- `output_format` — importante para Pedro: algunos agentes generan memes/hilos cortos, otros generan notas largas

**Nota de localización:** para adaptar el sistema a otro mercado (México, USA), mantener `id`, `role_universal` y `behavior.core_logic`. Reemplazar `name_local`, `references` y `sample_phrases`.

---

## activation_tables.json

Las 13 tablas de activación — una por cada combinación de protagonista + tipo de crisis. Cada tabla tiene:

- `activation_order` — lista ordenada de agentes con intensidad, orden de salida, dirección y detonador
- `key_rules` — las 3 reglas críticas de activación para ese escenario (variables condicionales que el orquestador tiene que evaluar antes de activar)
- `temporal_arc` — el arco por horas de la crisis. Esto es la base para el sistema de turnos.
- `global_rules` — reglas que aplican a TODAS las tablas (están en la raíz del JSON)

---

## Lo más importante para el motor

**El sistema de turnos todavía no está en estos archivos** — eso lo definimos en la próxima iteración con Lucas. Pero para que lo tengas en mente mientras construís:

Cada tuit del usuario = un turno. Cada turno avanza el reloj de la crisis. El orquestador tiene que leer en qué hora del `temporal_arc` está y activar solo los agentes que corresponden a ese momento, no todos de golpe. Los agentes tienen que aparecer con delay visual entre cada uno.

El estado de la simulación va a tener tres variables que se actualizan con cada turno: score de reputación, temperatura de agenda y sentiment acumulado. Eso lo especificamos en el tercer archivo (simulation_engine.json) que viene después.

**Pregunta que necesitamos que respondas antes de que avancemos con ese archivo:** ¿preferís que el orquestador llame a los agentes en paralelo y los resultados lleguen con delays simulados en el frontend, o en secuencia real con delays reales entre cada llamada a la API? La primera opción es más rápida, la segunda más fácil de debuggear.

---

## Cobertura de los archivos

- 15 perfiles de agentes completos
- 13 tablas de activación (4 industrial, 3 tech, 3 servicios masivos, 3 líder político)
- Reglas globales de activación
- Arcos temporales por escenario
- Nota de localización para mercados no argentinos

Lucas sigue trabajando en: las 3 crisis precargadas del modo videojuego, los indicadores de reputación, y los textos del sistema. Te llega todo eso en el próximo bloque.
