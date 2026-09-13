# Diseño de instrucciones del Codex basado en evidencia

## Conclusión central

El rendimiento confiable del Codex proviene de una jerarquía compacta de orientación específica,
conocimiento de repositorio accesible, validación de ejecutables y comentarios correctivos.
No proviene del lenguaje personal, del énfasis repetido o de un mensaje gigante.

## Elija la superficie duradera más pequeña

| Necesidad | Superficie |
|---|---|
| Objetivo y limitaciones de una tarea | Mensaje de usuario |
| Mapa de repositorio, invariantes, comprobaciones | `AGENTS.md` |
| Regla del subsistema | `AGENTS.md` anidado o anulado |
| Conocimiento profundo del dominio | Documentación versionada |
| Flujo de trabajo repetible | Habilidad |
| Rol de trabajador especializado | TOML de agente personalizado |
| Invariante duro | Prueba, linter, gancho, permisos o CI |
| Elección de tiempo de ejecución de una sola ejecución | Anulación de configuración o indicador CLI |

## Formulario de regla

Prefiere: **activador -> acción -> restricciones -> verificación -> excepción**.

Débil: `Be careful with upgrades.`

Fuerte: `Antes de una actualización crítica para el arranque, registre las versiones instaladas y de destino,
verificar la procedencia y compatibilidad del paquete, confirmar los medios de recuperación o la reversión,
Solicite aprobación con el tiempo de inactividad esperado, luego valide el arranque y los dispositivos afectados.

Prohibiciones estatales con camino seguro: `No X; utilizar Y; excepción Z requiere
aprobación. Separe las invariantes estrictas, los valores predeterminados y las preferencias. Especificar resultados
y límites; Evite la implementación de microgestión cuando los patrones locales sean suficientes.

## Plantilla de solicitud de tarea

1. Objetivo
2. Comportamiento o evidencia actual
3. Comportamiento deseado
4. Rutas, componentes, ejemplos y documentación relevantes
5. Restricciones
6. Alcance y no objetivos
7. Criterios de aceptación observables
8. Verificación exacta
9. Política de ejecución y aprobación

## Ingeniería de contexto

Mantenga la raíz `AGENTS.md` corta y utilícela como tabla de contenido. Poner detallado
conocimiento en documentos indexados y versionados y carga de flujos de trabajo de tareas progresivamente
a través de habilidades. Prefiere anclajes de repositorio e implementaciones análogas a
prosa de estilo genérico. Mantenga la verdad urgente fuera de las instrucciones estáticas a menos que
Incluye un propietario y un mecanismo de actualización.

## Comentarios y aplicación

Si una norma falla repetidamente, no se limite a intensificar su redacción. determinar
si el componente que falta es contexto, un ejemplo, una herramienta, una prueba, una explicación más clara
alcance, un límite de permiso o aplicación mecánica. Validación del diseño
errores para identificar la infracción, solución segura y documentación relevante.

## Anti-patrones

- Indicaciones con mucha personalidad y afirmaciones de experiencia.
- Todo lo etiquetado como crítico.
- Metas abstractas sin controles.
- Criterios de aceptación ocultos.
- Instrucciones contradictorias
- Reglas exhaustivas para casos raros en un contexto siempre cargado
- Solicitar una cadena de pensamiento privada en lugar de evidencia y decisiones.
- Reemplazo de las instrucciones del modelo incorporadas por orientación ordinaria del proyecto.

## Evaluación

Comparar variantes de instrucción en tareas repetidas representativas con las mismas
modelo, estado, permisos y criterios de aceptación. Realice un seguimiento del éxito del primer paso,
violaciones de instrucciones, resultados de pruebas, cumplimiento del alcance, abandono de parches, revisión
hallazgos, eficiencia de las herramientas y tiempo de corrección humana. Se necesitan múltiples ensayos
porque la salida del modelo es estocástica.

## Base de origen

- Solicitud de OpenAI Codex: https://learn.chatgpt.com/docs/prompting
- Descubrimiento de AGENTS.md: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Subagentes: https://learn.chatgpt.com/docs/agent-configuration/subagents
- Habilidades: https://learn.chatgpt.com/docs/build-skills
- Cómo utiliza OpenAI el Codex: https://openai.com/business/guides-and-resources/how-openai-uses-codex/
- Ingeniería de cableado: https://openai.com/index/harness-engineering/
- Bucle del agente Codex: https://openai.com/index/unrolling-the-codex-agent-loop/
