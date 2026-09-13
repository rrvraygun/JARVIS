# Nota de causa raíz de latencia de verificación previa/envío de TUI

**Observado:** 2026-08-20
**Alcance:** inspección de accesorios/solo lectura más el diario TUI existente; no vivir
La solicitud del sistema de archivos o el mensaje del servidor de aplicaciones se reprodujeron para realizar un diagnóstico.

## Causas comprobadas

1. `JarvisTui._dispatch_task()` esperaba `session.preflight_task()` antes del
   antigua proyección `capture_task()`. Por lo tanto, la vista de conversación no tenía ningún usuario.
   entrada para renderizar durante la latencia del modelo. El renderizado no puede ser la causa de
   esa primera pintura que faltaba porque aún no había sido solicitada.
2. Cada solicitud en lenguaje natural inigualable creó un servidor de aplicaciones independiente.
   Turno clasificador con `readOnly`, `never` y un camarero de 90 segundos. el
   La ventana de diario suministrada 11:10:29Z–11:10:36Z contiene una duración de aproximadamente siete segundos.
   ciclo de vida del clasificador antes de la proyección bloqueada.
3. Los antiguos `EventJournal.append()` y `append_once()` analizaron el completo
   Prefijo JSONL para cada evento. El diario en vivo inspeccionado fue 13.212.831
   bytes/14.054 registros. Una cadena sintética copiada de 14.000 registros válida tomó
   0,104779 segundos para verificar y una ruta de anexión de estilo antiguo tomó 0,048719
   segundos en este host. La misma ventana en vivo contenía una aplicación densa y normalizada.
   Eventos del servidor y `process_event()` deltas registrados antes de la limitación de la interfaz de usuario.
   Esto demuestra que el trabajo de prefijo sincrónico fue una fuente de presión de bucle de eventos
   distinto de la espera de red/modelo.
4. El esquema de cable de verificación previa permitía combinaciones de campos cruzados rechazadas por
   `IntentAssessment`, por lo que una respuesta que se ajuste al esquema podría colapsar en el
   ruta `ValueError` no diagnosticada. La producción bruta histórica no fue correctamente
   persistió, por lo que el campo exacto violado en ese evento sigue siendo desconocido.
5. `JarvisPresentation.capture_task()` tradujo la frase literal
   `host authority none`; no derivó la explicación de la evaluación
   o admisión y por lo tanto podría implicar falsamente que la falta de autoridad del anfitrión
   fue el motivo de la denegación.
6. El contrato anclado Codex App Server 0.146.0 `turn/start` expone
   `outputSchema` como objeto. La propia familia de esquemas de protocolos anclados utiliza
   `anyOf`, palabras clave de número de elementos y longitud de cadena, y el generador de solicitudes local
   La prueba de contrato verifica que el esquema anidado se transmita sin cambios. Eso fue
   evidencia a nivel de transporte únicamente. Un informe en vivo posterior en las secuencias del diario.
   14059–14081 produjo un servidor `systemError` antes de la salida del clasificador, lo que demuestra
   que la aceptación del transporte no establecía la aceptación final del producto exacto
   forma del esquema. El error sin formato de 360 ​​caracteres se representó correctamente solo por
   longitud/resumen, por lo que atribuir ese evento únicamente a una palabra clave de esquema sería
   exceder la evidencia retenida.

## Hipótesis refutadas o acotadas

- El mensaje inicial del usuario que falta no fue causado por la representación de la conversación:
  la presentación se invocó sólo después de la verificación previa esperada.
- El intervalo de varios segundos observado no se puede atribuir únicamente al diario.
  análisis: el turno del modelo ocupó la mayor parte de la ventana de marca de tiempo. Diario
  En cambio, el trabajo explica las repetidas paradas del bucle de eventos durante la transmisión.
- La evidencia inspeccionada no establece qué campo modelo causó la
  excepción de validación histórica; reclamar uno excedería el retenido
  evidencia.

## Corrección implementada

La proyección pendiente precede ahora a la clasificación asincrónica; un guardia ocupado
evita colas; las lecturas locales acotadas exactas utilizan un ejecutor determinista; el
El esquema alternativo y el modelo Python comparten variantes de decisión y fallas estables.
códigos; el diario mantiene una cabeza verificada incrementalmente y fusiona deltas;
y el texto de autoridad de la línea de tiempo se deriva del estado escrito. La evidencia de validación es
informado por el registro de finalización de la implementación en lugar de inferirse de
archivos presentes.La evidencia del tiempo de ejecución de seguimiento mostró que el nuevo proceso fusionó eventos de flujo
correctamente (cero registros de transmisión para el turno fallido), mientras que el inicio de la línea de tiempo tenía
reprodujo 500 filas normalizadas heredadas del diario sin cambios. Inicio
La proyección ahora conserva solo los últimos 100 registros de error/ciclo de vida del material y
recuentos acotados para material antiguo y filas de protocolos heredados/no materiales.

Un segundo informe en vivo en las secuencias 14086–14108 clasificó la falla del backend
como `output_schema`, demostrando que la primera corrección de compatibilidad fue insuficiente.
La guía actual de Salidas Estructuradas de OpenAI establece que cada `anyOf` anidado
El esquema debe satisfacer de forma independiente el subconjunto admitido y ese esquema ajustado.
Los modelos pueden rechazar palabras clave de longitud de cadena, rango numérico y cardinalidad de matriz.
El esquema de cableado ahora utiliza cuatro ramas completas de objeto estricto sin esas
palabras clave; Python conserva las comprobaciones semánticas/cardinalidad más estrictas y falla
cerrado una vez con un código estable. Una sonda en vivo de un solo intento a través de una aplicación fijada
El servidor 0.146.0 luego se completó con `decision=execute` y
`route=conversation`. El texto de error del servidor se reduce en la memoria a un estado estable.
categoría no sensible antes de ser descartada.

Una solicitud de aprobación en vivo posterior expuso un defecto de correlación independiente. Aplicación
El servidor emitió `item/commandExecution/requestApproval` con ID de solicitud entera
`0`; el reductor lo retuvo, pero el registro de sesión y la guardia modal TUI
Probé la veracidad de la identificación. Por lo tanto, la línea de tiempo mostró una solicitud pendiente mientras
no apareció ninguna pantalla de revisión. Esas rutas, además de la limpieza de solicitudes resueltas, ahora se prueban
Presencia de identificación explícita. La cobertura de regresión demuestra que el ID `0` está registrado,
se muestra para una revisión exacta, se responde una vez y se elimina sin registrar el diario
texto de comando.

Luego, una revisión independiente de solo lectura identificó cinco defectos que fueron reparados
antes de la validación: manipulación de prefijo combinada con agregar, directorio ilimitado
clasificación, E/S de diario de eventos de material en el bucle de eventos, falta local de un solo uso
reserva de ejecución y enlaces de admisión del sistema de archivos anulables.

## 2026-08-26 seguimiento de continuidad de conversación

La evidencia en vivo de un saludo sin respuesta mostró una aplicación completa de 38 caracteres
Elemento del agente del servidor en el diario. El agente había respondido; esto refutó un
clasificador o explicación de silencio de modelo. El renderizador de conversaciones solo tiene hash
clave de entrada y longitud del texto. `item/started` y `item/completed` llevan el mismo
longitud del texto mientras que solo se cambió el estado, por lo que se podría omitir el elemento completado
después de que la versión en progreso se haya filtrado de la vista limpia. Representación
ahora vincula la clave, el estado, la longitud y el resumen de contenido y fuerza el agente-elemento del terminal
y volver a pintar.

La solicitud/resultado determinista de lectura local también estuvo ausente en el servidor de aplicaciones
hilo por diseño, por lo que los turnos de agentes posteriores carecieron de ese contexto visible. el activo
La proyección de conversación limpia ahora está limitada a 64.000 caracteres desinfectados,
elimina los intercambios completos más antiguos desde la vista/contexto juntos y sincroniza
faltan entradas anteriores una vez a través de `thread/inject_items` fijado antes de la siguiente
verificación previa. La carga útil se enmarca como un historial que no es de confianza y no otorga ninguna autoridad;
la solicitud actual permanece separada. La carga útil inyectada no está por separado.
persistido por JARVIS, los resultados locales deterministas permanecen fuera de la conversación JSON,
y el contexto bruto permanece fuera de los registros de auditoría; Los mensajes ordinarios de usuario/agente conservan
su comportamiento existente en el historial de conversaciones. La muestra de escritorio en vivo también
demostró una brecha en el nombre de archivo sensible a la configuración regional; etiquetas de credenciales en español concatenadas
ahora se filtran antes de su visualización o sincronización.
