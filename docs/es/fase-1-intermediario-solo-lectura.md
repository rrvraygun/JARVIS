# Corredor de solo lectura de fase 1

> Registro histórico de diseño. No define la autoridad actual de la TUI. Ver
> `current-product-state.md` y `tui-contract.md`.

## Resultado

La fase 1 está implementada y validada. Agrega una aplicación Codex propiedad del corredor
Sesión de servidor sin agregar un recopilador de Fedora, un ejecutor de comandos, un ejecutor de host,
ruta de aprobación-aceptación o servicio privilegiado. La TUI predeterminada permanece completamente
fuera de línea. No se utilizó ninguna sesión de App Server en vivo ni turno del Codex durante la implementación.
o validación.

La verificación de aceptación de la integración en vivo se pospone intencionalmente hasta que el usuario
elige ejecutarlo. Esta distinción es importante: la finalización del partido demuestra ser un corredor
manejo de lógica y fallas; no afirma que la versión instalada del Codex,
cuenta ChatGPT actual, o se ha ejercido una sesión de red real.

## Superficie entregada

### Transporte del servidor de aplicaciones

El cliente stdio JSONL implementa la inicialización y una lista de permitidos cerrada:

- `account/read`, `account/login/start` administrado, cancelación de inicio de sesión y
  `account/rateLimits/read`;
- `thread/start` y `thread/resume`;
- `turn/start`, `turn/steer` y `turn/interrupt`.

Elimina `OPENAI_API_KEY` y `CODEX_API_KEY` del entorno secundario. Sólo
una cuenta cuyo tipo de servidor de aplicaciones sea `chatgpt` estará lista. no hay pago
Respaldo de API.

El transporte niega todos los métodos fuera de esa lista. En particular, Jarvis ha
sin ruta de transporte a `thread/shellCommand`, `command/*`, `process/*`, `fs/*`,
eliminación de subprocesos, inyección de historial sin procesar o herramientas dinámicas. Stderr está drenado a
evitar el estancamiento del proceso, las solicitudes tienen tiempos de espera y el cierre de la secuencia se convierte en un
evento de desconexión normalizado.

### Controlador de sesión

El controlador posee conexión, autenticación, capacidad, hilo, turno y
estado de solicitud pendiente. Soporta:

- Se requiere inicio de sesión en ChatGPT, listo, con capacidad limitada, autenticación no admitida,
  estados desconectados y fallidos;
- depósitos de límite de velocidad documentados sin credenciales persistentes ni reinicio opaco
  identificaciones de crédito;
- creación de subprocesos de sólo lectura y reanudación explícita de subprocesos;
- un turno de conversación únicamente con `approvalPolicy: on-request` y
  `sandboxPolicy: {type: readOnly}`;
- dirección con `expectedTurnId` e interrupción tanto con ID de hilo como de giro;
- correlación de respuestas y notificaciones incluso cuando se produce un evento de finalización
  llega antes de la respuesta a la solicitud correspondiente.

El envío de turnos en vivo está deshabilitado tanto en el controlador como en la CLI de forma predeterminada.
El indicador compilado de la Fase 1 también prohíbe terminal, recopilador, ejecutor,
herramientas de inspección de host y escritura del sistema de archivos. El sandbox es una defensa en profundidad;
no se trata como una autorización para inspeccionar la estación de trabajo.

### Reducción de eventos y privacidad

El reductor asigna mensajes del servidor de aplicaciones a eventos escritos y aptos para visualización. Eso:

- correlaciona los ID de subprocesos, turnos, elementos, solicitudes y tareas de Jarvis;
- deduplica eventos del ciclo de vida reproducibles mientras conserva transmisiones idénticas
  fragmentos de texto que pueden ser ambos legítimos;
- Las mayúsculas muestran texto y neutralizan ANSI, hipervínculo OSC, C1 y bidireccional.
  controles terminales;
- retiene razonamientos brutos, resultados de comandos y diferencias;
- registra solo resúmenes de contenido, longitudes, claves de metadatos, ID de correlación y
  transiciones de estado en el diario encadenado hash.

Un comando, archivo, permiso, obtención de MCP o solicitud de entrada del usuario de App Server
se convierte en un objeto pendiente. La Fase 1 no expone ningún método de aceptación. Herramienta inesperada
Los elementos, la salida del comando y las diferencias bloquean la tarea. La interrupción es la única
manera disponible para detener tal giro.

### Recuperación e idempotencia

Antes de `turn/start`, el corredor agrega atómicamente una reserva de idempotencia.
La misma tarea de Jarvis no se puede enviar dos veces. Un accidente después de la reserva pero
antes de que una respuesta confirmada se recupere como `blocked` y `uncertain_operation`;
el mensaje nunca se reproduce automáticamente.El diario puede reconstruir el estado de la tarea no confidencial, la correlación entre hilo/giro,
y si el usuario debe volver a enviarlo. Se puede recuperar un ID de hilo del Codex conocido
sin cargarlo. La reanudación es independiente de la pronta presentación.

### Lecturas deterministas locales

El corredor puede enumerar los registros de capacidad y acción y consultar los existentes.
base de datos de conocimiento a través de una conexión SQLite `mode=ro` y `query_only`. un
La base de datos faltante se informa y nunca se crea. Estas lecturas no llaman al
modelo y no inspeccione Fedora.

## Puertas CLI

Los modos de comando son deliberadamente acumulativos:

| Modo de invocación | Servidor de aplicaciones | Cuenta/capacidad leída | Presentación de turnos |
|---|---:|---:|---:|
| sin banderas | apagado | no | no |
| `--connect-app-server` | en | si | no |
| ambos `--connect-app-server --enable-live-turns` | en | si | sí, sólo conversación |

El modo final gasta la asignación del Codex ChatGPT y no forma parte del modo automatizado.
validación. Ninguno de estos modos expone un ejecutor de host.

## Evidencia de validación

La suite Phase 1 utiliza un servidor de aplicaciones falso y tiendas temporales. Cubre:

- Autenticación solo ChatGPT y eliminación del entorno de clave API;
- aplicación de la lista de métodos permitidos;
- inicio/reanudación de subprocesos, inicio de giro/dirección/interrupción y finalización;
- Giros en vivo desactivados de forma predeterminada y construcción de solicitudes de solo lectura;
- normalización del límite de tarifas;
- manejo de eventos duplicados y desordenados;
- correlación de aprobación pendiente sin ruta de aceptación;
- desconexión forzada, recuperación incierta y sin repetición;
- detección de manipulación del diario y falta de persistencia del contenido;
- neutralización de la inyección terminal;
- Registro y acceso al conocimiento sin creación y de solo lectura.

El validador de todo el proyecto sigue siendo la puerta de liberación. Valida la fuente
esquemas, accesorios, habilidades, metadatos de complementos, pruebas del plano de control, pruebas TUI,
Compilación de Python y manifiesto de lanzamiento determinista.

## Base del protocolo oficial

- [Codex App Server](https://learn.chatgpt.com/docs/app-server)
- [Codex authentication](https://learn.chatgpt.com/docs/auth)
- [Codex approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Acceso Codex a través de planes ChatGPT](https://help.openai.com/en/articles/11369540-using-codex-with-chatgpt)

Sólo se utiliza la superficie de protocolo estable. Capacidades experimentales del servidor de aplicaciones
están intencionalmente ausentes de esta fase.

El esquema JSON estable exacto generado por `codex-cli 0.146.0` se vende en
`tui/vendor/codex-app-server-schema/0.146.0/`. El registro de compatibilidad fija el
métodos permitidos y la ortografía de los cables de la versión instalada. En particular, el
El esquema generado requiere `approvalPolicy: "on-request"` y el hilo heredado.
valor de la zona de pruebas `"read-only"`; La política de entorno de pruebas utiliza `{ "type": "readOnly" }`.
El esquema generado tiene prioridad si los ejemplos en prosa difieren.

## Resultado de aceptación en vivo (2026-08-06)

El servidor de aplicaciones `codex-cli 0.146.0` anclado pasó la prueba explícita de humo en vivo
grabado en
`runtime/reports/2026-08-06-jarvis-live-app-server-acceptance.json`:
Cuenta administrada por ChatGPT y lecturas con límite de velocidad, inicio del hilo, uno
solo conversación, solo lectura, giro, dirección, interrupción, desconexión limpia,
volver a conectarse y reanudar el hilo poblado. Sin comando de host, recopilador,
Se realizó una escritura en el sistema de archivos o un cambio de hardware.

La prueba también estableció una regla de ordenamiento: un hilo vacío recién creado puede
aún no tiene un lanzamiento reanudable. Por lo tanto, la aceptación del currículum debe seguir un
turno poblado, no solo un `thread/start` vacío.
