# Envío de TUI, verificación previa y plan de corrección de lectura local

> **Nota de implementación (actualizada el 26 de agosto de 2026):** se realiza un seguimiento de la implementación del proyecto
> por [`tui-submit-preflight-latency-root-cause.md`](causa-raiz-latencia-preflight-tui.md).
> Este plan sigue siendo el contrato de aceptación. La implementación y sin cabeza.
> la aceptación está validada por dispositivos; contexto de conversación en vivo del servidor de aplicaciones
> la continuidad sigue siendo un punto de control de aceptación ejecutado por el usuario.

**Estado:** implementado y validado por dispositivos; transferencia de contexto en vivo no verificada
**Preparado:** 2026-08-20
**Mensaje principal:**
`automation/prompts/fix-tui-submit-preflight-latency.md`

## Resultado

El envío de una solicitud nunca debe parecer que congela JARVIS o desaparece mientras
Se ejecuta la resolución de intención. Las lecturas exactas y no confidenciales del sistema de archivos local deben utilizar un
ejecutor determinista acotado en lugar de pagar por un turno de clasificador de modelo.
Las solicitudes con significados plausibles materialmente diferentes deben solicitar al usuario que
Elija un alcance. La UI y la proyección de auditoría deben distinguir captura,
clasificación, admisión, ejecución y negación verazmente.

El comportamiento de referencia es:```text
El usuario envía "enumerar los archivos dentro de Escritorio"
  -> task captured and rendered immediately
  -> deterministic parser resolves list + XDG Desktop
  -> broker admits bounded local read
-> el ejecutor enumera una vez sin shell/modelo/aprobación
-> se representa el resultado limitado desinfectado
  -> one completion summary is journaled
```## Decisiones aceptadas

| Área | Decisión |
| --- | --- |
| Clasificación | Ruta rápida determinista antes de la verificación previa del modelo |
| Envío simultáneo | Deshabilite Enviar brevemente; rechazar, no hacer cola, una segunda presentación |
| Ciclo de vida de la revista | Optimizar el diario existente; sin rotación/eliminación en este cambio |
| Implementación de lectura local | Ejecutor local acotado |
| Alcance del sistema de archivos | Rutas exactas no sensibles y legibles por el usuario actual |
| Operaciones | Lista de directorios, lectura de archivos de texto, búsqueda de nombre de archivo/contenido |
| Ambigüedad | Una pregunta con 2-3 opciones concretas; sin autoridad heredada |
| Fallo/reintento | Un intento; grabar y detener; nunca reproducir automáticamente |

Las lecturas locales son propiedad del corredor y, por lo tanto, funcionan sin conectividad del servidor de aplicaciones.
Esto no convierte órdenes arbitrarias, privilegios, mutaciones o descubrimientos secretos.
disponible sin conexión.

## Evidencia y diagnóstico

### Observado en la fuente actual

- `JarvisTui._dispatch_task()` espera `session.preflight_task()` antes
  `presentation.capture_task()`. Por lo tanto, la representación está acoplada al clasificador.
  latencia.
- `JarvisPresentation.capture_task()` utiliza un literal `host authority none`
  cadena de línea de tiempo en lugar de datos de admisión.
- La verificación previa crea un turno de servidor de aplicaciones con una zona de pruebas de solo lectura y una política de aprobación.
  `never` y un tiempo de espera de finalización de 90 segundos.
- `PREFLIGHT_OUTPUT_SCHEMA` valida las formas de campo individuales pero no las
  invariantes específicas de decisión impuestas por `IntentAssessment`.
- `EventJournal.append()` y `append_once()` analizan todo el diario JSONL en
  un bloqueo sincrónico antes de cada adición.
- `process_event()` registra cada evento normalizado. Se produce una limitación delta de la interfaz de usuario
  más tarde y no puede evitar el costo de la sesión/diario.
- El ejecutor de tareas local reconoce únicamente `knowledge.search`; el existente
  El controlador de host de solo lectura no tiene capacidad de sistema de archivos genérico.

### Evidencia de tiempo de ejecución observada

En el momento de la inspección, `runtime/tui/events.jsonl` era de aproximadamente 13 MiB con 14.054
registros. La actividad de verificación previa de una tarea duró aproximadamente siete segundos y
terminado como una denegación con motivo `invalid typed preflight: ValueError`. el
El resultado del clasificador sin procesar estuvo intencionalmente ausente de la revista, por lo que el resultado exacto
Se desconoce la combinación no válida.

### Modelo de causa raíz para demostrar durante la implementación

Hay tres causas independientes:

1. **Proyección retrasada:** la presentación del usuario se produce después de la admisión esperada.
2. **Denegación falsa/opaca:** el esquema de salida estructurada permite combinaciones
   rechazado por el modelo de dominio de Python, y la excepción pierde el nivel de campo
   contexto.
3. **Presión del bucle de eventos:** el análisis sincrónico O (tamaño de diario) más `fsync` es
   realizado para cada evento transmitido.

La latencia del modelo es la latencia externa esperada. Se convierte en un error de UX porque la UI
no proyecta la tarea pendiente de forma inmediata. El caso de borrar la lista de directorios
debería evitar esa latencia por completo.

## Arquitectura de destino

### Secuencia de admisión```text
capture
  -> render pending task
  -> deterministic preflight
       -> exact local read -> typed local plan -> broker admission -> local executor
       -> deterministic ambiguity -> clarification -> stop
       -> no safe match -> typed model preflight
            -> execute -> broker admission -> existing agent/workflow route
            -> clarify -> clarification -> stop
            -> deny/invalid -> safe reason -> stop
```La captura no es la admisión. La salida del modelo no es autoridad. Un plan de lectura local es
datos, no un comando de shell. La admisión del corredor sigue siendo la única decisión de ruta.

### Diseño de fuente propuesto

Utilice patrones y nombres locales descubiertos durante la implementación. lo esperado
El diseño coherente más pequeño es:

- `tui/src/jarvis_tui/local_filesystem.py`: plan escrito, analizador determinista,
  XDG/resolución de rutas, comprobaciones de políticas y ejecutor limitado.
- `tui/src/jarvis_tui/preflight.py`: resultado de verificación previa determinista más alineado
  modelo de esquema de cable/indicador.
- `tui/src/jarvis_tui/models.py`: plan local y contrato de admisión/dominio.
- `tui/src/jarvis_tui/broker.py`: vinculación del plan, admisión y solo metadatos
  eventos de auditoría.
- `tui/src/jarvis_tui/session.py`: verificación previa del modelo alternativo y resumen de flujo
  acumulación.
- `tui/src/jarvis_tui/event_store.py`: encabezado de diario verificado incremental.
- `tui/src/jarvis_tui/presentation.py` y `app.py`: estado pendiente inmediato,
  guardia ocupada, cronograma veraz y representación de resultados.
- Esquemas, accesorios, pruebas, documentos actuales y manifiesto de lanzamiento correspondientes.

Si un módulo existente proporciona un límite más claro, extiéndalo en lugar de
creando una abstracción duplicada.

## Línea de trabajo 1: envío inmediato y receptivo

Agregue una operación de presentación como `capture_pending_task(task)` que cree
una entrada de usuario/acción con clave con estado `resolving_intent`. Admisión más tarde
actualiza esa entrada y agrega un evento en el cronograma de admisión; no crea un
segunda entrada de usuario.

El responsable del envío debe:

1. Validar y capturar la entrada.
2. Borre sólo la entrada aceptada.
3. Establezca un único estado `_submission_busy`.
4. Deshabilite el botón Enviar y proteja tanto la ruta de entrada como la del botón.
5. Renderizar la entrada pendiente y ceder a Textual antes de esperar clasificación.
6. Ejecutar clasificación/ejecución en un trabajador sin un diario completo sincrónico
   explora en el bucle de eventos.
7. Restaurar envío en `finally`, incluyendo aclarar, denegar, excepción, tiempo de espera,
   desconexión y cancelación.

La navegación y el cambio de tamaño permanecen habilitados. El compositor puede seguir siendo editable, pero un
El envío ocupado nunca consume ni borra el borrador. Cancelar debe interrumpir una
Clasificador activo/turno una vez y resolver la tarea sin repetición automática.

## Línea de trabajo 2: planificación determinista de lectura local

### Plan mecanografiado

Agregue un `LocalFilesystemReadPlan` inmutable (el nombre exacto puede seguir al repositorio
estilo) que contiene:

- versión del esquema e ID del plan;
- enumeración de operaciones: `list`, `read`, `search`;
- etiqueta de destino proporcionada por el usuario;
- ruta de destino canónica;
- modo de búsqueda: nombre de archivo o texto y consulta limitada;
- indicador recursivo, profundidad máxima, límites de elementos/archivos/coincidencias/bytes;
- incluir bandera oculta;
- metadatos de destino capturados en el momento de la planificación cuando sean seguros;
- plan estable/resumen de objetivos.

Vincularlo a `TaskRecord` o su evaluación/admisión por campo mecanografiado, no un
diccionario no estructurado. Vuelva a resolver y verificar el objetivo inmediatamente antes
ejecución. Un objetivo modificado invalida el plan y se detiene.

### Gramática conservadora

Reconozca sólo formas claras de imperativo/consulta:

- Lista en inglés: `list files in PATH`, `show the contents of DIRECTORY`.
- Lista española: `lista/listar los archivos en/de PATH`,
  `muestra el contenido de DIRECTORIO`.
- Inglés léase: `read FILE`, `show the contents of FILE` cuando la resolución resulte probada
  es un archivo normal.
- Lectura en español: `lee/leer ARCHIVO`, `muestra el contenido de ARCHIVO`.
- Búsqueda de nombres de archivos: `find files named QUERY in PATH` y equivalentes en español.
- Búsqueda de contenidos: `search for QUERY in PATH` y equivalentes en español cuando el
  consulta y raíz son sintácticamente distintos.

Las rutas y espacios citados deben analizarse como datos. Operadores Shell, sustituciones,
Las redirecciones y los comandos permanecen como texto inerte y, en general, deberían evitar una rápida
partido. El planificador puede recurrir a la verificación previa del modelo; nunca los ejecuta.

### Resolución de alias

Analizar `~/.config/user-dirs.dirs` como un formato de datos estricto sin obtenerlo.
Resolver al menos Escritorio/Escritorio, Documentos/Documentos,
Descargas/Descargas, inicio y proyecto/espacio de trabajo actual. Prefiero el configurado
Camino XDG. Si no hay ningún valor configurado, seleccione un convencional existente
directorio sólo cuando existe exactamente un candidato. De lo contrario aclarar.No registre la ruta personal completa. La interfaz de usuario puede mostrar la ruta resuelta al
usuario actual después de la desinfección del terminal; el diario almacena una categoría y
digerir.

## Línea de trabajo 3: seguridad del sistema de archivos y ejecución limitada

El ejecutor utiliza `pathlib`, `os.scandir` y E/S de texto delimitado en un trabajador.
hilo. Nunca invoca un shell, subproceso, asistente de privilegios, asistente de paquete,
o servidor de aplicaciones.

### Clases objetivo denegadas

Rechazar en la planificación y volver a comprobar en la ejecución:

- almacenes de credenciales/claves como `.ssh`, `.gnupg`, nube/Kubernetes/contenedor
  ubicaciones de autenticación, conjuntos de claves y almacenes de contraseñas;
- perfiles de navegador, cookies, bases de datos de inicio de sesión, bases de datos de autenticación y
  almacenes de tokens/sesiones;
- contenedores de clave privada/certificado y nombres de archivos que contienen secretos como
  sin ejemplo `.env`, `credentials`, `id_rsa`, `id_ed25519`, `*.key`, `*.pem`,
  `*.p12` y `*.pfx`;
- `/dev`, procesos internos sensibles según `/proc`, sensibles a la seguridad `/sys`
  rutas, sockets, FIFO, dispositivos y otros tipos de archivos no regulares;
- rutas que se deniegan después del enlace simbólico o la resolución canónica.

Las reglas de denegación son una defensa en profundidad, no una pretensión de identificar cada secreto.
Aplique la redacción de contenido del repositorio antes de renderizar. Nunca escribas un diario
archivo/lista/contenido de búsqueda devuelto.

### Límites

| Operación | Límites |
| --- | --- |
| Lista | No recursivo por defecto; 500 entradas; oculto excluido a menos que sea explícito |
| Leer | Archivo de texto normal; leer como máximo 64 KiB; renderiza como máximo 16.000 caracteres desinfectados |
| Buscar | Profundidad 8; 2.000 expedientes regulares; 1 MiB/archivo; 200 partidos; plazo monótono |

Devolver metadatos de resultados estructurados, incluidos truncamientos, recuentos omitidos/denegados,
duración y limitaciones. Los errores de permiso y los archivos que desaparecen son normales
errores escritos, no motivos para volver a intentarlo.

## Flujo de trabajo 4: verificación previa de respaldo alineado

Reemplace el contrato de cable plano con permiso de campo cruzado por un objeto raíz cuyo
La carga útil utiliza variantes de decisión `anyOf` admitidas. Incluir ejecución separada
sucursales para explicaciones y operaciones que requieren objetivos para que la presencia del objetivo sea
aplicado por esquema. Aclarar requiere exactamente una pregunta y 2 o 3 opciones. Negar
no puede llevar una ruta ejecutable.

`IntentAssessment.from_dict()` debe informar errores estables como:

- `preflight.invalid_json`
- `preflight.invalid_shape`
- `preflight.invalid_decision_variant`
- `preflight.missing_target`
- `preflight.invalid_route`
- `preflight.invalid_clarification`

La denominación exacta puede seguir las convenciones existentes, pero los códigos deben ser estables, probados,
seguro de mostrar y más útil que la clase de excepción de Python. Salida bruta
permanece solo en memoria y se descarta después de un resumen de recuento/resumen limitado.

La verificación previa del modelo sigue siendo un turno del clasificador de solo lectura/sin aprobación. el
el cambio elimina ese giro para lecturas locales deterministas; no quita el
Invariante de verificación previa escrita para otras solicitudes con capacidad de ejecución.

## Línea de trabajo 5: claridad del contrato de admisión

Los campos actuales `execution_authorized` y `host_authority` combinan una aplicación
Turno de ejecución del servidor con trabajo local determinista. Revisar el contrato en uno.
versión coherente del esquema. Una forma compatible recomendada es:

- conservar `route` como `local_read`, `agent_conversation` o `blocked`;
- definir `execution_authorized=true` para una lectura local admitida o admitida
  turno de agente;
- añadir `agent_turn_authorized`, verdadero sólo para `agent_conversation`;
- añadir `mutation_authorized`, falso en el momento de la admisión a menos que se produzca una aprobación exacta posterior
  y el estado político lo establece explícitamente;
- utilizar una enumeración de autoridad o un valor equivalente que distinga `none`,
  `bounded-local-read` y `current-user-agent`;
- conservar la política de espacio aislado solo cuando realmente se inicie un turno del servidor de aplicaciones.

Si el análisis de compatibilidad favorece la conservación de los campos antiguos, agregue el nuevo explícito
campos y desaprobar en lugar de cambiar silenciosamente la semántica antigua. Actualizar
`task-admission.schema.json`, accesorios, pruebas de broker, presentación, recuperación,
y médicos juntos.## Línea de trabajo 6: diario de eventos incremental y resúmenes de secuencias

### encabezado del diario

En el primer acceso, escanee y verifique la cadena existente una vez y almacene en caché:

- identidad del inodo/archivo y evidencia de modificación;
- desplazamiento de bytes verificado;
- recuento de registros/siguiente secuencia;
- hash del último evento;
- claves de idempotencia necesarias para la búsqueda de O(1);
- registros analizados opcionalmente para proyecciones `read()` repetidas si la memoria es limitada
  son aceptables.

Para agregar, tome el bloqueo exclusivo y compare el estado actual del archivo con el
caché. Valide solo un sufijo recién agregado. Reemplazo, truncamiento o
La modificación in situ desencadena una nueva exploración completamente verificada o un error de cierre fallido.
Agregue exactamente una línea canónica vinculada a hash, vacíe `fsync` y actualice el caché.
El `verify()` explícito aún escanea la cadena completa y debe continuar detectando
manipulación.

### Delta fusionándose

No agregue un registro para cada `agent_delta`/fragmento de transmisión. mantener acotado
acumuladores por turno/artículo que contienen solo:

- recuento de eventos;
- recuento de caracteres/bytes;
- resumen rodante;
- indicador de saneamiento/truncamiento;
- inicio/fin de duración monótona.

Vacíe un resumen cuando se complete el elemento autorizado y limpie en turno
finalización, cancelación, error o desconexión. Nunca retengas un razonamiento privado,
salida de comando sin formato, contenido de solicitud o contenido de archivo en el acumulador/diario.

## Línea de trabajo 7: presentación veraz

Las entradas de la línea de tiempo son transiciones de estado, no prosa decorativa:

- `captured`: solicitud registrada; aún no hay admisión;
- `resolving_intent`: clasificación determinista/modelo en curso;
- `needs_clarification`: sin autoridad; mostrar la pregunta acotada;
- `admitted/local_read`: lectura local limitada, sin mutación/privilegio;
- `admitted/agent_conversation`: autoridad real del usuario actual y zona de pruebas;
- `blocked`: motivo de la política;
- `classifier_failed`: resultado del clasificador no válido, explícitamente no es un riesgo
  determinación;
- resultado terminal: completado/fallido/cancelado con limitaciones seguras.

Representa valores de admisión en lugar de literales. Mantenga la vista de conversación limpia
corto; Coloque evidencia de diagnóstico limitada en la línea de tiempo.

## Estrategia de verificación

### Pruebas unitarias

- Tabla analizadora de formas positivas, negativas y ambiguas en inglés/español.
- Análisis XDG sin evaluación de shell, respaldo único y ambigüedad.
- Política de ruta para ocultos, sensibles, enlaces simbólicos, permisos, especiales, binarios,
  casos de gran tamaño, desaparición y control terminal.
- Límites de lista/lectura/búsqueda y orden determinista cuando se prometió.
- Matriz de decisión JSON-esquema/modelo-dominio.
- Códigos de error del clasificador estables y sin fugas en el diario de salida sin procesar.
- Caché de diario incremental, sufijo externo, reemplazo/truncamiento,
  idempotencia, permisos, detección de manipulaciones y escaneo de prefijos de una sola vez.
- Recuento/resumen de delta y limpieza.

### Pruebas TUI sin cabeza

- La verificación previa falsa retrasada demuestra que la renderización está pendiente de inmediato antes de su finalización.
- Enviar/Ingresar guardia ocupada y restauración `finally`.
- Navegación y cambio de tamaño durante la clasificación pendiente.
- La solicitud exacta `Escritorio` utiliza la ruta local sin solicitudes del servidor de aplicaciones.
- No hay entradas de usuarios duplicadas en las transiciones de estado.
- Aclarar, negar, fallo del clasificador, cancelación, tiempo de espera y desconexión.
- La línea de tiempo utiliza la ruta/autoridad/motivo real.

### Regresión y aceptación

Ejecute una vez cada uno, en este orden:

1. Nuevas pruebas de analizador/ejecutor/diario enfocadas.
2. Comprobación previa, intermediario, sesión, presentación, servidor de aplicaciones y sin cabeza existentes
   Pruebas TUI.
3. Complete el descubrimiento de `tui/tests`.
4. `./scripts/validate-bundle.sh`.
5. Una aceptación manual o fiel y acéfala de
   `list the files inside Escritorio` con un dispositivo controlado existente.

No realice la aceptación en un directorio real sensible simplemente para
demostrar que funciona. Se prefiere un accesorio XDG temporal. No vuelva a ejecutar un error
comando automáticamente; registrar su resultado, diagnosticar, cambiar el código si
autorizado e informar cualquier validación no ejecutada.

## Criterios de aceptaciónEl cambio se completa solo cuando se demuestra todo esto:

- el texto de usuario pendiente se proyecta antes de cualquier trabajo modelo esperado;
- la solicitud exacta de la lista de escritorio no produce ningún giro, caparazón o aprobación del modelo;
- la interfaz de usuario sigue respondiendo bajo clasificación falsa retrasada y grandes
  condiciones de revista sintética;
- las entradas ambiguas nunca reciben autoridad de ejecución;
- los casos de escape sensibles/especiales/de enlace simbólico fallan al cerrarse;
- La salida del modelo válido para el esquema no puede violar la decisión `IntentAssessment`
  invariantes;
- la salida con formato incorrecto informa una vez un error de clasificador estable seguro;
- el costo de agregar el diario después de la inicialización no escala con el prefijo completo;
- los deltas de flujo no generan un registro fsynced cada uno;
- la integridad de la revista existente y el comportamiento de idempotencia permanecen intactos;
- la autoridad y el motivo de la línea de tiempo se derivan del estado escrito, no del código fijo;
- todos los contratos, esquemas, accesorios, pruebas y hashes de lanzamiento actuales cambiaron
  estar de acuerdo;
- la evidencia de finalización nombra todo lo que no está verificado.

## No objetivos y riesgo residual

Esta solución no crea acceso arbitrario al shell, inspección privilegiada,
autonomía de mutación, autonomía de red, indexación de hogar sin restricciones o perfecta
Detección secreta. El modelo alternativo todavía tiene latencia externa, pero la interfaz de usuario pendiente
debe permanecer receptivo y veraz. Las lecturas de archivos locales pueden encontrar contenido no
predecible a partir de nombres de archivos; negación de objetivos, límites estrictos, redacción y
La auditoría libre de contenido reduce, pero no elimina, ese riesgo.

## Revertir

Todos los cambios previstos son sólo para el proyecto y reversibles restaurando el cambio
Archivos fuente, esquema, accesorio, prueba, documentación y manifiesto. No modificar,
truncar, rotar o eliminar `runtime/tui/events.jsonl` durante la implementación o
revertir. No se permite ningún paquete de host, servicio, ayudante de Polkit o cambio de sistema externo.
parte de este plan.

## Registro de finalización requerido del agente de implementación

Informar artefactos modificados, comandos realmente ejecutados y sus resultados, no verificados
elementos, supuestos, riesgos residuales y estado de reversión. Separado observado
hechos a partir de la inferencia. No afirme que la TUI responde o el caso de aceptación
pasa sin evidencia manual o sin cabeza.
