# Arquitectura de la plataforma Jarvis

## Aviones

1. **Plano de intención:** el mensaje, `AGENTS.md`, los roles de los agentes y las habilidades definen los resultados.
   y procedimientos pero no otorgan autoridad.
2. **Plano de control:** registro de capacidades, versiones de procedimientos, motor de políticas,
   Los resúmenes de acción, las aprobaciones y la actualidad del estado deciden lo que puede proceder.
3. **Plano de herramientas:** herramientas MCP estrechas, shell, administradores de paquetes e instalaciones del sistema operativo.
   La ejecución sin formato no está expuesta por el servidor Jarvis MCP.
4. **Plano de evidencia:** observaciones redactadas, instantáneas, líneas de base, validación,
   procedencia e informes.
5. **Plano de conocimiento:** datos de Fedora con reconocimiento de versión, documentación local, comando
   intentos, informes de errores, lecciones revisadas y resúmenes de decisiones.
6. **Plano de auditoría:** eventos bloqueados, fsynced, encadenados hash más retención y remotos
   Puntos de integración exportadora.
7. **Plano de recuperación:** copias de seguridad, instantáneas, procedimientos de reversión, acceso de rescate,
   y restauración probada de forma independiente.
8. **Plano de implementación de host directo:** una estación de trabajo Fedora inscrita es la
   objetivo principal de producto personal. Progresa desde el elemento fijo hasta la sombra y
   funcionamiento supervisado sólo después de las puertas de recuperación específicas de la máquina.
9. **Plano de escenario-laboratorio:** matrices de accesorios y un Fedora desechable aislado
   Los invitados ensayan revisiones exactas del adaptador como entorno secundario. no tiene
   El conocimiento de producción/auditoría se acumula y no puede dar fe del hardware físico.
   comportamiento.

## Mapa de capacidades de OpenAI

| Característica del códice | Uso de Jarvis |
|---|---|
| `AGENTS.md` | Invariantes cortas duraderas y mapa de documentación |
| Agentes aduanales | Investigación, exploración, diagnóstico, implementación, revisión |
| Subagentes | Líneas independientes de evidencia/revisión; nunca autorización independiente |
| Habilidades | Divulgación progresiva del flujo de trabajo por capacidad |
| Complemento | Paquete instalable versionado para skills y MCP |
| PCM | Herramientas de gobernanza escritas con política de aprobación a nivel de herramienta |
| Ganchos | Barreras secretas y de acción catastrófica, contexto del ciclo de vida |
| Caja de arena/aprobaciones | Privilegio mínimo en tiempo de ejecución y autorización humana |
| `requirements.toml` | Restricciones gestionadas por la organización cuando se implementa de forma centralizada |
| `codex exec --json` | Automatización y evaluación de solo lectura legible por máquina |
| Esquemas de salida | Resultados de automatización estables y artefactos de validación |
| Tareas programadas | Observación, informes de deriva, recordatorios; sin mutación predeterminada |
| Árboles de trabajo | Cambios aislados de agente/complemento y puesta en escena de actualización automática |
| Acción de GitHub | Validación de CI y revisión independiente del paquete |
| Servidor de aplicaciones Codex | Verificación previa de TUI con tipo alternativo, ejecución de agente, transmisión, interrupción y transporte de aprobación exacta; nunca se requiere para lecturas locales deterministas y nunca la autoridad política de Jarvis |
| SDK del códice | Envoltorio de App Server escrito opcional cuando sus eventos expuestos satisfacen el contrato TUI |

La habilidad `system-knowledge` posee un flujo de trabajo de recuperación y aprendizaje. determinista
SQLite y scripts de indexación poseen persistencia e invariantes. El servidor MCP
expone consultas escritas y operaciones de registro, nunca la ejecución sin formato del sistema.

El registro especializado y el coordinador son el agente modular de cara al usuario.
límite. El especialista seleccionado por el usuario aporta instrucciones limitadas,
referencias de conocimiento, metadatos de contexto y referencias de herramientas registradas; lo hace
no otorgar autoridad. Las ediciones de definiciones se organizan, validan, revisan y analizan.
aprobado de un solo uso y activado atómicamente con un archivo de versión anterior. el
La superficie de paquetes y el especialista en instalación comparten el backend del corredor/paquete.

La TUI utiliza la arquitectura indicada en `tui-implementation-plan.md`. naturales
Las acciones de lenguaje y catálogo comparten una misma línea de tareas. Lista local exacta/lectura/
las solicitudes de búsqueda pueden tomar una ruta ejecutora determinista vinculada al resumen antes
verificación previa del modelo. Ni la ruta de lectura del usuario actual, ni la interfaz ni la aplicación
El servidor se convierte en autoridad de administración de host o de mutación.Las mutaciones exactas del sistema de archivos y de los paquetes también se pueden planificar de forma determinista,
pero sus admisiones siguen pendientes de aprobación. El usuario actual escribe en una cruz
Ejecutor vinculado al descriptor de Python después de una decisión modal; paquete privilegiado
instalar/eliminar cruza sólo el asistente Polkit registrado como root después de un
Vista previa de DNF enlazada al resumen. Los turnos de agentes pueden proponer un trabajo más amplio para los usuarios actuales,
a través de ejecutores registrados de revisión exacta. Los turnos de agentes son de solo lectura y las aprobaciones genéricas de comandos/archivos no pueden autorizar escrituras.

## Límites de confianza

La salida del modelo no es una intención confiable. Páginas web, registros, metadatos de paquetes, repositorio
Los archivos y los resultados de MCP son datos que no son confiables. Los ganchos son barandillas incompletas.
La autoridad proviene de la admisión mecanografiada, la política determinista, las aprobaciones exactas,
Puerta de comando confiable, ganchos, permisos del sistema operativo, procedimientos registrados y
validación. La verificación previa escrita otorga solo el alcance registrado; Los turnos de agente siguen siendo de solo lectura. Un host comprometido no puede ser
su único testigo; exportar evidencia de auditoría crítica a un sistema independiente.
Un huésped comprometido o contaminado no puede promover sus propios resultados. Máquina virtual futura
las ejecuciones requieren identidad y restablecen certificaciones fuera del invitado.

La recuperación se basa en la cobertura, no es booleana. Una instantánea del sistema de archivos local no
proteger un sistema de archivos de arranque/EFI independiente, un estado de firmware, subvolúmenes excluidos o
falla en el mismo dispositivo. Las clases de acción de anfitrión directo requieren progresivamente más fuertes.
Evidencia R0–R3 como se define en `direct-host-deployment-and-recovery.md`.

## Política de automatización

La automatización desatendida puede inventariar, comparar, alertar y preparar planes de cambio.
La mutación requiere una política de máquina revisada por separado, una identidad de servicio limitada,
Procedimiento y objetivos exactos preaprobados, recuperación, ventana de mantenimiento limitada,
y notificación posterior a la ejecución. La ambigüedad no se cierra.
