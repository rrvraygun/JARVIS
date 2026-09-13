# Hoja de ruta maestra de Jarvis

**Rol del documento:** hoja de ruta canónica y lista de verificación de finalización para Jarvis
proyecto. Este archivo consolida el plan de arquitectura, fases de entrega,
contratos de plano de control, hitos de TUI, implementación de host directo, recuperación,
requisitos de lanzamiento y madurez de capacidad.

**Fecha de la instantánea:** 2026-08-07

> **Nota del estado actual (2026-08-09):** esta hoja de ruta es el diseño canónico
> y el historial de entrega, pero partes de su texto de estado de fase son anteriores a la
> implementó una ruta de control de paquetes limitada. Para el comportamiento implementado actualmente,
> mapa fuente y limitaciones, leer
> [`current-product-state.md`](estado-actual-producto.md) primero.

**Límite importante:** este es un documento de planificación y estado. no es un
autorización para instalar, inspeccionar, modificar, aprobar, ejecutar o actualizar automáticamente el
anfitrión. Cada cambio de estado futuro aún requiere su propia política, evidencia,
puertas de recuperación, aprobación, ejecución y verificación.

## 1. Objetivo del producto

Jarvis es un asistente de estación de trabajo local basado en evidencia con dos iguales
estilos de interacción:

1. conversación en lenguaje natural;
2. un catálogo con capacidad de búsqueda de acciones versionadas y escritas.

Ambos estilos deben converger en una tarea y una línea de políticas inmutables. La TUI es
sólo una superficie de presentación/consentimiento. El intermediario/avión de control es propietario del estado,
política, evidencia, aprobaciones, auditoría y eventuales adaptadores estrechos. Aplicación del Códice
El servidor proporciona conversación y razonamiento, pero nunca se convierte en un anfitrión oculto.
ejecutor.

El producto objetivo es una consola de estación de trabajo Fedora segura y supervisada. Opcional
El trabajo de VM/laboratorio valida los contratos de software pero no puede reemplazar la evidencia física
para firmware, ACPI, enrutamiento de GPU, paneles, iluminación de teclado, batería, térmicas,
o suspender/reanudar.

### 1.1 Alcance unificado de host directo/TUI

El objetivo principal de entrega es ahora una estación de trabajo Fedora directa que ejecute Jarvis.
en modo sombra. Textual TUI es la superficie de operador única para:

- Conversación administrada por ChatGPT y acciones de catálogo escritas;
- plataforma H1 delimitada/observaciones informáticas en la estación de trabajo real;
- Estado de recuperación de LUKS/R2 y visibilidad de la auditoría;
- diagnóstico basado en evidencia del primer caso de uso físico: brillo de la pantalla y
  iluminación del teclado.

La TUI y el plano de control de host directo avanzan juntos: una característica TUI no es
completar hasta que su estado de autoridad de host sea visible y se realice una observación del host.
no admitido hasta que tenga un alcance, frescura, evidencia y parada visibles para TUI
condición. El ensayo de VM sigue siendo opcional y nunca bloquea este host directo
pista de sombra.

## 2. Invariantes no negociables

- Observación separada, hecho fundamentado, inferencia, recomendación, propuesta,
  aprobación, ejecución, validación y estados de lección.
- Inspección predeterminada de solo lectura y con privilegios mínimos con alcance limitado y uno
  intento. Deténgase ante un resultado inesperado; nunca vuelva a intentarlo automáticamente.
- Sin shell sin formato, raíz sin restricciones, comando arbitrario, canal privilegiado directo,
  o ejecutor oculto en la TUI, broker o modelo.
- Cada mutación es comando exacto, objetivo, estado, política, adaptador y
  sujeto a aprobación, con estado previo, reversión/recuperación, condiciones posteriores y
  revisión independiente.
- La autenticación del Codex se gestiona mediante ChatGPT de forma predeterminada. Nunca utilices silenciosamente un
  Clave API o reserva API paga.
- Nunca persista en credenciales, tokens, claves privadas, cadenas de pensamiento en bruto o
  salida sensible sin editar.
- Fallo de auditoría y gobernanza cerrado por mutación.
- Una capacidad avanza sólo a través del modelo de madurez y la revisión explícita;
  El uso repetido y exitoso no crea autoridad.
- El agente puede realizar un cambio pero no puede aprobar ni dar fe únicamente de su propio
  lanzamiento o transición de política.

## 3. Arquitectura y planos permanentes

### 3.1 Plano de presentación`jarvis-tui` ofrece descripción general, conversación, acciones, conocimientos, planes,
aprobaciones, cronograma, errores, lecciones, recuperación y configuración. recoge mecanografiado
entrada y consentimiento explícito, pero no tiene API de shell, ejecutor sin formato, privilegios, política
capacidad de escritura o mutación directa de bases de datos.

### 3.2 Plano de sesión/broker

`jarvisd` (inicialmente permitido ser un servicio en proceso) posee sesiones, tarea
registros, idempotencia, reducción de eventos, correlación del servidor de aplicaciones, llamadas de políticas,
aprobación de encuadernación, recuperación y redacción de diarios. Antes de la mutación supervisada
Debe ser un proceso independiente sin privilegios en un socket Unix privado.

### 3.3 Plano del servidor de aplicaciones Codex

Utilice el servidor de aplicaciones stdio JSONL local con el protocolo instalado anclado. la corriente
El objetivo de compatibilidad es `codex-cli 0.146.0`. La lista de permitidos se limita a la cuenta,
métodos de hilo, giro, interrupción y ciclo de vida requerido. Shell/proceso/archivo
Los métodos de ejecución se deniegan o se muestran como bloqueados.

### 3.4 Plano de control, conocimiento y auditoría

Los registros mecanografiados definen acciones, procedimientos, recolectores, adaptadores, evidencia,
riesgos y recuperación. SQLite almacena hechos, fuentes, intentos, errores, lecciones,
decisiones y aprobaciones. El libro de contabilidad JSONL v2 de solo agregar está encadenado mediante hash y
debe ser verificable de forma independiente.

### 3.5 Plano adaptador/ejecutor

Los adaptadores futuros son plantillas fijas de argumentos/ejecutables con salida limitada,
tiempos de espera, redacción, identidad de versión y verificación independiente. Un estrecho
Se prefiere el servicio de propiedad raíz con Polkit o autorización equivalente a
dando raíz a cualquier proceso orientado al modelo.

## 4. Vocabulario de estado

- **Completado:** la implementación y la validación requerida para esa puerta están realizadas.
- **Fixture-complete:** las pruebas deterministas y los escenarios sintéticos pasan, pero
  esto no prueba el comportamiento de Fedora en vivo o del hardware físico.
- **Observado:** se recopiló evidencia limitada de solo lectura en el host inscrito.
- **Pendiente de aceptación en vivo:** la implementación existe, pero la implementación deliberada en vivo
  La verificación de aceptación no se ha ejecutado.
- **Preparado:** existen esquemas, planes o procedimientos pero no tienen autoridad.
- **Planificado:** aún no implementado.
- **Bloqueado/diferido:** deliberadamente no disponible debido a una seguridad requerida,
  Falta la condición de dependencia, aprobación o evidencia.

## 5. Hoja de ruta de entrega

### Fase 0: decisiones arquitectónicas y accesorios

**Objetivo:** establecer los contratos y hacer inexpresable la ejecución insegura.

**Secciones y entregables**

- Modelo de límites y registros de decisiones de arquitectura.
- Esquemas canónicos: `IntentEnvelope`, `ActionDefinition`, `TaskRecord`, corredor
  eventos, instantáneas de sesiones, aprobaciones y compatibilidad de protocolos.
- Registro versionado de acciones/procedimientos con metadatos de UI escritos.
- Conversaciones sobre accesorios, envíos de catálogos, aprobaciones, desconexiones,
  salidas inesperadas, reinicios, agotamiento de capacidad y datos de protocolo con formato incorrecto.
- Esquema del Codex App Server anclado/generable y pruebas de compatibilidad de valores de cable.
- Amenazas, privacidad, seguridad de terminales, ciclo de vida de datos y madurez de capacidad
  contratos.

**Criterios de finalización**

- Todos los esquemas se validan y la serialización/resúmenes canónicos son estables.
- Ningún componente puede expresar la ejecución del host sin formato a través del protocolo declarado.
- La cobertura de accesorios incluye normal, adversario, reinicio, desconexión y
  casos de capacidad degradada.
- Los documentos de arquitectura, seguridad y autorización coinciden en los mismos límites.

**Estado:** Completo.

### Fase 1: corredor de solo lectura

**Objetivo:** crear un corredor local sin cabeza que pueda conversar y recuperarse
sin inspeccionar ni cambiar Fedora.

**Secciones y entregables**- Inicio e inicialización del servidor de aplicaciones stdio, estado de autenticación/inicio de sesión administrado por ChatGPT,
  visualización de límite de velocidad, inicio/reanudación del hilo, inicio de giro/dirección/interrupción.
- Lista de permitidos de métodos de cliente cerrada y métodos de ejecución/experimentales denegados.
- API de agente local, interfaz de usuario de solo anexo/diario de eventos de tareas, normalización de eventos,
  correlación, idempotencia y recuperación de fallas solo de metadatos.
- Listado de capacidades de solo lectura y consultas de conocimiento SQLite que nunca crean un
  tienda perdida.
- Comportamiento sin conexión y con capacidad agotada sin repetición automática de avisos.

**Criterios de finalización**

- Un cliente sin cabeza puede conectarse, autenticarse o mostrar el estado de inicio de sesión requerido.
  iniciar/reanudar un hilo, transmitir un turno, dirigirlo/interrumpirlo y recuperarse de
  desconéctese usando un servidor falso y una prueba de humo real aprobada por separado.
- No se utiliza ningún comando de Fedora, clave API, privilegio o mutación de host.
- Se cerraron los eventos duplicados/fuera de orden y el envío incierto.

**Estado:** Aceptación en vivo aprobada el 6 de agosto de 2026; ninguna autoridad anfitriona está expuesta.

### Fase 2: MVP de TUI híbrido

**Objetivo:** proporcionar una interfaz textual accesible mediante teclado para
acciones de conversación y catalogación.

**Secciones y entregables**

- Descripción general: sesión, autenticación/capacidad, registro, conocimiento, seguridad y recuperación
  estado.
- Conversación: compositor en lenguaje natural, mensajes transmitidos, estados de tareas,
  advertencias, solicitudes bloqueadas y dirección de seguimiento.
- Acciones: búsqueda generada por el registro y formularios escritos basados ​​en esquemas.
- Conocimiento: búsqueda de solo lectura entre hechos, fuentes, intentos, errores, lecciones,
  y decisiones.
- Plan: deltas del plan delimitado y estados de paso autorizados.
- Cronograma: proyecciones del ciclo de vida del broker seguro/servidor de aplicaciones.
- Desinfección de terminales, límites de salida, modo simple, manejo de cambio de tamaño, enfoque y
  limpieza de accidentes.

**Criterios de finalización**

- Las solicitudes de lenguaje natural y catálogo convergen en la misma tarea normalizada,
  admisión y resultado de la política sin autoridad de host.
- Las pruebas de interacción sin cabeza pasan en terminales de tamaño compacto y ancho.
- Pegar no puede enviar entradas de aprobación ocultas; argumentos de herramienta sin procesar, salida, diferencias,
  y el razonamiento son retenidos.
- Las vistas solo locales siguen siendo utilizables sin servidor de aplicaciones ni capacidad.

**Estado:** Implementado y validado por dispositivos. La dependencia textual fijada es
instalado en el proyecto local `.venv`; las 53 pruebas TUI y el inicio fuera de línea
pase. La aceptación del App Server en vivo se registra en la Fase 1.

### Fase 2B: integración de la consola sombra de host directo

**Objetivo:** fusionar el hito de TUI con la estación de trabajo principal de Fedora
flujo de trabajo en la sombra sin agregar autoridad de mutación.

**Secciones y entregables**

- Mostrar el estado de inscripción H1, resúmenes de propuesta/fuente/adaptador, estado de enlace del host,
  frescura e incógnitas explícitas en la TUI.
- Exponer solo el nivel mínimo 0 `platform-identity` y `compute-summary`
  alcance a través de la fachada del corredor mecanografiado.
- Mantenga los datos de los candidatos efímeros hasta que se obtenga un backend cifrado y con recuperación verificada.
  está explícitamente desbloqueado; mostrar la persistencia como no disponible de lo contrario.
- Revelar la base de recuperación existente de LUKS/R2 y la integridad del libro mayor de auditoría
  como requisitos previos para futuros trabajos de acogida directa.
- Permitir instantáneas Btrfs locales sin cifrar como R1 solo para desarrollo de rutina;
  conservar R2 como protección requerida para kernel, NVIDIA, arranque, gráficos,
  cambios de almacenamiento y cifrado.
- Vincular el recorrido del diagnóstico de iluminación con la misma evidencia, alcance y parada
  condiciones mientras se mantienen cerradas las comprobaciones de Nivel 1/Nivel 2/protegido/de activación del dispositivo.

**Criterios de finalización:** la TUI puede presentar la propuesta exacta de anfitrión directo,
alcance, resúmenes, estado de recuperación, distinción de hechos candidato versus host y bloqueado
motivo de activación; Ninguna observación o mutación puede comenzar a partir de un material no aprobado o
estado obsoleto.**Estado:** El estado de solo lectura de TUI a `jarvisd` y la proyección de recuperación son
implementado. el
Marca de suscripción TUI `--connect-jarvisd` llamadas solo `health.read` y
`activation.status` sobre el socket Unix exclusivo del propietario; no puede iniciar un
observación o mutación del estado huésped. El broker tipado y transaccional v2
El almacenamiento SQLite respaldado por LUKS permanece probado, con identidad de montaje/dispositivo
controles, manejo de ruta sin seguimiento controlado por el propietario, activación duradera de un solo uso
vinculante y verificación de integridad de registros. H1 Tier-0 está disponible para el
plataforma/alcance informático aprobado; la persistencia de hechos restringida permanece deshabilitada.

### Fase 3: aprobaciones exactas sin mutación del huésped

**Objetivo:** implementar aprobaciones de Jarvis exactas y deliberadas utilizando solo una opción no operativa
simulador.

**Secciones y entregables**

- Representación y ciclos de vida distintos para solicitudes de Codex versus aprobaciones de Jarvis.
- Enlace inmutable de comando/procedimiento/adaptador con ID de sesión/tarea, exacto
  ejecutable y `argv[]`, directorio de trabajo, objetivos, resumen de políticas, estado
  semántica de resumen, nonce, caducidad y de un solo uso.
- Interacción de aprobación de dos pasos sin enfoque y pegado de aprobación predeterminados
  rechazo.
- Aceptar, rechazar, cancelar, caducar, reemplazar, modificar, reiniciar, estado obsoleto,
  pruebas de solicitud simultánea, repetición y sesiones cruzadas.
- Vista previa segura que no puede ejecutar ni responder a una solicitud del servidor de aplicaciones.

**Criterios de finalización**

- Las pruebas adversarias no pueden ampliar, falsificar, confundir, reutilizar o reproducir una
  aprobación.
- Las decisiones de aprobación nunca se convierten en ejecución del host o respuestas del servidor de aplicaciones.
- Cualquier discrepancia, vencimiento, error de auditoría o estado inesperado detiene la progresión.

**Estado:** Completo y validado con dispositivos; Sólo simulador.

### Fase 4: observaciones registradas de solo lectura

**Objetivo:** agregar recopilación de evidencia limitada a la sombra del host directo
consola, primero desde dispositivos y luego desde una estación de trabajo registrada explícitamente
adaptadores. La estación de trabajo es primaria; El trabajo de VM es un ensayo opcional.

#### 4A. Requisito previo del laboratorio de escenarios de Fedora

- Definir perfiles gemelos del sistema Fedora, matrices de escenarios, reinicio y
  contratos de aislamiento, brechas físicas y resúmenes de cobertura.
- Mantener el trabajo de VM opcional y centrado en el software; nunca lo trates como algo físico
  evidencia de hardware.

**Criterios de finalización:** los escenarios declarados analizan, validan, aíslan, restablecen y
rechazar el estado no declarado; la cobertura sigue siendo explícitamente la Etapa 1.

**Estado:** Accesorio completo.

#### 4B. Contrato de inscripción de controlador y estación de trabajo L1

- Definir operaciones de controlador con tipo deshabilitado y máquina de estado del ciclo de vida.
- Definir catálogo de fuentes, propuesta de inscripción de 90 hechos, tres niveles de consentimiento,
  accesorios exactos de solicitud/respuesta y estado de revisión sin autoridad.

**Criterios de finalización:** los contratos se validan, todas las operaciones/fuentes/grupos están
deshabilitado hasta una transición explícita, el enlace del host no se resuelve hasta que se apruebe,
y no existe ningún servicio de controlador.

**Estado:** Punto de control estructural completo; la autoridad de inscripción permanece desactivada.

**Actualización de implementación (06/08/2026):** ahora una fachada de intermediario mecanografiada solo para elementos fijos
aplica un alcance mínimo de nivel 0, enlace de resumen, caducidad, rechazo de reproducción y
negación del modo en vivo. Los hechos restringidos siguen siendo efímeros hasta que se determine de forma independiente.
se proporciona backend cifrado certificado; la activación aún está desactivada.

#### 4C. Plano completo de VM de estación de trabajo Fedora L2

- Defina una imagen de estación de trabajo completa con perfiles de arranque gráficos y sin cabeza.
- Definir comprobaciones de preparación, bloqueos de imagen/dominio, puertas de aprovisionamiento, novedades.
  superposiciones, reinicio y límites de integración gráfica.
- Agregue analizadores de nivel 0 solo para dispositivos para sistema operativo, kernel/arquitectura, topología de CPU,
  memoria/NUMA y respuestas de escenario declaradas.

**Criterios de finalización:** todos los analizadores y esquemas rechazan archivos mal formados, duplicados,
  datos inconsistentes, no UTF-8, secretos o no declarados; no se descarga ninguna VM,
  aprovisionado, iniciado o tratado como evidencia física.**Estado:** Plano y punto de control de accesorios completos; La máquina virtual real permanece
opcional y no provisionado.

#### 4D. Puertas H de host directo

- H1: inscripción de solo lectura limitada y enlace de fuente.
- H2: diseño de recuperación por capas.
- H3/H4: establecer y probar límites de recuperación.
- H5: modo de funcionamiento sombra/solo lectura.
- H6: primer caso de iluminación acotado.

**Criterios de finalización:** cada lectura en vivo está registrada, delimitada, redactada,
de un intento, con etiqueta de actualización, atribuida y vinculada a auditoría; lecturas protegidas,
Activación de sesión, monitoreo de entrada, estado del conector y escrituras físicas.
permanecer cerrado por separado.

**Estado:** Existen pruebas de recuperación de host directo y adaptadores de iluminación en el
registros de tiempo de ejecución. El brillo de la pantalla y la luz del teclado confirmados por el usuario
se registran las reparaciones; La activación H1 y una nueva observación del huésped inscrito son
aún pendiente.

#### 4E. Primer caso de uso de iluminación

- Diagnosticar el brillo de la pantalla, la iluminación del teclado, las teclas de acceso rápido, la integración del escritorio,
  Topología de GPU, potencia de tiempo de ejecución e historial de versiones/cambios como capas separadas.
- Mantenga las lecturas de sysfs/proc/proc de nivel 0 separadas de la plataforma/proveedor de nivel 1,
  Enlace WMI de nivel 2, asociación de conector de nivel 3, UPower/sesión y cualquier
  mutación.
- Preparar planes de reparación con objetivo exacto, validación, reversión e independientes.
  revisión.

**Criterios de finalización:** la evidencia distingue la presencia del proveedor,
comportamiento solicitado/real, ruta del evento de entrada, integración de escritorio y datos físicos.
efecto; ninguna hipótesis se promueve simplemente a partir de la correlación.

**Estado:** Preparado y parcialmente observado; El síntoma manual original es
resuelto por el usuario, mientras que el registro de evidencia de la máquina de Jarvis permanece
es de solo lectura y no debe inferir el estado actual del servicio a partir de esa confirmación.

### Fase 5: Fundación de mutación supervisada

**Objetivo:** autorizar una mutación reversible estrecha detrás de un sistema operativo separado
límite de autorización.

**Secciones y entregables**

- Servicio de ejecutor de propiedad raíz con Polkit/autorización equivalente.
- Protocolo de adaptador registrado con ejecutable fijo, argumentos, conjunto de objetivos,
  tiempo de espera, límites de salida, lista de entornos permitidos y versión.
- Evidencia previa al cambio, aprobación exacta del comando, reversión de acciones específicas,
  validación posterior a la condición, revisión independiente y finalización de la auditoría.
- Ensayo de instalación y scratch aislado/representante de VM antes del primer anfitrión
  uso.

**Criterios de finalización**

- Uno y sólo un adaptador reversible alcanza la madurez Etapa 4.
- La recuperación se prueba y se vincula a la evidencia.
- TUI/broker/modelo no puede llamar comandos arbitrarios ni ampliar el adaptador.
- La aprobación es de un solo uso, exacta, vigente, vinculada al estado e independiente.
  verificado.

**Estado:** Fundación de admisión implementada y aprobada de forma independiente como
cerrado por falla. `vm-lab/scripts/phase5_executor.py` no tiene ningún adaptador habilitado o
ruta de mutación del huésped; no hay ningún ejecutor supervisado instalado.

### Fase 6: consola operativa completa

**Objetivo:** terminar la consola de la estación de trabajo sin debilitar los límites.

**Secciones y entregables**

- Errores: intentos inmutables, revisiones de diagnóstico, restricciones y desinfectados.
  salida.
- Lecciones: recuento de pruebas, revisiones de candidatos, activación/suspensión y
  Promoción exclusiva para usuarios.
- Recuperación: límites, instantáneas, pruebas de copia de seguridad/restauración, RPO/RTO y brechas.
- Configuración: política versionada, valores predeterminados seguros, diferencias completas y revisión de alto riesgo.
- Auditar la integridad, el estado de cifrado, el estado del receptor remoto y las vistas de recuperación.
- Recomendaciones vinculadas a evidencia y exportaciones de incidentes/mantenimiento redactadas.
- Notificaciones de escritorio opcionales que no pueden aprobar el trabajo.
- Accesibilidad, solo teclado, cambio de tamaño, modo simple, privacidad, recuperación ante fallas,
  y reconectar las pruebas de aceptación.

**Criterios de finalización**- Cada vista en `docs/tui-contract.md` es funcional y está probada.
- Los informes están redactados, exportables, vinculados a evidencia y reproducibles.
- Errores de bloqueo/reconexión/auditoría/almacenamiento bloqueado que fallan al cerrarse.
- La consola etiqueta con precisión simulados, no implementados, obsoletos, inferidos,
  con alcance de sandbox y evidencia viva.

**Estado:** Completo para la puerta de liberación de solo lectura construida. Errores/
intentos, lecciones, recuperación, configuración, auditoría, notificaciones, estado de reconexión,
Las fallas de almacenamiento bloqueado y la entrega explícita de exportación local redactada son visibles.
y probado en la vista Operaciones. Mutación, ejecución, persistencia de hechos y
la autoridad de aprobación permanece fuera de la TUI; El despliegue y la aceptación en vivo son
puertas separadas.

### Fase 7: Aumento de la autonomía limitada

**Objetivo:** automatizar selectivamente solo procedimientos específicos, maduros y revocables
flujos de trabajo.

**Secciones y entregables**

- Reunir evidencia independiente sobre procedimientos supervisados exitosos repetidos.
- Promover revisiones de procedimientos versionados a través de revisión de madurez de capacidades.
- Definir políticas estrechas de Etapa 5, monitoreo, condiciones de detención, revocación y
  recuperación.
- Mantener desactivada la lista segura preautorizada hasta que se gane un procedimiento específico
  Etapa 5 y recibe la aprobación explícita del usuario.

**Criterios de finalización**

- La automatización es específica del procedimiento, limitada, auditable, monitoreada, revocable,
  y recuperable.
- Ninguna lección, éxito repetido, modelo de confianza o sesión activa crea
  amplia autoridad.
- Seguridad, arranque, firmware, identidad, cifrado, almacenamiento y acceso remoto
  las acciones nunca saltan la revisión independiente.

**Estado:** Planificado e inicialmente deshabilitado. Opcional; no es necesario para una caja fuerte
liberación supervisada.

## 6. Puertas de madurez de capacidad

| Etapa | Significado | Uso permitido | Pruebas de promoción |
|---|---|---|---|
| 0 - Definido | Existen contratos/instrucciones | Sólo documentación | Esquemas y políticas revisados ​​|
| 1 — Validado | Pasan las pruebas estáticas/unitarias/de accesorios | Uso de accesorios | Pruebas deterministas y cobertura |
| 2 — Ensayado | Pases de ensayo aislados representativos | Objetivo de laboratorio/rasguño | Restablecimiento, aislamiento y resultado repetible |
| 3 — Observado | La evidencia de producción de solo lectura funciona | Observación en vivo | Evidencia limitada, redactada y auditada |
| 4 — Supervisado | La mutación probada en recuperación funciona | Aprobación humana exacta | Pre-estado, reversión, poscondición, revisión independiente |
| 5 - Automatizado | Pruebas repetidas y auditoría externa | Política estrecha preaprobada | Transición, seguimiento y revocación de políticas explícitas |

Cada adaptador avanza de forma independiente. Una fase completada no promueve todos
capacidad en esa fase.

## 7. Hoja de ruta de recuperación y host directo

El modelo de recuperación de estaciones de trabajo tiene cuatro límites:

- **R0:** registrar y copiar de forma independiente los archivos de proyecto afectados; no sistema operativo
  protección.
- **R1:** instantánea del sistema de archivos/subvolumen local; no puede cubrir otros subvolúmenes,
  `/boot`, EFI, partición, firmware o falla del dispositivo.
- **R2:** copia de seguridad externa cifrada del sistema que cubre la raíz declarada, el hogar,
  máquinas anidadas, arranque y límites EFI con comparación independiente y
  restaurar la prueba.
- **R3:** recuperación fuera de línea de todo el dispositivo por pérdida de partición/dispositivo; requiere
  pruebas separadas de dispositivos de arranque y de hardware.

La finalización de la recuperación requiere resolución de topología, límites de secreto/privacidad,
verificación previa, aprobación exacta, un intento, finalización de auditoría, independiente
comparación y una restauración probada. Una copia de seguridad no probada nunca se presenta como
recuperable.

## 8. Hoja de ruta de validación transversal

### Contrato y pruebas unitarias

- Esquema/canonicalización, estabilidad del resumen, monotonicidad del riesgo, aprobación.
  caducidad/repetición/vinculación de estado, determinismo reductor/idempotencia, desinfección,
  generación de registro a menú y motivos de estado deshabilitado.

### Pruebas de integración- Transmisiones de App Server fijadas falsas y reales; reconectar, reanudar, dirigir,
  interrupción, compactación, capacidad, base de datos bloqueada, MCP fallido, libro mayor corrupto,
  y separación de solicitud de aprobación.

### pruebas TUI

- Flujos de trabajo de teclado sin cabeza en tamaños compactos/anchos, seguridad de enfoque, pegar
  rechazo, cancelación alcanzable, semántica en modo plano, restauración de terminal y
  limpieza de accidentes.

### Pruebas de seguridad

- Inyección rápida en registros/docs/salida MCP; escapes/hipervínculos de terminal;
  inyección de argumentos; aprobaciones falsificadas/obsoletas/repetidas/ampliadas;
  reemplazo de ruta/enlace simbólico; y prueba de que ninguna interfaz comprometida tiene un aspecto crudo
  Canal privilegiado.

### Pruebas de lanzamiento

- Sintaxis/metadatos, complemento/habilidad/config/esquema/política/gancho/validación de MCP,
  redacción, integridad del libro mayor, casos representativos de solo lectura, independientes
  revisión de seguridad, generación de manifiesto de lanzamiento e inicio de procesos separados
  validación.

## 9. Secuencia de lanzamiento y actualización automática

1. Construya en un árbol o rama de trabajo aislado.
2. Ejecute todas las pruebas deterministas e inspeccione la diferencia completa.
3. Genere y revise el manifiesto de lanzamiento y la diferencia de capacidad/permiso.
4. Obtener una revisión de seguridad independiente para políticas, ganchos, MCP, aprobación, auditoría,
   o cambios de privilegios.
5. Cree una versión versionada inmutable conservando la anterior.
6. Solicitar aprobación ligada al compendio de manifiesto.
7. Active atómicamente usando un puntero o cambiando el nombre del directorio.
8. Validar desde un proceso separado y revertir al inicio, política, MCP o
   fallo del libro mayor.
9. Registrar la liberación, el revisor, la aprobación, la activación y el resultado externamente.

## 10. Estado maestro histórico — 2026-08-07

Esta instantánea se conserva como prueba y se reemplaza por la TUI actual.
autoridad por `current-product-state.md` y `tui-contract.md`.- Fases 0–3: implementadas y validadas.
- Fase 1 de aceptación del servidor de aplicaciones en vivo: aprobada el 6 de agosto de 2026 para los anclados
  `codex-cli 0.146.0`; lecturas de cuenta/capacidad, ciclo de vida del subproceso, uno
  Sólo conversación Sólo lectura Girar, dirigir/interrumpir, reconectar/reanudar y
  La desconexión limpia se registra en el informe de tiempo de ejecución. Ninguna autoridad anfitriona fue
  usado.
- Lanzamiento de TUI en vivo de la fase 2: inicio fuera de línea y las 53 pruebas de TUI validadas en
  el proyecto local `.venv` con `textual==8.2.8` anclado; servidor de aplicaciones en vivo
  la aceptación se registra en la Fase 1.
- Fase 3: sólo simulador; sin ejecución del host.
- Fase 4: contratos estructurales/accesorios e iluminación delimitada preparada
  las observaciones están presentes; la pista de sombra del host directo es primaria y VM
  sigue siendo opcional y no provisionado.
- Fase 5: se implementa la fundación ejecutor de sólo admisión y de forma independiente
  aprobado; no hay ningún adaptador, autorización de sistema operativo ni ejecutor supervisado instalado.
- Fase 6: completa para la consola de solo lectura construida. Las operaciones
  La proyección ahora cubre falla, lección, recuperación, configuración, integridad de auditoría,
  estados de almacenamiento bloqueado, reconexión y notificación. Las exportaciones redactadas tienen un
  límite de entrega local explícito sin sobrescritura. Laboratorio VM local completo y TUI
  pase de suites; el despliegue y la aceptación en vivo siguen siendo decisiones separadas.
- Fase 7: deshabilitada y no requerida para liberación supervisada.
- Expansión de host útil limitada (preparada el 7 de agosto de 2026): iluminación pasiva/DRM
  se implementan y prueban contratos de observación y diagnóstico determinista;
  Las operaciones de reparación de iluminación y perfil de potencia están representadas en el catálogo.
  pero permanece sin registrar y deshabilitado. Credenciales, acceso arbitrario a la red,
  los registros protegidos y las sondas de activación de dispositivos siguen no disponibles.
- Controles de iluminación TUI (construido el 7 de agosto de 2026): efecto gráfico, brillo,
  Los controles de velocidad, dirección, color y zona generan una vista previa escrita del
  Interfaz del controlador Acer RGB. La acción Aplicar permanece deshabilitada y no puede llamar
  el conductor directamente.
- Objetivo CLI del Codex: `0.146.0`; La conexión al servidor de aplicaciones y los turnos en vivo permanecen
  aceptación explícita.
- Libro mayor de auditoría Runtime v2: verificado como válido con 85 eventos en la instantánea.
- Base de datos de conocimiento: actual y recientemente actualizada.
- Instantánea local de R1: completada el 7 de agosto de 2026 a las
  `/var/lib/jarvis-r1-20260807T085200Z`, que cubre solo lectura `root`, `home`,
  y `var/lib/machines` instantáneas; boot/EFI permanecen fuera de R1.
- Conjunto de sistema R2 cifrado nuevo: completado y verificado de forma independiente
  2026-08-07. Instantánea restic `d28c9d2e` con etiqueta
  `jarvis-r2-system-set-20260807T090408Z` pasó `check --read-data`, restaurado
  en `/var/lib/jarvis-r2-restore-20260807T090408Z/data`, y emparejó los cinco
  límites con cero desajustes y sin lagunas en las pruebas; el objetivo restaurado es
  retenido como de solo lectura. La capacidad de arranque y la reconstrucción completa quedan fuera
  esta prueba R2 a nivel de archivo.
- Manifiesto de lanzamiento: regenerado y verificado con 650 entradas después del
  iluminación, control TUI, hoja de ruta, corredor, puerta de almacenamiento y aceptación en vivo
  actualizaciones.
- Reparaciones exitosas confirmadas por el usuario del brillo de la pantalla y del teclado RGB
  están registrados en `docs/use-case-lighting-controls.md`; un nuevo anfitrión inscrito
  Aún se requiere observación antes de afirmar el estado actual del servicio/módulo.
- Construcción de la puerta de ejecución H1: los contratos solo preparados ahora fijan la decisión exacta,
  enlaces de política, servicio, transporte, adaptador y almacenamiento; fresco autónomo
  La ejecución de la revisión está disponible a través de `automation/run-independent-review.sh`.
  La revisión independiente final pasó las verificaciones de artefactos/pruebas, pero mantiene la activación.
  bloqueado porque la interfaz SQLite estándar de Python no elimina el
  carrera de nombre de ruta de diario/base de datos del mismo UID. Esto está registrado en
  `runtime/reports/2026-08-07-h1-runtime-independent-review-final.json`.
- Se prepara y se elabora un prototipo de libro mayor de autoridades vinculado a descriptores y sin sidecar.
  se ejercita de forma independiente, pero permanece sin cables. Su punto de control en el archivo detecta
  truncamiento con el punto de control retenido; reversión completa de la instantánea todavíarequiere un punto de control monótono autenticado externo y permanece bloqueado.
- El contrato del punto de control TPM y el emulador HMAC exclusivo para dispositivos están preparados y
  revisado de forma independiente. El índice real de TPM NV, la clave protegida y el backend
  La integración permanece intencionalmente desconfigurada y bloqueada en espera de una evaluación por separado.
  decisión de configuración privilegiada y revisión de activación final.
- Activación del tiempo de ejecución H1 Tier-0: completada el 7 de agosto de 2026 después de una nueva independencia
  aprobación. `jarvisd.service` está activo como servicio exclusivo del usuario; el exacto
  cuatro adaptadores aprobados exponen 14 hechos de solo lectura, sin persistencia de hechos,
  mutación, privilegio, acceso a la red o al dispositivo. Una observación de seguimiento también
  aprobado y registrado en
  `runtime/reports/2026-08-07-h1-followup-observation-20260807T162422Z.json`.
- Puente de estado TUI fase 2B: completo para proyección de estado de solo lectura. el
  TUI permanece fuera de línea de forma predeterminada y requiere `--connect-jarvisd` explícito para
  mostrar el estado del servicio H1; no tiene método de observación ni ejecutor.
- Base de admisión de la fase 5: completa para operación/parámetro/objetivo/
  vinculación de políticas, vencimiento e integración confiable de un libro mayor de un solo uso. el ejecutor
  permanece deshabilitado y no hay comando real, persistencia o ruta de mutación de políticas
  existe. Veredicto de revisión independiente: APROBAR la base preparada.
- Proyección operativa de la Fase 6: la TUI ahora muestra la Fase 5 redactada
  estado de ensayo y evidencia de reversión junto con el estado H1/recuperación; eso
  permanece como de solo lectura y no puede enviar solicitudes de ejecución.
- Configuración del proveedor de energía del host de fase 5: TuneD y `tuned-ppd` están activos con el
  perfil `jarvis-balanced` compatible con hardware; `tuned-adm verify` pasa y
  la API PPD estándar informa `balanced`. La evidencia está en
  `runtime/reports/2026-08-07-power-profile-provider-activation.json`. el
  El adaptador de estado de proveedor de solo lectura ahora está construido, probado y de forma independiente.
  aprobado en `runtime/reports/2026-08-07-power-profile-status-adapter-review.json`,
  pero sigue sin estar registrado y es inaccesible desde la TUI. El adaptador de mutación
  permanece sin implementarse pendiente de autorización, ensayo y revisión independiente.

## 11. Siguiente secuencia recomendada1. [Completado el 6 de agosto de 2026] Instale `textual==8.2.8` en un entorno aislado
   e iniciar la TUI en modo fuera de línea; pasa la suite TUI de 53 pruebas.
2. [Completado el 6 de agosto de 2026] Ejecute la prueba de humo del servidor de aplicaciones real anclado con
   consentimiento explícito; verificar cuenta/capacidad, inicio/reanudación del hilo, uno
   Turno de conversación, interrupción y recuperación de desconexión.
3. [Completado el 6 de agosto de 2026] Registre el éxito de iluminación final confirmado por el usuario y
   configuración del controlador RGB del teclado como una nota de implementación limitada y no secreta.
4. [Completado el 6 de agosto de 2026] Concilie la documentación de iluminación y regenere
   el manifiesto de lanzamiento.
5. Continuar con la integración de la sombra del host directo de la Fase 2B/4D: reemplazar el residual
   Carrera de diario/nombre de ruta de SQLite con un límite de almacenamiento que tenga en cuenta el descriptor,
   vuelva a ejecutar la revisión autónoma y luego (solo después de una decisión separada del usuario final)
   Considere una observación de nivel 0 acotada. Aquí no se implica ninguna activación.
6. [Completado el 7 de agosto de 2026] Cree el conjunto de instantáneas R1 local y actualice la
   conjunto de sistema R2 cifrado; verificar los datos del repositorio, restauración completa y los cinco
   límites de forma independiente.
7. [Completado el 7 de agosto de 2026] El producto solo desechable
   El candidato `jarvis.rehearsal.marker@1.0.0` fue aprobado de forma independiente y
   ejercido una vez con autorización explícita del usuario. El presente→ausente
   transición, enlace de destino, marcador final vacío y limpieza de raíz temporal
   pasado; la evidencia está en
   `runtime/reports/2026-08-07-phase5-rehearsal-marker.json`. queda
   no registrado y discapacitado.
8. [Configuración del proveedor completada el 7 de agosto de 2026] Descubrimiento del proveedor TuneD/PPD,
   selección de perfil compatible con hardware y verificación de identidad D-Bus.
   completo. A continuación, revise el candidato de selección de perfil de poder en
   `docs/phase-5-host-adapter-power-profile-candidate.md`; no implementar o
   Registre el adaptador mutante hasta la autorización del sistema operativo, el ensayo y una nueva versión.
   revisión independiente están completas.
9. [Adaptador de estado de solo lectura aprobado el 7 de agosto de 2026] El proveedor fijo de solo GetAll
   El lector y las pruebas enfocadas pasaron una nueva revisión independiente. Guárdalo
   no registrado hasta que se tome una decisión de integración por separado.
10. [Ensayo de transición desechable aprobado y completado el 7 de agosto de 2026] El en memoria
    `balanced -> performance -> balanced` y transiciones de ahorro de energía aprobadas
    Comprobaciones exactas de postcondición y reversión sin llamadas D-Bus, sistema de archivos
    escribe, o invocación del ejecutor. La evidencia está en
    `runtime/reports/2026-08-07-power-profile-transition-rehearsal.json`; el
    nueva revisión se registra en
    `runtime/reports/2026-08-07-power-profile-transition-rehearsal-review.json`.
11. [Límite de autorización definido el 7 de agosto de 2026] La sesión actual exacta,
    Límite PPD/Polkit de un solo uso de 60 segundos confirmado por TUI y advertencia de solo notificación
    La política está codificada en
    `vm-lab/controller/power-profile-authorization-policy.json` y validado
    por `vm-lab/scripts/power_profile_authorization.py`. Un nuevo independiente
    revisión aprobó el límite; el camino de la mutación viva sigue sin estar registrado.
    La evidencia está en
    `runtime/reports/2026-08-07-power-profile-authorization-boundary-review.json`.
12. [Aprobado de forma independiente el 7 de agosto de 2026] El adaptador supervisado preparado en
    `vm-lab/scripts/power_profile_mutation.py` pasó una nueva revisión independiente.
    Vincula el transporte PPD fijo, la condición previa del perfil anunciado, TUI y
    puertas de sesión activa, notificaciones previas a la mutación de mejor esfuerzo, un configurador,
    validación posterior a la condición y semántica de falla de no reversión/nueva aprobación.
    Sigue sin estar registrado y no tiene autorización de ejecución en vivo. evidencia
    está en `runtime/reports/2026-08-07-power-profile-mutation-adapter-review.json`.
13. [Aprobado independientemente 2026-08-07] El puente ejecutor preparado en
    `vm-lab/scripts/power_profile_executor_bridge.py` vincula parámetros exactos,
    objetivo fijo, resumen de políticas registradas, caducidad, revisión del adaptador confiable,
    y aprobación de un solo uso antes de llamar al adaptador revisado. queda
    no registrado y discapacitado. La evidencia está en
    `runtime/reports/2026-08-07-power-profile-executor-bridge-review.json`.
14. [Pase con condiciones: revisado independientemente 2026-08-07] Atado el puente
    al descriptor preparado vinculado `PowerProfileAuthorityLedger`, con exactitud
    esquema/diario/validación sincrónica, reapertura/reproducción, duplicado, corrupción,
    y pruebas de fallo del libro mayor. La revisión no encontró ningún defecto en el código de bloqueo, pero suSandbox no pudo crear directorios temporales para cinco pruebas de libro mayor; el
    La ejecución de escritura local pasó las 39 pruebas enfocadas. Una nueva escritura posterior
    la repetición pasó 39/39 con un directorio desechable limpio. Mantener la ejecución en vivo
    deshabilitado hasta que se tome una decisión de implementación por separado. La evidencia está en
    `runtime/reports/2026-08-07-power-profile-durable-ledger-binding-review.json`
    y `runtime/reports/2026-08-07-power-profile-focused-writable-rerun.json`.
15. [Completado el 7 de agosto de 2026] Conciliar los contratos de póliza activos H1 Tier-0 con
   controlador, corredor, observación, modelo de VM, preparación, servicio y
   expectativas fijas sin ampliar la autoridad. La suite completa de VM-lab
   pasa 181 pruebas; la presentación TUI/corte sin cabeza supera 17 pruebas
   (Se omitieron cuatro pruebas textuales cuando la dependencia opcional no está disponible).
16. [Completado el 7 de agosto de 2026] Construya la vista Operaciones de solo lectura de la Fase 6 con
   proyección de fracaso inmutable, política de lecciones respaldada por evidencia, recuperación
   límites, configuraciones seguras, estado de auditoría y notificaciones. no tiene
   ruta de observación, comando, persistencia, mutación de políticas o aprobación.
17. [Completado el 7 de agosto de 2026] Agregar un operativo redactado acotado determinista
   carga útil de exportación. Se genera únicamente en la memoria; sin escritura automática de archivos,
   existe un receptor remoto o una ruta de aprobación.
18. [Completado el 7 de agosto de 2026] Completar las vistas operativas y la aceptación de la Fase 6.
   pruebas: entrega de exportación local explícita y redactada, almacén bloqueado/integridad de auditoría
   proyecciones de cierre a prueba de fallas, etiquetado de estado de reconexión/a prueba de choques, compacto y
   Amplia aceptación del teclado e integración de pantalla solo para notificaciones. No
   se produjo el despliegue o la ampliación de la autoridad.
19. Deje la automatización de la Fase 7 desactivada hasta que un procedimiento específico pase a la Etapa 5.
20. [Revisado con condiciones 2026-08-07] Construir iluminación acotada/DRM
    observación y diagnóstico, controles de vista previa gráfica y exactitud deshabilitada
    Fijaciones para reparación de iluminación y operación de perfil de potencia. La nueva reseña
    no se encontraron hallazgos de seguridad altos o medios; su reproducción TUI completa fue
    limitado por los permisos sandbox AF_UNIX. La evidencia está en
    `runtime/reports/2026-08-07-bounded-authority-expansion-v1.json`.
21. [Promoción de un solo uso completada el 7 de agosto de 2026] Promocionar y ejecutar exactamente uno
    observación de iluminación pasiva a través del método Jarvisd exclusivo para el propietario. el
    la autorización duradera se consumió después de la lectura limitada; el resultado fue
    efímero y ningún hecho o estado de hardware persistió o mutó. el
    Se mantiene el límite de estado sin conector/activación del dispositivo. Reparación de iluminación y
    La mutación del perfil de potencia permanece deshabilitada y requiere revisiones y controles por separado.
    aprobaciones para cualquier promoción futura.
22. [Construido el 7 de agosto de 2026] Agregar un ejecutor de reparación de iluminación cerrado por falla
    límite con enlaces exactos de diagnóstico/plan/revisión, semántica de un solo uso y
    requisitos explícitos de reversión de nuevas aprobaciones. No puede mutar al huésped.
23. [Construido el 7 de agosto de 2026] Completa el ejecutor TuneD/PPD supervisado
    contratar y agregar vistas previas de aprobación de mutación solo de TUI para reparación de iluminación y
    perfiles de potencia. Ambos siguen siendo sólo de simulación y no registrados. Separado
    los paquetes de revisión de solo lectura se encuentran en `runtime/review-prompts/`; la evidencia está en
    `runtime/reports/2026-08-07-mutation-construction-v1.json`.
24. [Completado el 8 de agosto de 2026] Resuelva la limitación de validación de TUI AF_UNIX con
    una ejecución de escritura: se aprobaron 70 pruebas y se aprobaron cinco pruebas textuales opcionales
    saltado. Vincule ambas rutas de mutación a campos explícitos de aprobación de un solo uso.
    resúmenes de revisión independiente y reglas de reversión de nuevas aprobaciones. Seleccione el
    primer objetivo en vivo propuesto como una transición TuneD/PPD a `balanced`; capturar
    el perfil previo real en el momento de la activación y se detiene en estado obsoleto/no operativo.
    No se realizó ningún despliegue ni mutación del huésped.
25. [Construido el 8 de agosto de 2026] Agregue el marco de control de energía acotado que cubre
    resúmenes de Powertop de solo lectura, CPU EPP/turbo, potencia de tiempo de ejecución Intel/NVIDIA
    controles y perfiles TuneD/PPD. Los controles están incluidos en la lista permitida, con control térmico,
    de un solo uso, encuadernado en reversión y con vista previa en la TUI. El ejecutor permanecedeshabilitado en espera de una revisión e implementación independiente específica de energía
    decisión. La evidencia está en
    `runtime/reports/2026-08-08-energy-control-framework-v1.json`.
26. [Construido el 8 de agosto de 2026] Agregue un inventario de paquetes RPM de solo lectura a la TUI
    con vistas completas, alfabéticas, por categorías y orientadas a propósitos. Paquetes
    están clasificados para NVIDIA/GPU, Intel, GNOME, iluminación, kernel, desarrollo,
    virtualización, audio, redes, seguridad y otros fines. el proveedor
    es fijo, sin shell, con tiempo de espera limitado, acotado y libre de mutaciones. evidencia
    está en `runtime/reports/2026-08-08-package-inventory-v1.json`; independiente
    Sigue siendo necesaria una revisión antes de tratar el escaneo como un hecho vivo de Jarvis.
27. [Construido el 8 de agosto de 2026] Enriquezca el inventario de paquetes con locales acotados
    consultas de dependencia/dependencia inversa, propiedad de archivos instalados, DNF
    historial de transacciones y datos de origen del repositorio. Las consultas de asesoramiento son
    explícitamente conectado a la red y deshabilitado de forma predeterminada. La evidencia permanece
    efímero en la TUI pendiente de revisión independiente.
28. [Construido pendiente de revisión 2026-08-08] Ampliar el inventario de paquetes a Instalado/Disponible/
    Modos combinados/actualizados con versiones, repositorios, RPM autorizados
    conflictos, alternativas, gráficos de dependencia, propiedad, historial de transacciones,
    y avisos explícitamente conectados a la red. El plan completo está en
    `docs/package-availability-and-compatibility-plan.md`. Disponible en caché,
    vistas combinadas y actualizadas, paginación limitada, relación autorizada
    Se implementan tipos y registros de recomendaciones etiquetados con evidencia.
    La actualización de la red, los avisos y las transacciones de paquetes permanecen deshabilitados.
29. [Completado el 8 de agosto de 2026] Haga que la pestaña Paquetes cargue el RPM instalado
    inventario automáticamente en un trabajador en segundo plano la primera vez que se abre, almacenarlo en caché para
    la sesión TUI y gire el botón Escanear manual a Actualizar. Un local vivo
    leer observó 2.257 paquetes instalados; la prueba textual sin cabeza real
    verifica la carga automática.
30. [Completado el 8 de agosto de 2026] Repare la regresión de representación de la TUI de paquetes que
    trató un resultado de texto completo como un iterable de caracteres. Reemplace el
    registro de inventario no estructurado con una mesa con rayas de cebra seleccionable mediante teclado,
    dos barras de herramientas compactas, una ventana gráfica de tabla mínima garantizada de diez filas, un compacto
    resumen de estado y un panel de detalles separado. Al seleccionar una fila ahora se llena el
    campo exacto del nombre del paquete y presenta su estado, categoría, origen y
    propósito inferido sin otra exploración. El mismo campo ahora realiza un verdadero
    filtro que no distingue entre mayúsculas y minúsculas en Enter entre nombres, versiones, resúmenes,
    categorías, finalidades, orígenes y estados de instalación; enviando un vacío
    El campo borra el filtro.
31. [Construido e integrado de solo lectura 2026-08-08] Agregue un Power dedicado
    pestaña con descubrimiento automático limitado de TuneD/tuned-ppd, Intel P-state y
    Controles de frecuencia de CPU, perfiles de plataforma ACPI, tiempo de ejecución Intel/NVIDIA DRM
    alimentación, parámetros expuestos del módulo i915/NVIDIA, fuentes de alimentación, Powertop
    instalación y presencia del controlador del kernel NVIDIA. Se muestra el menú de la sección
    valores actuales, opciones anunciadas y fuentes de evidencia exactas. Dispositivo-
    Las sondas de activación, los privilegios, el acceso a la red y todas las mutaciones permanecen deshabilitados.
    La evidencia se encuentra en `runtime/reports/2026-08-08-power-inventory-v1.json`.
32. [Construido y probado pendiente de revisión/implementación 2026-08-08] Agregar supervisado
    cambios en vivo para los cinco controles de energía incluidos en la lista permitida: perfil de energía del escritorio,
    CPU EPP, CPU turbo, PM de tiempo de ejecución de GPU Intel y PM de tiempo de ejecución de GPU NVIDIA. cada
    La operación vincula un preestado observado, cambia una configuración, verifica su
    poscondición y reemplaza el único registro duradero de deshacer del último cambio.
    Deshacer requiere una nueva confirmación TUI y autorización de escritorio, rechaza
    deriva, y restaura sólo el estado previo capturado. Una interrupción o parcial
    La aplicación se expone como una recuperación revisada por separado utilizando el método fsynced preparado.
    registro; nunca retrocede automáticamente. El ayudante raíz no tieneshell, ruta/valor arbitrario, red o superficie de reversión automática.
    Los cambios de perfil y turbo fallan cerrados sin evidencia térmica legible y
    están bloqueados a 90°C o más.
    La evidencia se encuentra en `runtime/reports/2026-08-08-power-live-control-v1.json`.

## 12. Documentos fuente

- `docs/platform-architecture.md`
- `docs/tui-implementation-plan.md`
- `docs/tui-contract.md`
- `docs/phase-1-read-only-broker.md`
- `docs/phase-2-hybrid-tui.md`
- `vm-lab/scripts/observation_broker.py`
- `vm-lab/scripts/restricted_fact_store.py`
- `runtime/reports/2026-08-06-phase4-activation-readiness.json`
- `docs/phase-4-vm-lab-prerequisite.md`
- `docs/phase-4-l1-controller-enrollment.md`
- `docs/phase-4-l2-full-vm-blueprint.md`
- `docs/direct-host-deployment-and-recovery.md`
- `docs/r2-system-recovery-set.md`
- `docs/capability-maturity.md`
- `docs/release-and-self-update.md`
- `docs/evaluation.md`
- `docs/runbook.md`
