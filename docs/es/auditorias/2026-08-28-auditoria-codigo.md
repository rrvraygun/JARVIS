# 2026-08-28 auditoría de la base de código

**Alcance:** toda la implementación propia, esquemas, accesorios, pruebas, lanzadores,
artefactos de implementación y documentación actual. Los esquemas de proveedores fijados eran
revisado sólo en las superficies de integración. Los archivos en tiempo de ejecución se evaluaron solo para
diseño, tamaño, permisos y comportamiento de integridad; no se mostró ningún contenido privado sin procesar
leído o copiado.

## Línea base de evidencia

- Archivo de reversión de origen: `/tmp/jarvis-stabilization-baseline.x0G3KA/source-before-stabilization.tar.gz`
- Archivo SHA-256: `e1cf151f58eb89ae2e9e96b7d525c58da1da2ca8d52772d86ca1044310147892`
- Manifiesto de lanzamiento previo al cambio: 715 entradas verificadas.
- El validador de instalaciones existente alcanzó 214 pruebas TUI pero falló porque el
  sandbox negó un enlace de socket Unix; Se omitieron 26 pruebas textuales sin cabeza
  porque utilizó el sistema Python en lugar del entorno virtual del proyecto.
- La prueba enfocada de socket Unix pasó fuera del sandbox.

## Fortalezas observadas

- La evaluación/admisión de tareas escritas separa la intención del modelo de la autoridad.
- Los planes del sistema de archivos local utilizan límites, descriptores y desinfectados por terminal
  ejecución del usuario actual.
- Las operaciones de paquete y energía cruzan los estrechos límites de ayuda de Polkit con
  aprobaciones de un solo uso y registros de recuperación.
- El diario TUI utiliza una cadena hash bloqueada, validación de cabeza incremental y
  resúmenes de flujo en lugar de persistencia delta sin procesar.
- Los accesorios cubren el sistema de archivos local, análisis de paquetes, aprobaciones y diario.
  integridad, seguridad del terminal, recuperación y comportamiento del contrato de VM.

## Hallazgos y estado de la remediación| Gravedad | Encontrar | Evidencia | Estado |
| --- | --- | --- | --- |
| Alto | Una corrutina cancelada podría abandonar un hilo de mutación que ya se está ejecutando. | `async_boundary.py` trabajo independiente por defecto. | Se corrigió para llamadas de paquetes, energía, iluminación y mutación local: la cancelación dura como máximo 30 segundos y luego informa un estado pendiente de resultado indeterminado. |
| Alto | Un asistente obsoleto ofrecía amplias operaciones de `sudo dnf`, repositorio y actualización. | Antiguo `vm-lab/scripts/jarvis_sudo_helper.py`. | Remoto; La validación final demuestra que no quedan referencias. |
| Alto | Todo el entorno del proceso cruzó al Codex App Server. | El antiguo `app_server_environment()` copió el `os.environ`. | Corregido con lista de permitidos explícita; los valores permanecen sin registrar. |
| Alto | Algunos comandos de red podrían aceptarse automáticamente. | Heurística de lectura de red de sesión anterior. | Remoto; Cada solicitud de comando de App Server permanece pendiente de aprobación exacta. |
| Alto | El respaldo del portapapeles persistió en el texto de la conversación renderizado en `/tmp`. | Antiguo `_do_clipboard_copy()`. | Fijado; El portapapeles no disponible informa que no hay respaldo persistente. |
| Alto | El almacenamiento de conversaciones reescribió los archivos de forma sincrónica/in situ durante el procesamiento. | Antiguo administrador de guardado automático más puente de renderizado. | Las escrituras privadas atómicas y la persistencia de aplicaciones asincrónicas ahora ponen en cola instantáneas inmutables; Pasan las pruebas de persistencia enfocadas. |
| Alto | Los datos del protocolo del servidor de aplicaciones se aplicaron hash antes de los límites globales. | `event_reducer.py`, lector estándar. | Se corrigió con límites de línea, profundidad, recuento de valores, cola y desinfección de metadatos. |
| Alto | El asistente de poder raíz siguió las escrituras del nombre de ruta. | El antiguo `_write_targets()` usaba `Path.write_text`. | Se corrigió con verificaciones de identidad de descriptores sin seguimiento. |
| Medio | Libro mayor genérico del plano de control agregado después de confiar solo en la cola. | `jarvisctl.append_event()`. | Corregido: la verificación de la cadena completa se produce bajo el bloqueo de anexo. |
| Medio | El servidor MCP devolvió cadenas de excepción sin formato. | `mcp_server.py`. | Fijado a estable `request_failed`; El refuerzo de raíz de tienda/carga útil permanece abierto. |
| Medio | `app.py`, `session.py` y `broker.py` siguen siendo módulos de responsabilidad múltiple. | Más de 3000/1300+/1200+ líneas. | En curso; La extracción del flujo de trabajo está controlada por pruebas de caracterización. |
| Medio | La documentación actual tiene una deriva histórica/actual. | Los documentos actuales y los registros de fase entran en conflicto. | En curso; Se agregaron índice de autoridad, mapa, inventario generado, trabajo pendiente y registro de sesión. |
| Medio | La validación dependía de rutas absolutas externas y omitía la cobertura de la interfaz de usuario. | `scripts/validate-bundle.sh`. | En curso; Se agregaron herramientas bloqueadas y configuración de calidad local del proyecto. |
| Alto | El esquema del controlador de VM permitía solo un estado de solo contrato reemplazado, mientras que la política documentaba la activación de solo lectura H1 Tier-0. | `vm-lab/schemas/controller-policy.schema.json`, `vm-lab/controller/policy.json`. | Corregido con dos variantes de esquema exactas; ambos conservan las denegaciones de mutación, privilegios, redes y virtualización. |
| Alto | Los esquemas de observación de nivel 0 y el registro de acciones omitieron el estado de solo lectura H1 documentado. | Esquemas de observación y `action-definition.schema.json`. | Se corrigió con variantes exactas de solo dispositivo/H1 y el estado de acción de solo lectura de un solo uso registrado. |
| Alto | Las vistas previas de instalación de TUI DNF5 podían resolver una tabla de paquetes mientras que el asistente raíz no analizaba raíces de instalación y las rechazaba antes de DNF. | TUI `package_inventory.py` tenía una tabla alternativa ausente en `jarvis_package_control.py`. | Se corrigió con el análisis de la tabla de instalación limitada coincidente; pases de accesorios de ayuda. |

Las revisiones independientes de Luna también encontraron y cerraron una brecha en el ciclo de vida del paquete del catálogo.
(capturar/vincular ahora precede a la vista previa de DNF), deriva de cancelación de deshacer paquete y
La carrera de objetos vivos de la cola de persistencia. La revisión final aún registra
trabajo de solo medio en la cartera de pedidos.

## Política de trabajo pendiente restante

Los resultados medios y bajos permanecen en `../stabilization-backlog.md`. ellos no son
silenciado: cada uno debe tener un propietario, evidencia y una prueba de aceptación concreta o
motivo documentado para aplazarlo.
