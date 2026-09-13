# Fase 2 híbrido TUI MVP

> Registro histórico de diseño. No define la autoridad actual de la TUI. Ver
> `current-product-state.md` y `tui-contract.md`.

## Resultado

La fase 2 está implementada y validada. Jarvis ahora tiene un navegable
Interfaz de terminal textual que combina solicitudes de formato libre y catálogo versionado.
acciones, búsqueda de conocimiento local, conversación transmitida, planes y un auditable
línea de tiempo. Ambos estilos de solicitud ingresan al mismo límite de admisión del corredor.

Esta fase no agrega autoridad de anfitrión. No ejecutó la aplicación Codex real.
Servidor, envíe un turno de modelo en vivo, inspeccione Fedora, ejecute la iluminación preparada
canalización, ejecutar un recopilador, instalar un tiempo de ejecución del proyecto, aceptar una aprobación o
invocar un comando. La única instalación textual utilizada durante el desarrollo de este
La fase era un entorno virtual desechable aislado según `/tmp`.

## Puente de estado de fase 2B

La TUI ahora tiene una opción explícita `--connect-jarvisd` para estado de solo lectura
proyección. Comprueba el socket Unix exclusivo del propietario y llama únicamente a `health.read`
y `activation.status`. La descripción general muestra el estado del servicio H1 Tier-0 y
el alcance local aprobado más evidencia de recuperación R1/R2 redactada (estado,
recuento de discrepancias y recuento de lagunas de pruebas); no puede llamar a `observation.prepare`,
persistir hechos, ejecutar comandos o modificar políticas. También muestra el
resultado redactado del ensayo de la Fase 5 y estado de reversión; este es el estado
Solo proyección y no crea un método ejecutor. El modo sin conexión permanece
el valor predeterminado.

## Interfaz entregada

El MVP tiene seis vistas accesibles mediante teclado:

1. **Descripción general** muestra el estado del servidor de aplicaciones, el modo de autenticación ChatGPT, el hilo y
   estado de giro, solicitudes de servidor pendientes, capacidad, recuentos de registros locales,
   estado de conocimiento de solo lectura, metadatos de tareas recuperadas y seguridad actual
   límite.
2. **Conversación** combina solicitudes en lenguaje natural, solicitudes de catálogo,
   mensajes de agente transmitidos, estados de tareas de terminal, avisos seguros y bloqueados
   Solicitar advertencias.
3. **Acciones** se genera a partir de `registry/actions.json`. La búsqueda filtra el
   catálogo, las entradas no disponibles conservan su motivo y las acciones habilitadas abren un
   formulario generado a partir de su esquema de entrada JSON.
4. **Conocimiento** consulta la base de datos de conocimiento existente en SQLite de solo lectura
   modo por hechos, fuentes, intentos, errores, lecciones o decisiones. un desaparecido
   store se informa y nunca se inicializa.
5. **Plan** presenta deltas de planes limitados, mensajes de planes autorizados y
   estados de paso estructurados.
6. **Cronología** intermediario limitado de proyectos y ciclo de vida normalizado del servidor de aplicaciones
   eventos sin mostrar cargas útiles del diario sin procesar.

La navegación global está disponible a través de `Ctrl+1` a `Ctrl+6`. `Escape` devuelve
centrarse en el compositor y `Ctrl+X` solicita interrupción sólo cuando se realiza un turno.
activo. El modo simple conserva el estado a través de etiquetas explícitas en lugar de depender
en color.

## Un límite de admisión

Las entradas de forma libre y de acción se capturan como `TaskRecord` escrito y
luego recibe un `TaskAdmission` inmutable. El resultado de la admisión incluye el
ruta, decisión, identidad exacta de acción/procedimiento cuando esté presente, política de zona de pruebas,
resumen de políticas y estos campos no negociables:```text
host_authority = none
execution_authorized = false
```Las rutas de la Fase 2 son:

| Ruta | Trabajo elegible | Efecto |
|---|---|---|
| `local_read` | Lecturas registradas que no son agentes, como `knowledge.search` | Consultar el almacén de conocimiento del proyecto existente como de solo lectura; nunca contacte al servidor de aplicaciones |
| `agent_conversation` | Solicitudes en lenguaje natural y acciones de razonamiento registradas no mutantes | Puede ingresar al mismo hilo del Codex de solo lectura solo cuando ambas puertas en vivo están habilitadas |
| `blocked` | Cualquier acción mutante del huésped que alcance la admisión | Denegar antes del enrutamiento del servidor de aplicaciones |

Un turno activo acepta un seguimiento a través de `turn/steer` con el exacto
`expectedTurnId`. El seguimiento aún se captura, admite, compila y
reservada idempotentemente como tarea propia. Cada tarea correlacionada con el turno.
recibe el estado terminal autoritativo.

La elección del catálogo no es una autoridad adicional. Parámetros, una versión de acción o una
El identificador del procedimiento no puede debilitar la ruta. Asimismo, el lenguaje natural puede
nunca cree una ruta de ejecución.

## Comportamiento de autenticación del servidor de aplicaciones

La TUI se inicia sin conexión. Sus modos acumulativos quedan:

| Banderas de invocación | Servidor de aplicaciones | Autenticación/capacidad configurada | Envío de conversación |
|---|---:|---:|---:|
| ninguno | apagado | no disponible | discapacitados |
| `--connect-app-server` | conectado localmente | mostrado | discapacitados |
| `--connect-app-server --enable-live-turns` | conectado localmente | mostrado | solicitudes explícitas de solo conversación habilitadas |

El transporte acepta la autenticación de clave API o administrada por ChatGPT configurada
modo. Los valores de las claves API nunca se presentan en la TUI, el diario o los diagnósticos.
El agotamiento de la capacidad de ChatGPT impide el envío de nuevos turnos; La capacidad de la clave API es
administrado por el proveedor y, por lo tanto, reportado como no disponible localmente. Mensajes capturados
nunca se reproducen automáticamente después de una desconexión, capacidad, tiempo de espera, desconexión,
o estado de presentación incierta.

Las dos banderas de inclusión voluntaria se implementaron pero no se ejercieron contra el real
Servidor de aplicaciones en esta fase. Esa aceptación en vivo sigue siendo una aprobación separada del usuario.
cheque.

## Controles de presentación y privacidad

- Cada cadena unida a la terminal está desinfectada y tapada.
- Controles de terminal ANSI/OSC, controles C1, controles bidireccionales y maliciosos
  Los hipervínculos no se pueden emitir como instrucciones de terminal activas.
- Deltas de mensajes de agente agregados por elemento y un mensaje completo autorizado
  reemplaza la proyección parcial.
- Los metadatos del ciclo de vida de la herramienta segura pueden mostrar un tipo y estado de elemento. Argumentos de herramientas,
  consultas, resultados, salida de comandos, diferencias y cargas útiles de elementos arbitrarios no están
  prestado.
- Siempre se retiene el razonamiento crudo.
- Un comando, cambio de archivo, permiso, obtención de MCP o solicitud de entrada de usuario es
  aparece como bloqueado. La Fase 2 no tiene método de respuesta de aprobación.
- El texto de la consulta de conocimiento se representa en la interfaz de usuario, pero solo su resumen, tipo,
  el límite y el recuento de resultados ingresan al diario del corredor.
- La descripción general almacena en caché el estado de integridad local; los tokens transmitidos no se repiten
  consulta o verificación de integridad de la base de datos.
- Las conexiones SQLite se cierran explícitamente después de cada lectura local.

## Comportamiento de falla y recuperación

- La admisión de tareas se agrega una vez y es determinista por tarea.
- Gire las teclas de idempotencia separadas de reserva de dirección de inicio y seguimiento antes
  transmisión.
- Una operación incierta bloquea la tarea y requiere un nuevo envío deliberado;
  nunca se vuelve a intentar automáticamente.
- Desconexión, error de protocolo, actividad inesperada de la herramienta o un servidor no controlado
  La solicitud bloquea todas las tareas correlacionadas con el turno.
- Al apagar la terminal, el servidor de aplicaciones secundario se detiene si fue explícitamente
  comenzó. La interfaz de usuario no posee ningún proceso recopilador o ejecutor.
- La recuperación del diario restaura solo metadatos de correlación y estado no confidenciales,
  Nunca incites a los cuerpos.

## Evidencia de validación

El conjunto de pruebas deterministas cubre:- admisión equivalente sin autoridad de acogida para lenguaje natural y catálogo
  solicitudes de diagnóstico de iluminación;
- aislamiento de lectura local del servidor de aplicaciones;
- envío modal generado por esquema y validación de formularios;
- dirección de seguimiento y correlación compartida entre el estado terminal;
- planes estructurados y de sustitución de mensajes transmitidos;
- solicitudes de aprobación bloqueadas, razonamiento retenido, comando/salida diferencial retenidos,
  y representación segura del ciclo de vida de la herramienta basada únicamente en metadatos;
- estado semántico en modo plano, navegación por teclado, diseños compactos y amplios;
- interacciones de catálogo a conversación y vista de conocimiento a través de Textual
  sin cabeza `run_test`/Arnés de piloto;
- conexiones SQLite cerradas de solo lectura, desinfección de terminales, diario
  integridad, reconexión, idempotencia y no repetición.

El validador de proyectos ejecuta las pruebas TUI independientes de la dependencia con el sistema.
Pitón. Las pruebas reales de UI sin cabeza se ejecutan cuando el `textual==8.2.8` anclado
la dependencia está instalada; La validación de la versión para la Fase 2 también se ejecutó dentro del
entorno de prueba aislado.

## Diferido por diseño

La fase 2 no contiene deliberadamente:

- Escaneo de Fedora o recopilación de especificaciones del sistema;
- diagnóstico de brillo de la pantalla o iluminación del teclado;
- shell, entrada de comando arbitraria, ejecutor de comando, recopilador o privilegiado
  servicio;
- instalación de paquetes, limpieza, actualización, reparación, cambio de configuración, datos
  eliminación o automodificación;
- UI de aceptación de aprobación o respuesta de aprobación del servidor de aplicaciones;
- promoción de listas seguras o automatización desatendida;
- afirmar que el caso de uso de iluminación preparado ha sido diagnosticado en la realidad
  estación de trabajo.

Este límite histórico fue reemplazado por la aplicación exacta y de verificación previa escrita.
Contrato de aprobación del servidor en `tui-contract.md`.

## Referencias primarias

- [Codex App Server](https://learn.chatgpt.com/docs/app-server)
- [Codex authentication](https://learn.chatgpt.com/docs/auth)
- [Codex approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Codex with ChatGPT plans](https://help.openai.com/en/articles/11369540-using-codex-with-chatgpt)
- [Textual testing](https://textual.textualize.io/guide/testing/)
- [Textual workers](https://textual.textualize.io/guide/workers/)
- [Textual `TabbedContent`](https://textual.textualize.io/widgets/tabbed_content/)
