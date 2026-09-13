# Mapa base de código JARVIS

**Estado:** referencia de arquitectura actual
**Última revisión:** 2026-08-28
**Compañero generado:** `generated/codebase-inventory.md````text
User / Textual TUI
  └─ tui/src/jarvis_tui/app.py
├─ Presentation.py Conversación visible, línea de tiempo y proyecciones de estado.
       ├─ agent_registry.py      reviewed definitions, selection, drafts, activation, rollback
├─ agent_coordinator.py contexto y enrutamiento explícitos especializados seleccionados por el usuario
       ├─ broker.py             capture -> assess -> admit -> reserve -> complete
       ├─ models.py             immutable task, plan, assessment, admission data
       ├─ session.py            App Server threads, turns, context, event lifecycle
       ├─ app_server.py         bounded stdio JSON-RPC transport
       ├─ event_reducer.py      protocol normalization and terminal safety
       ├─ event_store.py        locked hash-chained TUI journal
       ├─ local_filesystem.py   bounded list/read/search executor
       ├─ local_mutation.py     approval-gated create/Trash executor
       ├─ package_*.py          inventory, exact planning, Polkit client
       ├─ power_*.py            inventory, telemetry, profiles, and Polkit client
       └─ conversation_manager.py private saved-conversation persistence

Registered authority boundaries
  ├─ vm-lab/scripts/jarvis_package_control.py  root-owned exact DNF helper
  ├─ vm-lab/scripts/jarvis_power_control.py    root-owned allowlisted power helper
├─ instaladores de implementación/host/ayudante y política de Polkit
  └─ plugins/jarvis-system-admin/               actions, schemas, knowledge, MCP policy

Specialist plugins
  ├─ plugins/jarvis-system-architect/           general project/system guidance
  ├─ plugins/jarvis-installation-specialist/    Fedora package ownership
  └─ plugins/jarvis-power-expert/                selectable Power specialist

Evidence and rehearsal boundaries
  ├─ schemas/ and tui/schemas/                  public/domain JSON contracts
├─ vm-lab/controlador solo de dispositivo y contratos de VM
  ├─ tests/, tui/tests/, vm-lab/tests/          deterministic regression suites
  ├─ scripts/                                   launch, manifest, validation, quality tools
└─ tiempo de ejecución/estado operativo privado; excluido de la fuente de lanzamiento
```## Responsabilidades principales

| Área | Archivos primarios | Límite de autoridad |
| --- | --- | --- |
| Conversación | `app.py`, `presentation.py`, `conversation_manager.py` | La interfaz de usuario muestra el estado; La persistencia es privada y no puede aprobar el trabajo. |
| Intención/admisión | `broker.py`, `models.py`, `preflight.py` | La salida del modelo no es de confianza hasta que el corredor ingresa. |
| Transporte de agentes | `session.py`, `app_server.py`, `event_reducer.py` | App Server recibe un entorno incluido en la lista de permitidos y una entrada de protocolo limitada. |
| Sistema de archivos local | `local_filesystem.py`, `local_mutation.py` | Lecturas/escrituras vinculadas al descriptor solo de Python; las mutaciones consumen una aprobación. |
| Paquetes/potencia | `package_*`, `power_*`, ayudantes raíz | La vista previa y la revisión de un solo uso vinculan operaciones exactas; Sólo los ayudantes de Polkit tienen privilegios. |
| Auditoría/conocimiento | `event_store.py`, almacenamiento de complementos/código MCP | Cadena hash que minimiza el contenido y revisiones de conocimiento inmutables. |
| Despliegue/ensayo | `deployment/host`, `vm-lab` | Estático o solo accesorio a menos que se instale y apruebe por separado. |

## Solicitar flujo```text
composer -> capture pending projection -> deterministic planner
  -> local read / local mutation / exact package route
  -> otherwise typed App Server preflight
  -> broker admission
  -> local executor, registered helper, or reviewed agent turn
  -> terminal projection + metadata-only audit
```La proyección determinista de resultados locales se puede sincronizar como acotada,
historial no confiable para un turno de agente posterior. Nunca otorga autoridad por sí mismo.

## Módulos de operación por etapas

`observation_safety.py` E/S del recopilador de límites. `project_snapshot.py` vincula la totalidad
árbol de origen permitido. `operation_workflow.py` posee propuestas, aprobaciones efímeras,
reservas duraderas, carga aislada y flujos de trabajo de proyectos de nuevas copias.
`outcome_verification.py` verifica las poscondiciones en un proceso separado de solo lectura;
`resource_guard.py` comprueba los límites efectivos de cgroup. `tool_scope.py` vincula la herramienta modelo
permisos al proceso del controlador. `domain_views.py` mantiene evidencia y exactitud
revisar fuera de la conversación. `transcript_store.py` posee registros sanitarios locales.
