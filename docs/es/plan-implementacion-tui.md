# Arquitectura de interfaz de terminal Jarvis y plan de implementación

## Resumen de decisión

### Anexo de implementación actual (2026-08-27)

La siguiente fase narrativa sigue siendo historia del diseño. La implementación actual
agrega el primer segmento de mutación determinista controlado por aprobación especificado por
`tui-mutation-executor.md`: el sistema de archivos exacto del usuario actual crea y
mover a la Papelera utiliza un plan inmutable exclusivo de Python; instalación/eliminación del paquete exacto
utiliza una vista previa de solo caché y un asistente registrado de Polkit; cada mutación recibe
una nueva decisión modal; y el trabajo más amplio con agentes de usuario actuales queda atrás
verificación previa escrita más revisión de comando/archivo del servidor de aplicaciones `untrusted`. admisión de tareas
La versión 3 del esquema representa estas autoridades pendientes por separado de las lecturas y
giros del agente.

Cree una aplicación de terminal híbrida con dos puntos de entrada iguales:

1. un compositor en lenguaje natural para solicitudes abiertas y preguntas de seguimiento;
2. un catálogo con capacidad de búsqueda de acciones versionadas con parámetros escritos.

No son sistemas de ejecución separados. Ambos se convierten en uno `IntentEnvelope`, ingresa
una conversación, y pasar por el mismo estado, evidencia, política, aprobación,
Puertas de ejecución, verificación, auditoría y aprendizaje.

Utilice una interfaz de Python para la primera implementación, con Textual como líder
Candidato a TUI. Mantenga la interfaz reemplazable. Poner la orquestación en un lugar separado.
servicio de aplicación local e integrar Codex a través de `codex app-server` sobre
su superficie JSON-RPC estable. El SDK oficial de Python Codex puede incluirlo
conexión donde expone las API de aprobación y eventos requeridos; el
la aplicación debe recurrir al esquema del servidor de aplicaciones generado en lugar de ocultarse
o comportamiento aproximado del protocolo faltante.

El perfil interactivo implementado utiliza una verificación previa escrita seguida de una verificación de alcance.
ejecución. No crea una autoridad raíz bruta; ayudantes registrados de Polkit
sigue siendo el límite preferido entre el huésped y la mutación.

La primera expansión especializada agrega System Health and Cargo, el primero de Fedora
Descriptores del constructor. Sus recolectores MCP tipificados inspeccionan el rendimiento,
térmicas, servicios, almacenamiento, estado de la red local, Rust/Cargo y acotado
manifiestos del proyecto. Compilaciones, pruebas, cambios de dependencia y shell generado
Los comandos permanecen sujetos a la revisión exacta existente y a la seguridad del proyecto/host.
límites.

La actual expansión especializada también registra redes, seguridad,
y herramientas de inventario de recuperación. Inspeccionan interfaces/rutas/DNS locales,
SELinux/firewall/postura de arranque seguro y montajes/instantáneas/señales de recuperación de arranque;
no realizan controles externos ni mutaciones del huésped.

## Decisión de implementación solo por suscripción

El producto inicial debe funcionar con la suscripción ChatGPT existente del usuario y
no debe requerir el uso de la API OpenAI facturado por separado.

- Inicie `codex app-server` local y utilice su autenticación administrada por ChatGPT.
- Al iniciar, llame a `account/read`. Si se requiere autenticación, ofrezca la
  App Server `account/login/start` ChatGPT fluye y muestra el inicio de sesión devuelto
  instrucciones sin recopilar credenciales en Jarvis.
- Reutilizar la autenticación persistente y actualizada del Codex. Nunca copie sus tokens
  en el almacenamiento de Jarvis, registros, informes de fallos o argumentos de línea de comandos.
- No utilice la API de Respuestas, el SDK de API de OpenAI general ni los Agentes de OpenAI
  SDK en el producto predeterminado. Esas son diferentes integración y facturación.
  caminos.
- El paquete Python `openai-codex` es aceptable sólo como cliente para local
  Servidor de aplicaciones Codex con autenticación administrada por ChatGPT. No debe pasar silenciosamente a una
  Clave API.
- No configurar `OPENAI_API_KEY`, `CODEX_API_KEY`, compra de crédito automática,
  o cualquier respaldo pagado. Agregar uno más tarde requiere un cambio de configuración explícito
  y confirmación de usuario separada.

El uso del Codex todavía cuenta contra la asignación de Codex/agentic del plan. la tui
Por lo tanto, necesita una capa operativa solo local y un estado de capacidad visible en lugar de
que asumir que el modelo está siempre disponible.### Diseño consciente del uso sin reducir la confiabilidad

- Navegación, paneles de control, consultas SQLite, verificación de auditoría, política.
  Los formularios de evaluación, verificación de aprobación y procedimientos estáticos no constituyen ningún modelo.
  llamar.
- Las observaciones registradas recopilan y almacenan evidencia sin una llamada modelo.
  Invocar Codex sólo cuando el usuario solicite interpretación, diagnóstico, planificación,
  investigación o una acción que necesita el juicio de un agente.
- No sondees el Codex, no crees turnos en segundo plano ni inicies subagentes simplemente para mantener
  la interfaz actual.
- Utilice un hilo del Codex por incidente o trabajo coherente, no uno global permanente
  hilo. La base de conocimientos global de Jarvis proporciona una memoria duradera; recuperar
  solo hechos, fuentes, errores y lecciones relevantes para cada turno.
- Mantener un resumen de la tarea conciso y vinculado a la evidencia al finalizar. Reanudar el
  hilo cuando su contexto todavía es útil; de lo contrario, inicie un hilo limpio y
  proporcionar el resumen correspondiente.
- Utilice `model/list` en lugar de codificar un nombre de modelo. Oferta `Standard`,
  `Deep` y `Independent review` perfiles de trabajo basados en los modelos y el esfuerzo
  niveles realmente disponibles para la cuenta iniciada.
- Por defecto a un agente. Gastar turnos adicionales o subagentes solo para material
  incertidumbre, revisión de cambios de alto riesgo, evidencia contradictoria o
  selección de usuario.
- Lea la capacidad actual a través de `account/rateLimits/read` y escuche
  `account/rateLimits/updated`. Mostrar disponibilidad sin inventar un token
  o estimación de tareas que App Server no proporciona.
- Cuando la capacidad del Codex no esté disponible, mantener utilizables las vistas y controles solo locales.
  conservar el borrador de la solicitud y permitir que el usuario la reanude más tarde. Nunca cambie a un
  credencial API pagada automáticamente.

Esta división preserva la calidad: el trabajo determinista no consume cuota de agentes,
mientras que el modelo está reservado para trabajos donde la comprensión y el razonamiento del lenguaje
realmente agrega valor.

## Objetivos del producto

- Permita que el usuario se mueva naturalmente entre la conversación y las acciones estructuradas en
  la misma sesión.
- Haga que las operaciones simples y comunes sean detectables sin necesidad de que el usuario
  conozca Bash o recuerde las indicaciones exactas.
- Preservar la capacidad del agente para diagnosticar condiciones ambiguas o novedosas.
- Realice automáticamente lecturas claras de riesgo 0 y proyecto reversible exacto de riesgo 1
  crea/modifica.
- Requerir una aprobación exacta deliberada para riesgo-2+, eliminación, mutación del huésped,
  privilegios, tiempo de inactividad, trabajos sensibles a la seguridad y efectos externos.
- Mostrar lo que se conoce, lo que se infiere, lo que está obsoleto, lo que está dentro del ámbito de la zona de pruebas, lo propuesto, lo aprobado,
  ejecutados y verificados como estados diferentes.
- Mantenga rastreable cada decisión operativa sin almacenar el modelo privado
  razonamiento.
- Apoyar una transición posterior de un prototipo de lenguaje natural a un
  Consola de estación de trabajo completa y dedicada sin reemplazar el plano de control.

## No objetivos explícitos para la primera implementación

- No hay un indicador de shell no clasificado dentro de la TUI.
- Sin shell raíz persistente, `sudo` directo aprobado automáticamente ni ruta de omisión de políticas.
- No se permiten escrituras SQLite directas desde vistas o widgets.
- Ninguna mutación con alcance de procedimiento, de transacción o preautorizada.
- No hay reintentos automáticos después de una salida fallida o inesperada.
- No se permite el uso del servidor de aplicaciones `thread/shellCommand` o experimental `process/*` como
  ejecutor de administración de host.
- No se puede afirmar que un plan generado, una aprobación del servidor de aplicaciones o una salida exitosa
  El código es equivalente a un resultado operativo verificado.

## Forma del sistema```text
teclado/catálogo de acciones/programador futuro
                    |
                    v
        +-------------------------+
        | jarvis-tui              |
        | presentation + consent  |
        +------------+------------+
                     | typed local protocol
                     v
        +-------------------------+
        | jarvisd                 |
        | session + task broker   |
        | policy + event reducer  |
        +---+----------+----------+
            |          |
    JSON-RPC|          |deterministic calls
            v          v
   +----------------+  +----------------------+
   | Codex          |  | Jarvis control plane |
   | app-server     |  | policy / knowledge   |
   | threads/turns  |  | approval / audit     |
   +-------+--------+  +----------+-----------+
           |                      |
| PCM | futuros adaptadores estrechos únicamente
           +-----------+----------+
                       v
          registered collectors / future executor
```### `jarvis-tui`

La interfaz procesa datos, recopila parámetros, transmite eventos y captura
consentimiento explícito. No tiene API de shell, privilegios, capacidad de escritura de políticas,
conexión de base de datos o identificador de ejecutor sin formato. Un widget comprometido no debe ser
capaz de autorizar una operación.

### `jarvisd`

El intermediario local es el límite de autoridad de la aplicación. Eso:

- posee sesiones TUI, estado de tareas y claves de idempotencia;
- inicia o se conecta al Codex App Server;
- asigna ID de subprocesos, giros, elementos y solicitudes de App Server a ID de Jarvis;
- valida esquemas de acción y resuelve versiones de procedimientos;
- llama a las funciones deterministas de política y aprobación de Jarvis;
- rechaza intentos de ejecución no registrados;
- escribe registros de auditoría y decisiones redactados a través del plano de control;
- reconstruye el estado de la vista a partir de eventos después de un accidente;
- eventualmente invoca sólo adaptadores de ejecutor registrados.

Para el prototipo, puede ejecutarse en el mismo proceso que la interfaz detrás de un
interfaz estricta. Antes de agregar la mutación supervisada, divídala en una sección separada.
Servicio sin privilegios accesible a través de un socket Unix privado. El protocolo debe
permanecen idénticos en ambas implementaciones.

### Servidor de aplicaciones Codex

App Server proporciona autenticación, subprocesos persistentes, turnos, transmisión de elementos,
planes, solicitudes de entrada de usuarios, solicitudes de aprobación de archivos/comandos, interrupciones y
eventos de error. Genere esquemas JSON o TypeScript a partir del instalado exactamente
Versión del Codex y fijar el protocolo compatible en las pruebas.

Utilice la API estable de forma predeterminada. Las capacidades experimentales requieren un análisis separado.
decisión de arquitectura, indicador de característica, prueba de compatibilidad y degradado visible
modo cuando no esté disponible.

Para la compilación de solo suscripción, el corredor inicia App Server sobre su
Transporte estándar JSONL predeterminado. Esto evita exponer a un oyente de la red y no
no depende del transporte experimental WebSocket. Un proceso TUI separado puede
hablar con `jarvisd` a través del protocolo privado de socket Unix de Jarvis; Servidor de aplicaciones
puede seguir siendo un proceso hijo propiedad del corredor.

### Jarvis MCP y plano de control

Codex utiliza el servidor MCP existente para herramientas de gobierno y conocimiento escrito.
El corredor aún debe hacer cumplir la política fuera del modelo. Una instrucción como
"llamar primero a la herramienta de políticas" mejora el comportamiento del agente pero no es una medida de seguridad
límite.

Agregue futuras herramientas de observación y ejecución solo después de sus contratos de adaptador.
están completos:

- `observe_registered`: plantillas ejecutables/argumentos fijas, de solo lectura,
  salida limitada, tiempo de espera, redacción, un intento;
- `propose_action`: valida y almacena un contexto de acción exacto pero no puede ejecutarse
  eso;
- `execute_approved_action`: acepta únicamente un producto válido, vigente, no consumido,
  aprobación estatal y revisión del adaptador registrado;
- `verify_action`: ejecuta una validación independiente y registra el resultado.

## Un canal para ambos estilos de interacción

### Ruta del lenguaje natural

1. El usuario envía texto.
2. El corredor registra la fuente del texto como `natural_language` y lo envía al
   hilo activo del Codex.
3. El Codex podrá responder de forma conversacional o proponer una tarea estructurada.
4. El corredor valida cada capacidad, procedimiento, parámetro y
   objetivo. Los valores desconocidos o ambiguos vuelven a la aclaración o planificación.
5. Se aplican las puertas de política ordinaria y de ciclo de vida.

### Ruta del catálogo de acciones

1. El usuario selecciona una acción registrada y completa el formulario escrito.
2. El corredor registra la fuente como `catalog_action`, resuelve la acción exacta
   y versiones de procedimientos, y valida los campos localmente.
3. Compila una solicitud canónica, legible por humanos, además de metadatos estructurados y
   envía esa solicitud al mismo hilo activo del Codex.
4. Codex recibe el contexto de la conversación actual y puede diagnosticar, explicar,
   planifique o solicite información faltante.
5. Se aplican las mismas políticas y límites del ciclo de vida.Por lo tanto, una entrada de catálogo es una plantilla de intención, no un Bash almacenado. Seleccionando
"Diagnosticar brillo" le pide al agente que siga el brillo registrado
procedimiento de diagnóstico; no ejecuta inmediatamente un comando recordado.

### Transiciones contextuales

La salida del agente puede incluir sugerencias de acciones validadas. Por ejemplo:```text
User: My brightness controls stopped working.
Agent: Three causes fit the current evidence.
Suggested actions:
  [Collect display/backlight evidence]  [Inspect recent updates]  [Keep planning]
```Seleccionar una sugerencia crea un seguimiento estructurado en el mismo hilo. el
El usuario puede luego volver al texto libre sin perder el diagnóstico o su evidencia.
enlaces.

## Contratos de datos básicos

Los siguientes nombres describen contratos, no la sintaxis de almacenamiento final.

### `IntentEnvelope````json
{
  "intent_id": "uuid",
  "session_id": "uuid",
  "source": "natural_language | catalog_action | contextual_action | automation",
  "requested_mode": "observe | diagnose | plan | execute | verify | recover | learn",
  "text": "optional user text",
  "action_id": "optional registry id",
  "action_version": "optional exact version",
  "parameters": {},
  "constraints": [],
  "created_at": "RFC3339 timestamp"
}
```### `ActionDefinition````json
{
  "id": "health.brightness.diagnose",
  "version": "1.0.0",
  "title": "Diagnose brightness controls",
  "capability": "health",
  "procedure": "health.assess@1.0.0",
  "mode": "diagnose",
  "input_schema": {},
  "required_facts": [],
  "risk_floor": 0,
  "mutates_host": false,
  "availability": "enabled | disabled | unavailable",
  "unavailable_reason": null
}
```El registro posee definiciones de acciones y sus metadatos de interfaz de usuario. La TUI construye su
menús del registro para que las capacidades mostradas no puedan desviarse de la política.
Las acciones discapacitadas e inmaduras siguen siendo visibles con una razón; ocultarlos sería
hacer que los límites del sistema sean difíciles de entender.

### `TaskRecord`

Una tarea vincula la intención normalizada a:

- Codex `threadId`, `turnId` y valores `itemId` pertinentes;
- versiones exactas de capacidad, acción y procedimiento;
- resúmenes de evidencias y instantáneas del estado;
- resultado de la política y advertencias materiales;
- comandos propuestos y resúmenes de acciones;
- solicitud de aprobación, decisión, nonce, vencimiento y estado de consumo;
- ID de intento de ejecución;
- resultados de validación y recuperación;
- resumen conciso de la decisión final.

El registro no almacena ninguna cadena de pensamiento privada.

## Máquina de estado de tareas```text
captured
   -> resolving_intent
   -> needs_clarification ------+
   -> preflight                 |
   -> planning <---------------+
   -> blocked
   -> awaiting_approval
   -> approved
   -> executing
   -> verifying
   -> completed

From planning/executing/verifying:
-> diagnosticando_resultado_inesperado -> replanificación
-> planificación_recuperación -> esperando_aprobación_recuperación
   -> cancelled | failed
```Sólo el intermediario cambia el estado de la tarea. La navegación de la interfaz de usuario nunca cambia el estado de la tarea.
Cada transición tiene un ID de evento, marca de tiempo, actor, código de motivo y enlaces a
su evidencia de entrada.

## Modelo de homologación en la TUI

La aprobación del Codex Sandbox y la aprobación operativa de Jarvis son independientes:

- **La aprobación del Codex** decide si una herramienta o comando de App Server puede cruzar su
  límite actual de zona de pruebas/herramienta.
- **La aprobación de Jarvis** autoriza un comando operativo exacto bajo el
  Política de Jarvis versionada y resumen del estado actual del sistema.

Una pantalla puede explicar que se aplican ambas puertas, pero nunca se debe tomar una decisión.
copiado silenciosamente en el otro. Una acción de cambio de estado no puede proceder simplemente
porque App Server emitió una solicitud de aprobación y el usuario la aceptó.

La pantalla de aprobación inicial de Jarvis muestra:

- ejecutable exacto y `argv[]`, con una representación Bash con escape independiente;
- directorio de trabajo, lista de claves permitidas del entorno y objetivos exactos;
- versiones de capacidades, procedimientos y adaptadores;
- mutación, privilegio, red, efecto externo, tiempo de inactividad, destructivo,
  banderas irreversibles y de actualización automática;
- riesgos calculados y razones políticas;
- evidencia/edad del estado y resumen del estado;
- resultados y efectos esperados, tiempo de espera, validación, reversión y ejecución en seco;
- nonce, vencimiento, alcance y estado de uso único.

De forma predeterminada, no se selecciona ninguna opción de aprobación. Aprobar, rechazar, cancelar e inspeccionar
utilizar claves distintas. La entrada pegada no puede confirmar una aprobación. Procedimiento y
Las opciones de transacción se muestran como deshabilitadas hasta que la política las habilite explícitamente.
ellos.

## Modelo de pantalla recomendado```text
+------------------+-----------------------------------------------+
| Overview         | Session: Brightness diagnosis                |
| System           |-----------------------------------------------|
| Actions          | conversation / plan / evidence cards         |
| Knowledge        |                                               |
| Errors           |                                               |
| Lessons          |                                               |
| Plans            |-----------------------------------------------|
| Approvals        | prompt > Ask or choose an action...           |
| Timeline         +-----------------------------------------------+
| Recovery         | OBSERVE | policy OK | facts: 12m | audit OK   |
| Settings         | Codex connected | no pending approval         |
+------------------+-----------------------------------------------+
```El diseño se colapsa en un panel más una paleta de comandos en terminales angostos.
Cada color tiene un texto o símbolo equivalente. Uso exclusivo del teclado, cambio de tamaño y pantalla
Se aceptan salida simple fácil de leer y recuperación después de la pérdida del terminal.
requisitos.

### Elementos esenciales de interacción

- Compositor con edición multilínea y envío explícito.
- Paleta de acciones que se puede buscar por resultado, síntoma, capacidad y riesgo.
- Formularios de parámetros escritos generados a partir del esquema JSON.
- Flujo de conversación con usuario, agente, herramienta, evidencia, advertencia y
  Tarjetas de respuesta final.
- Vista del plan impulsada por los eventos del plan de App Server pero conciliada con el plan final
  artículo.
- Inspector de pruebas que vincula las afirmaciones con hechos, documentos, intentos y
  procedencia de la fuente.
- Pantalla de aprobación exacta, nunca un genérico "¿Estás seguro?" diálogo.
- Vista de salida en vivo con separación stdout/stderr, límites de tamaño, redacción y un
  etiqueta clara del alcance de observación.
- Control de cancelación/interrupción persistente.
- Banner de recuperación para App Server desconectado, solicitud no resuelta, corrupta
  cadena de auditoría, cifrado bloqueado o estado obsoleto.

## Seguridad de comando y salida

- Representar internamente comandos como ejecutables más `argv[]`; nunca construyas
  texto de shell concatenando la entrada del usuario.
- Mostrar la sintaxis del shell solo como una representación escapada para su revisión.
- Tratar la salida de comandos, registros, documentación, metadatos de paquetes, títulos de terminales,
  hipervínculos y texto pegado como datos no confiables.
- Quite o escape visiblemente las secuencias ANSI CSI/OSC/control antes de renderizar a
  Evitar la inyección de escape terminal.
- No haga que las URL o rutas de archivos sean ejecutables al hacer clic de forma predeterminada.
- Limite la visualización en vivo y el almacenamiento de forma independiente. El truncamiento debe ser visible y
  preservar el resumen del registro permitido completo.
- Nunca envíe automáticamente texto pegado y avise antes de aceptar un texto grande o de varias líneas
  pegar.
- Si la salida viola una expectativa, registre el único intento, deténgase, ingrese
  Diagnosticar y requerir un nuevo plan y aprobación. No muestre el botón Reintentar.

## Comportamiento de sesión y persistencia

- Una sesión de Jarvis normalmente se asigna a un hilo del Codex reanudado.
- Almacenar hilos y girar identificadores, pero tratar el historial de implementación del Codex como contexto.
  no la autoridad de auditoría.
- Persistir en los eventos de tareas/UI antes de reconocer las transiciones que cambian de estado.
- Al reiniciar, reconstruir la última vista segura a partir de la secuencia de eventos y consultar
  Servidor de aplicaciones para el estado del hilo.
- Nunca asuma que una solicitud pendiente sigue siendo válida después de volver a conectarse. reconciliarlo
  a través del estado de aprobación de App Server y Jarvis.
- Caducar las aprobaciones no consumidas por discrepancia de estado, reiniciar el proceso cuando sea necesario,
  revisión de política, revisión de adaptador o tiempo de espera.
- Mantener el material de autenticación en el almacén de credenciales admitido del Codex. no
  copiar tokens en la base de datos de Jarvis, registros, visualización del entorno o falla
  informes.

## Fallos y modos degradados

| Fracaso | Comportamiento requerido |
|---|---|
| Servidor de aplicaciones no disponible | Conversación deshabilitada; la historia local sigue siendo legible |
| App Server se desconecta a mitad de turno | Marcar incierto, volver a conectar, leer el estado del hilo, nunca reproducir la entrada automáticamente |
| El corredor se reinicia | Reconstruir a partir de eventos; aprobaciones permanecen sin consumir o caducan según la política |
| TUI se bloquea | Restaurar terminal; el apagado no activa ninguna ejecución |
| Jarvis MCP no disponible | Falla cerrada para tareas operativas |
| Base de datos de conocimientos bloqueada | Mostrar modo degradado de solo lectura; no crear almacenamiento sustituto |
| La verificación de auditoría falla | Bloquear mutación y mostrar guía de recuperación |
| Pruebas obsoletas | Explicación del permiso; bloquear la acción hasta que la política la actualice o la maneje explícitamente |
| Salida inesperada | Registre una vez, diagnostique, replanifique; sin reintento automático |
| No coincide el esquema/la versión | Rechazar funciones no compatibles y mostrar versiones requeridas/observadas |

## Decisión tecnológica

### Primera implementación recomendada: Python + Textual

Razones:- el plano de control, el almacén de conocimientos, las pruebas y el SDK oficial de Codex Python son
  ya compatible con Python;
- Textual es asincrónico y proporciona pruebas de interacción sin cabeza, lo que se adapta
  eventos de App Server transmitidos y pruebas de estado de aprobación;
- Los objetos de dominio Python escritos pueden ser compartidos por el intermediario y la interfaz de usuario del prototipo;
- Minimiza el trabajo de integración mientras que la seguridad y la interacción se contraen.
  todavía están cambiando.

Esta es una elección de entrega, no una decisión de confianza. El código textual permanece afuera.
el límite de la autoridad.

### Alternativa posterior: Rust + Ratatui

Considere una interfaz Ratatui después de que el protocolo se estabilice si un pequeño nativo
binario, un uso más estricto de los recursos o la portabilidad del terminal a largo plazo justifican una
reescribir. Ratatui ofrece un backend de prueba y primitivas de terminal sólidas, pero un
reescribir ahora duplicaría la integración existente de Python y ralentizaría la validación
del diseño de políticas y aprobación más importante.

### No seleccionado inicialmente: TypeScript + Tinta

Ink se alinea con el SDK de TypeScript Codex y las habilidades de React, pero agrega una segunda
tiempo de ejecución de la aplicación sin una ventaja clara sobre Textual para este Python pesado
paquete. Reconsiderar solo si la aplicación luego se estandariza en TypeScript
back-end.

## Fases de entrega

### Fase 0: decisiones arquitectónicas y accesorios

- Aprobar este modelo de límites y redactar registros de decisiones de arquitectura.
- Definir `IntentEnvelope`, `ActionDefinition`, `TaskRecord`, evento y corredor
  esquemas de protocolo.
- Ampliar el registro de procedimientos existente con metadatos de UI escritos.
- Crear conversaciones fijas, selecciones de acciones, aprobaciones, inesperadas.
  salida, se desconecta y se reinicia.
- Fijar el protocolo mínimo compatible Codex/App Server y generar esquemas.

Salir: la validación del esquema pasa y ningún componente puede expresar la ejecución sin formato.

### Fase 1: corredor de solo lectura

- Implementar el inicio del App Server sobre stdio, inicialización, administrado por ChatGPT
  visualización/inicio de sesión del estado de autenticación, visualización del límite de velocidad, inicio/reanudación del hilo, giro
  arranque/dirección/interrupción y normalización de eventos.
- Implementar la API del agente local y el diario de eventos de tareas/UI de solo anexo.
- Conecte consultas de conocimiento de solo lectura y listado de capacidades actuales.
- Añadir correlación estricta de eventos e idempotencia.

Salir: un cliente sin cabeza puede conversar, reanudar, cancelar y recuperarse de una sesión forzada.
desconéctese sin ejecutar comandos de Fedora o usar una clave API.

### Fase 2: TUI MVP híbrido

- Cree vistas de descripción general, conversación, acciones, conocimiento, plan y cronograma.
- Agregue entradas en lenguaje natural y formularios de acción generados por esquemas.
- Compilar selecciones de catálogo en el mismo hilo del Codex.
- Representar mensajes de agentes, planes, elementos de herramientas, advertencias y estados finales transmitidos.
- Agregue desinfección de terminales, límites de salida, manejo de cambio de tamaño y limpieza de fallos.

Salida: solicitudes equivalentes de lenguaje natural y catálogo convergen en un
tarea normalizada equivalente y resultado de política.

### Fase 3: aprobaciones sin mutación del huésped

- Representar solicitudes de App Server y aprobaciones de Jarvis como objetos distintos.
- Implementar la pantalla de aprobación exacta y el ciclo de vida nonce/digest/expirity.
- Utilice únicamente adaptadores simulados; prueba aceptar, rechazar, cancelar, tiempo de espera, reproducir,
  estado obsoleto, enmiendas y solicitudes concurrentes.
- Rechazar intentos de comando sin procesar o no registrados.

Salida: las pruebas contradictorias no pueden eludir, reutilizar, ampliar o confundir una aprobación.

### Fase 4: observaciones registradas de solo lectura

- Agregar `observe_registered` detrás del registro de recopiladores existente.
- Admitir automáticamente sólo comandos que la política determinista haya demostrado ser válidos.
  de bajo riesgo y de solo lectura.
- Intento de récord, expectativas de salida, alcance de observación y frescura.
- Comience con accesorios, luego use solo adaptadores de solo lectura registrados limitados en el
  estación de trabajo real. Una VM Fedora desechable es opcional para el representante
  observaciones solo de software y no pueden sustituir el hardware físico
  evidencia.Salida: cada observación está delimitada, redactada, atribuida, auditable y se detiene.
después de una salida inesperada.

### Fase 5: fundación de mutación supervisada

- Diseñar un servicio ejecutor estrecho y un protocolo adaptador.
- Prefiere un servicio de propiedad raíz con Polkit o una autorización de sistema operativo equivalente
  límite sobre darle a la TUI, al intermediario o al modelo un shell raíz.
- Implemente un adaptador tipo reversible de bajo radio de explosión detrás del externo
  límite de autorización. Ensayarlo con fijos y un scratch aislado
  VM de destino o representativa opcional, luego requiere recuperación de acción específica
  y aprobación exacta para su primer uso de estación de trabajo supervisada.
- Requerir la aprobación de Jarvis con alcance de comando, evidencia previa al cambio, recuperación,
  validación posterior a la condición y revisión independiente.

Salida: el adaptador único cumple con la etapa de capacidad 4. Ninguna otra mutación hereda
esa madurez.

### Fase 6: consola operativa completa

- Agregar errores, lecciones, recuperación, configuraciones, integridad de auditoría, estado de cifrado,
  y vistas de estado del receptor remoto.
- Agregue acciones recomendadas contextuales y vincule cada recomendación con
  revisiones de pruebas y procedimientos.
- Agregue informes de incidentes y mantenimiento exportables y redactados.
- Agregue notificaciones de escritorio opcionales sin permitirles aprobar el trabajo.

Salir: todas las vistas en `tui-contract.md` cumplen con funcionalidad, accesibilidad, privacidad,
y pruebas de aceptación de recuperación.

### Fase 7: aumento de la autonomía

- Observar los procedimientos exitosos el tiempo suficiente para generar evidencia independiente.
- Promover sólo revisiones explícitas de procedimientos a través de la madurez de la capacidad.
  modelo.
- Mantenga desactivada la lista segura preautorizada hasta que se apruebe una política de etapa 5.
- Nunca infieras una autoridad amplia a partir del uso repetido o de una lección activa.

Salida: la autonomía es específica del procedimiento, limitada, revocable, monitoreada y
recuperable.

## Estrategia de prueba

### Pruebas unitarias y de propiedades

- Validación de esquemas y serialización canónica.
- Estabilidad del resumen de comando/acción.
- Clasificación de riesgos y monotonicidad de políticas.
- Vencimiento de la aprobación, rechazo de repetición, vinculación de objetivos y vinculación de estado.
- Determinismo e idempotencia del reductor de eventos.
- ANSI/neutralización y redacción de secuencias de control.
- Generación de registro a menú y motivos de estado deshabilitado.

### Pruebas de integración

- Flujos de eventos falsos de App Server, incluidos eventos duplicados y desordenados.
- Real App Server con un hogar temporal de Codex y esquemas versionados generados.
- Convergencia entre lenguaje natural y catálogo de acciones.
- Reanudar hilo, girar dirección, interrupción, compactación y reconexión.
- La aprobación de App Server y la aprobación de Jarvis se muestran sin confusión de alcance.
- Base de datos bloqueada, inicio fallido de MCP y comportamiento corrupto de la cadena de auditoría.

### pruebas TUI

- Flujos de trabajo de teclado sin cabeza e instantáneas en varios tamaños de terminal.
- No hay enfoque predeterminado en la aprobación.
- Pegar no puede enviar ni aprobar.
- Cancelar permanece accesible mientras se transmite la salida.
- El modo simple/sin color lleva toda la semántica de estado.
- El modo terminal y el cursor se restauran después de la salida normal y el bloqueo simulado.

### Pruebas de seguridad

- Inyección rápida en registros, descripciones de paquetes, documentación y salida MCP.
- Secuencia de escape y salida de hipervínculos maliciosos.
- Inyección de parámetros de acción y preservación de límites de argumentos.
- Aprobaciones falsificadas, obsoletas, reproducidas, ampliadas y entre sesiones.
- Reemplazo de enlace simbólico/ruta entre planificación y ejecución.
- Simulaciones de compromiso de corredor/TUI que demuestran que no existe ningún canal privilegiado sin procesar.

## Criterios de aceptación de lanzamiento- Ambos estilos de entrada comparten una conversación y un proceso de tareas normalizados.
- El catálogo de acciones se genera a través del registro y tiene en cuenta la versión.
- Un proceso de interfaz no puede ejecutar un comando de host ni mutar almacenes de autoridad.
- Cada acción propuesta tiene un objetivo exacto, riesgo, evidencia, validación y
  estado de recuperación.
- Cada cambio de estado requiere una aprobación de comando exacta en la versión inicial.
- Las aprobaciones de App Server y Jarvis no se pueden confundir entre sí.
- Ningún resultado inesperado provoca un reintento o progresión automática.
- Las pruebas de bloqueo/reconexión no dejan una ejecución ambigua ni una aprobación consumida.
- Falla de auditoría, estado obsoleto, secretos bloqueados o fallas de gobierno no disponibles
  cerrado por mutación.
- La documentación indica qué capacidades permanecen simuladas, no implementadas o
  no verificado en la estación de trabajo en vivo.

## Primera porción de implementación

La porción útil más pequeña debe contener únicamente:

1. un corredor privado local;
2. Conexión/inicio del servidor de aplicaciones, inicio/reanudación del subproceso, un turno transmitido y cancelación;
3. un caparazón textual con descripción general, conversación, acciones y línea de tiempo;
4. entrada en lenguaje natural;
5. tres acciones no ejecutables: explicar el estado del sistema, buscar conocimiento local,
   y preparar un plan de control de salud;
6. esquemas normalizados de tareas y eventos de UI;
7. Pruebas de servidor falso, TUI sin cabeza, redacción y reconexión.

También incluye un dispositivo fuera de línea/con capacidad agotada que demuestra que todos los locales
las vistas aún funcionan y las indicaciones en cola no se reproducen automáticamente.

Ese segmento valida el modelo de interacción antes de introducir incluso el de solo lectura.
coleccionistas anfitriones.

### Punto de control de preparación implementado

Este punto de control fue reemplazado el 18 de agosto de 2026 por el canal de autoridad unificado.
Los documentos de la fase anterior son historial de diseño y no definen la TUI actual.
comportamiento en tiempo de ejecución. La autoridad actual está definida por `tui-contract.md`,
`shared-contract.md` y el código/configuración que se menciona a continuación.

El repositorio ahora contiene:- esquemas escritos de intención, acción, tarea y evento de corredor;
- el esquema JSON estable del servidor de aplicaciones generado y anclado a
  `codex-cli 0.146.0`, además de pruebas de compatibilidad para cada método permitido y
  valor de transferencia relevante para la seguridad;
- descubrimiento de acciones generadas por el registro y captura de parámetros basada en esquemas;
- una ruta de normalización para solicitudes de catálogo y lenguaje natural;
- un cliente stdio de App Server que admite ChatGPT administrado o autenticación de clave API y
  denegar todos los métodos fuera de la cuenta fijada/hilo/lista permitida de turnos;
- inicio/reanudación de subprocesos, verificación previa escrita, turnos de ejecución opcionales, exacto
  respuestas de comando/archivo e interrupción; la dirección de giro activo está desactivada;
- contexto de conversación limpio activo sincronizado a través del anclado
  Método `thread/inject_items`, con un límite de 64.000 caracteres, intercambio completo
  poda, épocas de hilo nuevo y sin persistencia de resultados locales en JARVIS;
- reducción de eventos normalizada, estado derivado del ciclo de vida para elementos sin estado,
  neutralización de terminales, correlación y manejo de duplicados o fuera de servicio;
- reservas de envío de tareas atómicas, recuperación solo de metadatos y no automática
  repetición rápida;
- capacidad de solo lectura, acción y acceso al conocimiento que nunca inicializa un
  tienda perdida;
- un diario de corredor privado encadenado y neutralización de salida de terminal;
- la descripción textual inicial, las acciones, la conversación/línea de tiempo, el compositor y
  diseño de estado;
- la descripción general completa, la conversación, las acciones, el conocimiento, el plan y la fase 2
  Vistas de línea de tiempo, estado de presentación determinista, modal generado por esquema
  formularios, navegación por teclado, modo simple y pruebas de interacción sin cabeza;
- evaluación mecanografiada determinista y admisión con lectura local y alcance
  ejecución, aclaración y resultados bloqueados;
- `dangerFullAccess` como usuario actual del sistema operativo con revisión del Codex `untrusted`,
  lecturas automáticas exactas de la red, confirmación de riesgo 2+ de un solo uso, coincidencia de objetivos,
  negaciones permanentes y no opciones de aprobación persistentes;
- una vista de Aprobaciones para solicitudes de archivos/comandos reales de App Server; el primero
  la superficie de simulación ya no está conectada a la TUI;
- un caso de uso y accesorios preparados para brillo de pantalla/iluminación de teclado;
- un laboratorio de escenario/sistema gemelo Fedora solo con dispositivos fijos y con un host no observado
  perfil, bloqueo de imagen oficial no resuelto, políticas de aislamiento/restablecimiento/promoción,
  37 regresiones seleccionadas, 64 512 casos de estado de iluminación, 60 480 planos de control
  casos estatales y diez brechas físicas explícitamente abiertas.
- un futuro controlador de VM solo por contrato con 18 operaciones escritas deshabilitadas y un
  propuesta no aprobada de inscripción de estaciones de trabajo de 90 hechos en 32 personas discapacitadas,
  Definiciones de fuentes fuera de línea, no mutantes y tres niveles de consentimiento.

La validación de Real App Server y la implementación de ayuda privilegiada siguen siendo el entorno
puntos de control. La validación de dispositivos cubre las respuestas de aprobación del servidor de aplicaciones y las escritas.
admisión. El aprovisionamiento real de VM es opcional y no una puerta de finalización.
La conexión y el envío de ejecución permanecen desactivados de forma predeterminada y requieren
indicadores CLI explícitos.

## Hoja de ruta desde el punto de control actual hasta su finalización| Fase | Estado | Puerta de finalización |
|---|---|---|
| 0 — arquitectura y accesorios | completo | validan esquemas y fijaciones libres de ejecución |
| 1 - corredor de solo lectura | accesorio completo; aceptación en vivo diferida | la prueba de humo explícita ejecutada por el usuario confirma la conexión, reanudación, transmisión, interrupción y desconexión del servidor de aplicaciones instalado sin un comando de Fedora |
| 2 — híbrido TUI MVP | completo; dispositivo validado | todas las vistas principales y las pruebas de interacción sin cabeza pasan; lenguaje natural y acciones de catálogo convergen en el mismo límite sin autoridad de host |
| 3 — aprobaciones sin mutación | completo; dispositivo validado | pruebas contradictorias de aprobación simulada demuestran alcance exacto, vencimiento, vinculación de estado/política/adaptador, invalidación de enmiendas, entrada deliberada y rechazo de repetición |
| 4 — observaciones registradas | Contratos L0 y L1 completos; estación de trabajo H1 registrada; integración del adaptador TUI mecanografiado pendiente | los accesorios y la evidencia limitada del anfitrión real demuestran observaciones redactadas en un solo intento que se detienen en las sorpresas; la cobertura opcional de VM es específica de la capacidad |
| 5 — mutación supervisada | planeado | un adaptador de tipo reversible alcanza la etapa de madurez 4 detrás de un límite de autorización de sistema operativo separado con recuperación verificada y aprobación exacta; El ensayo de VM es opcional cuando es representativo |
| 6 — consola operativa | planeado | cada vista de contrato pasa las pruebas de aceptación de función, accesibilidad, privacidad, integridad y recuperación ante fallas |
| 7 — autonomía limitada | previsto, inicialmente apagado | sólo las políticas de etapa 5 específicas del procedimiento pueden ingresar a una lista segura revocable después de revisar la evidencia y la aprobación explícita del usuario |

El producto definitivo estará completo sólo cuando pasen las puertas de la consola de la Fase 6 y
los adaptadores operativos elegidos han pasado individualmente la Fase 5. La Fase 7 es una
vía de madurez opcional, no es un requisito previo para una liberación supervisada segura. No
La capacidad se vuelve confiable simplemente porque se completó una fase anterior.

La evidencia estructural de la Fase 4 y los puntos de control restantes L1-L7 están documentados.
en `phase-4-vm-lab-prerequisite.md` y `../vm-lab/README.md`. Accesorio
la cobertura tiene un límite al vencimiento en la Etapa 1; no puede sustituir a un huésped real o
evidencia física de la estación de trabajo.
El subpunto de verificación del controlador/inscripción está documentado en
`phase-4-l1-controller-enrollment.md`; su propuesta preparada no otorga
autoridad de observación.

## Referencias oficiales y primarias

- Servidor de aplicaciones Codex: https://learn.chatgpt.com/docs/app-server
- SDK de Codex Python y TypeScript: https://learn.chatgpt.com/docs/codex-sdk
- Acceso al Codex a través de planes ChatGPT:
  https://help.openai.com/en/articles/11369540-using-codex-with-chatgpt
- Uso y créditos flexibles (opcional, no habilitado por este diseño):
  https://help.openai.com/en/articles/12642688
- Aprobación del Codex y modelo sandbox:
  https://learn.chatgpt.com/docs/agent-approvals-security
- Configuración del Codex MCP: https://learn.chatgpt.com/docs/extend/mcp
- Prueba textual: https://textual.textualize.io/guide/testing/
- Conceptos de Ratatui y backend de prueba: https://ratatui.rs/concepts/backends/
