# Estado actual del producto JARVIS

**Actualizado:** 2026-09-13 (candidato de publicación raíz; la implementación privilegiada permanece cerrada por separado)

Este es el documento del estado operativo del repositorio. Fase anterior y
Los documentos de planificación siguen siendo útiles como historial de diseño, pero no anulan esta página.
para conocer el comportamiento actual de la TUI o el estado de implementación.

## Ubicación del proyecto

La raíz del proyecto es `~/Escritorio/Proyecto/codex-agent-system`.

La aplicación Textual activa se encuentra en `tui/src/jarvis_tui/`. ejecutarlo desde el
raíz del proyecto con el iniciador de verificación de fuente:```bash
bash scripts/launch-tui.sh
```Utiliza el proyecto `.venv`, habilita el servidor de aplicaciones local/indicadores de turnos en vivo y
se niega a iniciar si `jarvis_tui.package_inventory` no se importa de este
pago. Pase `--connect-jarvisd` o `--plain` después del comando de script cuando
necesario.

El registro de estabilización activo es `docs/sessions/2026-08-28-stabilization.md`.
Utilice `bash scripts/quality-gate.sh --fast` para el perfil de calidad rápida local;
la puerta de liberación completa sigue siendo `./scripts/validate-bundle.sh`.

## Mapa fuente

| Área | Ubicación principal | Función actual |
| --- | --- | --- |
| Diseño TUI, pestañas, cuadros de diálogo, flujo de envío | `tui/src/jarvis_tui/app.py` | Conversación, Agentes, paquetes, energía, iluminación, cronograma y operaciones; las aprobaciones siguen siendo modales. |
| Conexión del servidor de aplicaciones | `tui/src/jarvis_tui/app_server.py`, `session.py` | Autenticación, subprocesos y turnos de conversación del Codex App Server local. |
| Estado corredor y auditoría | `tui/src/jarvis_tui/preflight.py`, `broker.py`, `event_store.py`, `event_reducer.py` | Evaluación determinista de primera intención, admisión de tareas escritas, estado incremental de la cadena hash, resúmenes de flujo limitado y proyecciones de recuperación. |
| Lecturas del sistema de archivos acotado | `tui/src/jarvis_tui/local_filesystem.py` | Planificación conservadora en inglés/español y lista/lectura/búsqueda solo para usuarios actuales a través de las API del sistema de archivos Python. |
| Mutaciones del sistema de archivos controladas por aprobación | `tui/src/jarvis_tui/local_mutation.py` | Creación exacta de directorio/archivo de texto vacío y movimiento a la Papelera en el mismo sistema de archivos, con revisión inmutable y confirmación de un solo uso. |
| Inspección de host de sólo lectura | `tui/src/jarvis_tui/local_control.py` | Recopilación limitada de inventario de energía, paquetes y plataformas. |
| Catálogo de paquetes y detalles | `tui/src/jarvis_tui/package_inventory.py`, `package_knowledge.py` | RPM instalados, paquetes DNF almacenados en caché, orígenes, propósito, documentación, relaciones y vistas previas. |
| Paquete cliente privilegiado | `tui/src/jarvis_tui/package_control_client.py` | Invoca sólo el asistente raíz instalado a través de Polkit. |
| Asistente raíz del paquete | `vm-lab/scripts/jarvis_package_control.py` | Instalación/eliminación exacta del conjunto de paquetes y desinstalación aprobada por separado con un diario duradero previo al estado. |
| Implementación de paquetes | `deployment/host/install_jarvis_package_control.sh`, `deployment/host/org.jarvis.package-control.policy` | Instalación del asistente raíz vinculado a hash en `/usr/libexec/jarvis-package-control`. |
| Inventario/control de energía | `tui/src/jarvis_tui/power_inventory.py`, `power_profiles.py`, `power_profile_results.py`, `power_control_client.py`, `vm-lab/scripts/jarvis_power_control.py`, `plugins/jarvis-power-expert/scripts/power_tools.py` | Recomendaciones de energía impulsadas por agentes a través de herramientas MCP escritas, topología/telemetría desinfectadas, planificación persistente de perfiles de CA/batería, mutaciones de control único/perfiles atómicos incluidos por separado y comparaciones de aplicaciones verificadas vinculadas a resumen sincronizadas con Conversation. |
| Controles de iluminación | `tui/src/jarvis_tui/lighting_controls.py`, `lighting_widgets.py` | Detección de conductores, vista previa y rutas de iluminación registradas. |
| Especialistas | `plugins/*/specialist.json`, `tui/src/jarvis_tui/specialists.py`, `tui/src/jarvis_tui/agent_registry.py` | Especialistas seleccionados por el usuario, definiciones validadas, selección persistente y anulaciones activas exclusivas del propietario. |
| Acciones y conocimientos tipificados | `plugins/jarvis-system-admin/` | Registros, esquemas, habilidades, definiciones de recopiladores y almacenamiento de conocimientos. |
| Soporte de host directo y VM | `deployment/host/`, `vm-lab/` | Guiones de implementación, artefactos de políticas, ayudantes y contratos de ensayo. |

El servidor de aplicaciones secundario recibe solo un entorno de proceso/autenticación explícito
lista de permitidos. Las líneas de protocolo, el anidamiento, los tamaños de colección y los eventos en cola son
acotado antes de la normalización. Los comandos de red propuestos por el modelo quedan atrás
La misma aprobación de comando gráfico exacta que otros efectos externos.

## Comportamiento disponible

### Configuración global del agente y vistas contextuales

La vista Agentes expone un selector de modelo global, un selector de esfuerzo de razonamiento
y un selector de ventana contextual para todos los especialistas. Los valores persisten en
`runtime/jarvis-model.json` y se aplican a nuevos turnos. Las opciones de contexto son Auto,
Fichas de 8k, 16k, 32k, 64k, 128k, 256k, 512k, 800k, 1M y 1,05M. salud,
Desarrollo, Red, Seguridad y Recuperación exponen evidencia limpia y cruda
vistas; Clean presenta campos delimitados con explicaciones `[i]` y Raw retiene
el JSON completo.La proyección de actividad de conversación incluye el uso de token cuando el servidor de aplicaciones
envía `thread/tokenUsage/updated` y muestra `unavailable` hasta entonces. Nuevo
Las conversaciones y las restauraciones de puntos de control restablecen el contexto utilizado a cero. Especialistas
no heredar el historial de conversaciones anteriores.

### Conversación y contexto especializado

- El historial de conversaciones persiste en todos los roles que se muestran en la vista de conversación.
  (`user`, `agent`, `jarvis`, `action` y `system`), incluida una aclaración
  preguntas y su texto de Opciones, con estado/tarea/identidad de turno delimitados.
  Los registros más antiguos creados antes de este cambio de esquema siguen siendo legibles pero no
  recuperar contenido que nunca persistió.
- La recarga del historial utiliza la posición de la matriz de cada mensaje guardado para la contabilidad;
  Las claves locales/de tareas persistentes son identificadores opacos y nunca se analizan como
  índices numéricos.
- La presentación de la conversación sigue un diseño de mensajería: `YOU` y usuario
  las entradas de aclaración están alineadas a la derecha; todos los entrantes `AGENT`, `JARVIS`,
  Las entradas `ACTION` y `SYSTEM` permanecen visibles y alineadas a la izquierda.
- La pestaña Conversación utiliza una composición centrada del 92% de ancho con una celda
  corrección de redondeo del renderizador, un riel de acción derecha de ancho uniforme, simétrico
  6% de brechas de equilibrio alrededor del chat y un selector especializado en la parte superior izquierda sin
  etiqueta separada.- Un envío aceptado se proyecta en Conversación como
  `resolving_intent` antes de la clasificación. Enviar y entrar adicional
  los envíos están deshabilitados para esa tarea en vuelo; navegación, volver a dibujar,
  el cambio de tamaño y la cancelación siguen estando disponibles. El texto escrito mientras está ocupado se mantiene y
  no está en cola.
- Las solicitudes de lista/lectura/búsqueda del sistema de archivos local delimitado exacto primero usan el
  planificador determinista. No dependen de la disponibilidad del App Server, cree
  un turno del Codex, invocar Bash o solicitar aprobación. Otro lenguaje natural
  las solicitudes todavía usan exactamente una verificación previa del servidor de aplicaciones escrita y no mutante cuando
  Los turnos en vivo están habilitados.
- La vista de conversación limpia y desinfectada es el contexto activo para el agente posterior
  solicitudes, incluidas solicitudes y resultados de lectura local delimitados. Falta visible
  las entradas se inyectan una vez como historial explícitamente no confiable antes de la siguiente
  verificación previa escrita; la solicitud actual permanece separada. Esta sincronización
  no utiliza Bash y no otorga autoridad.
- Un seguimiento puede derivar de un recuento, resumen, comparación o explicación de uno
  resultado de conversación compatible reciente. Referencias singulares como “el
  directorio” resuelve ese resultado, y al agente de solo respuesta se le dice que no
  para utilizar herramientas o solicitar aprobación. Las referencias ambiguas aún aclaran; un
  La solicitud de actualización explícita requiere una nueva lectura limitada.
- El contexto de conversación activa sigue la configuración global de la ventana de token (Auto, 8k,
  16k, 32k, 64k, 128k, 256k, 512k, 800k, 1M o 1,05M) y permanece limitado a
  500 entradas de presentación. Los intercambios completos más antiguos se eliminan de ambos
  junto con un marcador de omisión visible. Las acciones nuevas, limpias y con historial cargado inician un nuevo contexto
  época y, por lo tanto, un nuevo hilo de App Server en la siguiente solicitud de modelo.
- Los resultados visibles de lectura local persisten en la conversación después de la terminal
  desinfección/redacción para que las transcripciones de especialistas y las recargas de historial se conserven
  el flujo de trabajo visible para el usuario. La salida del sistema de archivos sin procesar permanece excluida del
  El diario de eventos y los nombres/contenidos de archivos confidenciales se rechazan antes de procesarlos.
  o la persistencia.
- Los eventos del ciclo de vida del servidor de aplicaciones sin estado `agentMessage` derivan su estado
  de `item/started` y `item/completed`. La respuesta iniciada se muestra como
  en progreso inmediatamente y al finalizar se actualiza esa misma entrada de la conversación.
- Escritorio/Escritorio, Documentos/Documentos y Descargas/Descargas se resuelven por
  analizando `~/.config/user-dirs.dirs` como datos, nunca obteniendolos. un
  El respaldo compatible con la configuración regional se usa solo cuando exactamente un directorio existente
  coincidencias. También se admiten formularios de espacio de trabajo/proyecto y ruta explícita.
- El lector local es sólo para el usuario actual, seguro para descriptores y no recursivo para un
  listado predeterminado, delimitado, desinfectado de terminal, redactado con valor de credencial y
  denegada para objetivos sensibles/especiales/ambiguos. Contenidos de archivos, listados,
  Las rutas y el texto de búsqueda no se escriben en el diario de eventos de TUI.
- La coincidencia confidencial de nombres de archivos tiene en cuenta la configuración regional y rechaza la posesión de credenciales
  Etiquetas en inglés y español, incluidas `contraseña`/`contrasena` concatenadas
  prefijos, antes de enumerar, buscar, representar o sincronizar el contexto.
- El sistema de archivos exacto crea y mueve a la Papelera utiliza un determinista separado
  ejecutor del usuario actual. Pueden apuntar a rutas de escritura no protegidas fuera de
  el proyecto, pero siempre espere una nueva confirmación modal exacta, reserve
  una vez, revalidar la identidad del descriptor y nunca usar Bash.
- Cada mutación requiere una nueva decisión de un solo uso. Modelo propuesto
  las mutaciones del usuario actual utilizan operaciones registradas de un solo uso; se rechazan las aprobaciones genéricas de comandos/archivos de App Server; El trabajo privilegiado está limitado a los ayudantes registrados de Polkit. Experto en energía
  A su vez, utiliza una zona de pruebas de solo lectura y herramientas MCP escritas. La aprobación de toda la sesión es
  no expuesto.
- Las solicitudes de aprobación de archivos/comandos conservan exactamente los ID JSON-RPC actuales,incluyendo el número entero `0`; el modal de revisión exacta admite aceptar una vez, rechazar,
  y cancelar, y la resolución del terminal elimina la solicitud pendiente.
- El usuario selecciona explícitamente el especialista activo. El coordinador nunca
  cambia de especialistas automáticamente; se aclara una solicitud fuera de alcance o
  declinado.
- La pestaña Agentes expone resúmenes operativos y tanto estructurados como sin procesar.
  edición de definiciones. La activación requiere validación, una diferencia exacta, una nueva
  aprobación y conserva la definición activa anterior para la reversión.
- Se pueden seleccionar ocho especialistas: arquitecto JARVIS, especialista en instalación, experto en energía, especialista en salud del sistema, constructor de carga, especialista en redes, especialista en seguridad y especialista en recuperación.
- Proporciona evidencia limitada de inspección del host a una solicitud de conversación. el
  El modelo recibe evidencia formateada, no acceso de terminal o raíz.

### Inspección de host de solo lectura

- Plataforma: sistema operativo, kernel y arquitectura.
- Paquetes: RPM instalados y metadatos del repositorio DNF en caché.
- Alimentación: TuneD/tuned-ppd, gobernador de CPU/EPP/interfaces de estado P, plataforma
  perfil, energía de tiempo de ejecución Intel/NVIDIA, fuentes de alimentación, presencia de Powertop y
  evidencia relacionada del controlador/módulo.
- Power Expert es seleccionable e informa la topología de hardware/software desinfectada,
  conflictos de proveedores, telemetría limitada, capacidades de control disponibles y
  Planes persistentes de perfil de CA/batería. La activación del perfil permanece manualmente
  aprobó y utiliza una transacción de ayuda atómica; resultados parciales requieren
  Recuperación previa al estado exacta aprobada por separado.
- Los datos del catálogo de paquetes se almacenan en
  `runtime/knowledge/package-catalog.json.gz` con permisos exclusivos de propietario.

### Inventario de paquetes y recomendaciones

- Vistas de candidatos instaladas, disponibles en caché, combinadas y actualizadas.
- Filtrado acotado, paginación, categoría/propósito/origen/detalles de estado, local
  Documentación de RPM, consultas de dependencia/relación e historial de DNF.
- Las recomendaciones almacenadas en caché están etiquetadas según la evidencia. Los partidos con el mismo propósito son una
  inferencia, no un reclamo de conflicto de RPM.
- La actualización de la documentación web oficial no es una capacidad automática.

La pestaña Paquetes y el Especialista en instalación utilizan el mismo inventario de paquetes y
backend de mutación. Las acciones de paquete permanecen disponibles desde Paquetes mientras el
El especialista posee el contexto, las referencias de herramientas y las explicaciones específicas del paquete.
La inspección de paquetes en lenguaje natural se dirige a través del seleccionado
Especialista en instalación o Power Expert y su paquete de solo lectura registrado
Herramientas MCP. La pestaña Paquetes sigue siendo una vista de inventario local separada y exacta
Las solicitudes de instalación/eliminación conservan su flujo de trabajo registrado sujeto a aprobación.

### Instalación y eliminación de paquetes sujetos a aprobación

La vista Paquetes y el planificador conservador en lenguaje natural admiten nombre exacto
Instalación y desinstalación a través de un ayudante fijo registrado. lenguaje natural
las solicitudes de paquetes exactas conservan raíces deterministas pero usan una escrita
verificación previa de planificación de agentes antes de una vista previa de DNF de solo caché. Nombres citados y
Las raíces denominadas "relacionadas con" se normalizan antes de esa transferencia. El abandono determina
dependencias; hay una aprobación final exacta, no una elección de dependencia
diálogo. El agente puede aclarar una vez, pero no puede proponer `sudo`/`dnf`/Bash para
la mutación; sólo el ayudante registrado lo ejecuta.

Antes de la verificación previa del modelo relacionado con el paquete, JARVIS realiza una verificación limitada de solo lectura
Actualización de RPM/base de datos y catálogo DNF en caché. El clasificador recibe sólo
recuentos, frescura y hasta 24 registros de candidatos desinfectados instalados/disponibles
para la solicitud. Utiliza esa evidencia para solicitar raíces exactas de Fedora u ofrecer
candidatos concretos; no autoriza una transacción. Oficial aguas arriba
descargar descargas, cambios en el repositorio y comandos arbitrarios del administrador de paquetes
permanecer sin apoyo.Los alias de lenguaje utilizan nombres de paquetes de Fedora observados antes que utilidades genéricas:
por ejemplo, una solicitud para la cadena de herramientas del lenguaje Go prioriza el almacenamiento en caché
`golang` sobre herramientas `go-*` no relacionadas. Las respuestas de aclaración numeradas están vinculadas.
al texto de opción mostrado antes del siguiente turno de clasificación.

Los saludos breves utilizan una ruta de conversación determinista. Un recién ingresado
La solicitud de paquete determinista reemplaza una aclaración pendiente no relacionada.
en lugar de concatenarse en texto de verificación previa del modelo.

Antes de mostrar una autorización final, JARVIS verifica automáticamente:

1. los nombres son tokens de paquetes RPM exactamente delimitados;
2. el asistente raíz vinculado a hash está instalado y es ejecutable;
3. una simulación DNF de solo caché resuelve la transacción y vincula el RPM actual
   pre-estado; y
4. Las vistas previas de instalación son estrictamente aditivas (sin eliminación, actualización, degradación,
   reinstalar o reemplazar), mientras que las vistas previas de eliminación usan `--no-autoremove`,
   enumera el conjunto de eliminación y no contiene ningún paquete protegido.

El cuadro de diálogo de revisión muestra los paquetes solicitados, el estado de instalación anterior y los resueltos.
eliminaciones y la vista previa limitada de DNF. Comienza la aprobación
Autenticación Polkit y pasa solo la operación, los nombres de los paquetes y el estado previo del resumen
al ayudante raíz. El asistente registra un diario por usuario de propiedad raíz antes del DNF
se ejecuta, verifica el estado posterior y admite la deshacer aprobada por separado.
La pestaña Paquetes y las rutas de lenguaje natural consumen la misma aprobación del corredor.
y registros de reserva de ejecución antes de invocar al ayudante. Una vez invocada
comienza, un error o una respuesta perdida se informa como indeterminado y apunta a
el registro de recuperación autorizado; nunca se describe como una operación no segura.
Si una lectura de estado posterior al error encuentra ese registro vinculado a un paquete diferente
establecido, la línea de tiempo informa `package_helper.recovery_record_mismatch` y bloquea
aprobación adicional hasta que se concilie ese registro.
Rechazos de ayuda conocidos que ocurren antes de que se escriba un registro de transacción duradero
se informan como operaciones seguras no operativas previas a la ejecución; solo fallas posteriores al registro o desconocidas
permanecen indeterminados.
Cuando no existe ningún registro de recuperación, el asistente devuelve un estado vacío explícito;
la vista Paquetes no abre un cuadro de diálogo de aprobación de reversión sin sentido.
Un estado de autoridad vacío después de una invocación perdida/incierta no prueba la finalización o ausencia de efectos posteriores. JARVIS informa `package_helper.no_recovery_record`, conserva un resultado indeterminado y requiere la reconciliación del ayudante original. Los rechazos explícitos previos a la ejecución conocidos siguen siendo operaciones de exclusión seguras distintas.

El registro de acciones también contiene metadatos deshabilitados para la potencia preparada.
candidato de perfil. Esto sólo satisface la coherencia del catálogo: no
registrar el adaptador candidato, habilitar la capacidad, invocar D-Bus o conceder
autoridad de mutación del perfil de poder.

Implemente el asistente actual antes de usar esta función:```bash
sudo ./deployment/host/install_jarvis_package_control.sh
```El ayudante no es un shell ni un ejecutor DNF arbitrario. No acepta concha
fragmentos, URL del repositorio u opciones DNF proporcionadas por el usuario.

## Limitaciones actuales

- El flujo de trabajo del paquete directo cubre únicamente la instalación/eliminación del nombre exacto. Actualizaciones,
  habilitación del repositorio, opciones arbitrarias de DNF, objetivos amplios del paquete y
  Este flujo no habilita la recuperación automática de documentación oficial.
- La edición de la definición del agente se limita a los agentes instalados revisados y
  herramientas registradas. Nuevos módulos ejecutables, comandos arbitrarios y directos.
  Las concesiones de privilegios no se pueden crear desde el editor de Agentes.
- Reinstale el asistente raíz después de que cambie su fuente vinculada a hash o su instalador.
- El descubrimiento de energía es amplio, pero solo se pueden escribir controles incluidos en la lista permitida por separado.
  No se puede escribir automáticamente en una fila de inventario mostrada.
- Encuestas de telemetría de energía solo mientras la pestaña Energía está activa. TLP, frecuencia de CPU automática,
  Los controles de frecuencia/térmicos y del proveedor se detectan o representan como
  capacidades pero requieren adaptadores revisados fijos antes de la mutación.
- Las recomendaciones del paquete Power Expert crean una instalación explícita
  Traspaso de especialistas; no instalan ni eliminan paquetes directamente.
- La compatibilidad con la iluminación depende de los controladores de hardware detectados y registrados.
- La gramática del lenguaje determinista es intencionadamente estrecha. Reconocido pero
  la redacción ambigua de lectura local produce una pregunta con 2 o 3 opciones concretas;
  la redacción no reconocida cae en la verificación previa del modelo.
- La reproducción de inicio de la línea de tiempo omite los deltas de transmisión heredados y el protocolo no material
  charla de la proyección humana, limita la historia material a más tardar 100
  registra, informa recuentos de omisiones limitadas y deja el diario de solo anexos
  sin cambios. Los nuevos deltas de flujo producen un resumen de solo metadatos en el elemento o
  finalización del turno.
- La búsqueda permanece limitada a la profundidad 8, 2000 archivos normales examinados, 1 MiB por
  archivo, 200 coincidencias y una fecha límite corta y monótona. No es una indexación de viviendas.
  o función de descubrimiento de secretos.
- Los turnos de agentes son de solo lectura y no pueden escalar. Las mutaciones requieren albaceas registrados; no existe un respaldo genérico de Bash. El nuevo perfil de tiempo de ejecución debe revisarse y activarse por separado.

## Validación y soporte

Las pruebas de control/paquete TUI enfocadas se encuentran en `tui/tests/`. Ejecute el paquete estático
validador con:```bash
./scripts/validate-bundle.sh
```El validador no instala paquetes ni modifica la estación de trabajo. Para paquete
fallas en las transacciones, use el resultado de la conversación y la línea de tiempo: el cliente
muestra el detalle del error acotado del asistente raíz.

## 2026-09-07 implementación por etapas

Este candidato está separado del pago activo. Ver
[specific acceptance and remaining work](sesiones/2026-09-08-implementacion.md).

- Los recolectores de salud y extendidos limitan los bytes durante la lectura, se detienen en caso de desbordamiento o tiempo de espera,
  redacte antes de regresar y etiquete las observaciones nuevas. El manifiesto del proyecto dice rechazar
  enlaces simbólicos, archivos especiales/sin propietario, contenido de gran tamaño y raíces inseguras.
- Cada proceso de App Server recibe su propio identificador de alcance MCP. El corredor publica
  permisos sólo después de la admisión y los revoca en eventos terminales, interrupción,
  o desconectar. Los esquemas MCP son detectables, pero cada envío verifica el estado en vivo.
  ámbito especializado. Un esquema descubierto nunca otorga autoridad. Activación de lección
  no está disponible a través del MCP orientado al modelo.
- `operation_plan` prepara una propuesta de resumen; No existe ninguna herramienta de solicitud/aprobación de MCP.
  Una revisión dedicada consume una decisión efímera y reserva un intento duradero
  antes de los efectos. Aplicar manifiestos de dependencia existentes a un proyecto original
  requiere propuesta propia y conserva archivos desplazados.
- Cargo ejecuta la instantánea de la fuente aprobada bajo plástico de burbujas y un sistema transitorio
  servicio al usuario. Una protección requiere límites efectivos de memoria/proceso/CPU de cgroup v2 antes
  código de lanzamiento. No tiene soporte de red, doméstico o de fuente grabable. Una carga vacía
  caché significa que las dependencias externas pueden no estar disponibles. Aprobado por separado,
  Las descargas vinculadas a la suma de comprobación se pueden consumir a través de una fuente de directorio sin conexión.
- Las propuestas de dependencia de carga crean un espacio de trabajo separado con archivos revisados ​​exactos.
  Copias de seguridad/restauración de árboles de proyectos de texto vinculados únicamente a un nuevo destino. Estos
  son operaciones de proyecto R0, no recuperación de disco, arranque o datos binarios del sistema completo.
- Los resultados de la operación y los registros de verificación están separados. El verificador se ejecuta en un
  proceso de envoltura de burbujas de solo lectura. Si esa zona de pruebas no puede iniciarse, el resultado es desconocido,
  nunca verificado de forma independiente. El estado de salida de la compilación por sí solo no demuestra la seguridad del hardware.
- Las vistas de Salud, Desarrollo, Red, Seguridad y Recuperación solo recopilan evidencia
  previa solicitud y revisar el ID de operación proporcionado por el agente. La conversación permanece
  libre de tarjetas de actividades; los resultados materiales entran en su contexto persistente existente.
- Las transcripciones operativas desinfectadas tienen tipo/campo, tamaño, recuento y caducidad explícitos.
  límites. Se rechazan los campos de razonamiento y secreto/entorno. El contenido caducado es
  retenido; la eliminación/rotación requiere una política revisada por separado.
- El código auxiliar del servicio existe pero no está implementado/inscrito. Las comprobaciones TCP exactas tienen un ejecutor de un solo uso. Los asistentes de DNS estrecho, etiqueta SELinux y firewall están preparados, pero no implementados. Los asistentes de actualización y arranque ahora requieren una revisión raíz independiente exacta y evidencia de recuperación nueva; El despliegue no es automático. La orquestación de recuperación del sistema permanece separada del backend de copia del proyecto de texto.

## Cierre de terminal y validación — 2026-09-11

El modo terminal normal tiene su propia propuesta, resumen, enlace de entorno efímero,
aprobación, reserva y resultado. Textual suspende/reanuda su hilo de interfaz de usuario;
el niño hereda descriptores de terminal reales y se ejecuta sin imposición de la aplicación
límites de recursos o tiempo de ejecución. El usuario ve explícitamente el acceso al host y la red.
autoridad; el modo nunca hereda afirmaciones de la propuesta aislada. TUI raíz
Los procesos no pueden utilizar esta ruta. Sólo se atestigua la salida en primer plano.

La afirmación anterior de un conjunto de textos colgado permanentemente no fue respaldada:
el registro retenido completó 36 pruebas en 109,777 segundos. Un nuevo humo PTY real
Ejerció el botón de revisión, un printf y la reanudación de la interfaz de usuario. Ver
`sessions/2026-09-11-validation-closeout.md` y `PATCH-GUIDE-2026-09.md`.
