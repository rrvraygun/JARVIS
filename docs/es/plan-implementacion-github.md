# Plan de implementación de GitHub Agent

## Fase actual

La fase 1 está implementada y validada con fixtures, la fase 2 de ejecución Git
local también está implementada y validada, y el adaptador GitHub CLI acotado ya
está implementado. GitHub Agent se puede
seleccionar en Agents y Conversation. Dispone de un inspector Git local acotado,
un preflight de publicación y una herramienta que prepara planes de operación.
Init, ramas, commit, pull rápido y push locales pasan por la revisión TUI de un
solo uso. Las operaciones remotas producen planes CLI validados, pero aquí siguen
bloqueadas porque GitHub CLI no está instalado y no hay un conector MCP oficial
configurado.

## Identidad y autenticación

El agente utiliza el perfil GitHub configurado y activo. El transporte Git usa
la configuración SSH del usuario. La cuenta nunca se deduce de una solicitud y
las credenciales nunca se copian, muestran ni guardan en el proyecto.

## Catálogo inicial

| Herramienta | Alcance | Autoridad |
| --- | --- | --- |
| github_inspect | Rama, estado, diferencias, historial, rutas ignoradas, conflictos, remotos y versión de Git | Solo lectura |
| github_preflight | Rutas modificadas e ignoradas, nombres potencialmente sensibles, archivos grandes y conflictos | Solo lectura |
| github_operation_plan | Init, clonación, ramas, commit, pull/push, repositorios, issues, PR, release, Actions, borrado y configuración | Solo plan; exige aprobación exacta nueva |

GitHub CLI y un conector MCP oficial se detectan y se informa de su
disponibilidad. Las herramientas de la fase 1 no los invocan.

## Modelo de autoridad

La inspección de solo lectura puede ejecutarse automáticamente sobre el
repositorio elegido por el usuario. Commits, push, creación de repositorios,
pull requests, merges, releases, Actions, colaboradores, protecciones, force
push, borrado de ramas y borrado de repositorios exigen una aprobación exacta
nueva. Un conflicto detiene el flujo; el agente no lo resuelve automáticamente.

## Fases de entrega

1. Inspección: completada.
2. Acciones Git locales: init, clonación por SSH, ramas, worktrees, commit, pull
   rápido y push detrás de la revisión TUI de un solo uso.
3. Acciones de repositorio GitHub: habilitar el adaptador GitHub CLI/API acotado o
   MCP oficial para repositorios, forks, plantillas, issues, PR, etiquetas y
   milestones después de instalarlo y comprobarlo de forma independiente.
4. CI y releases: checks, logs y reejecuciones de Actions, artefactos, tags y
   releases con autorización explícita de red y publicación.
5. Endurecimiento: archivos grandes y LFS, protecciones de rama, auditoría,
   recuperación y pruebas de aceptación. El escaneo acotado de patrones de
   secretos por ruta y tipo ya está implementado.

## Criterios de aceptación

- El especialista se puede seleccionar en las dos ubicaciones solicitadas.
- Toda operación identifica perfil, repositorio, rama, objetivo y autoridad.
- Ninguna escritura se ejecuta sin aprobación exacta nueva.
- No aparecen credenciales ni claves privadas en registros, prompts o archivos.
- Rutas sensibles, conflictos y archivos demasiado grandes bloquean la publicación
  hasta su revisión.
- El trabajo dependiente de red queda bloqueado si el perfil aprobado no dispone
  de capacidad de red.
- Los resultados fallidos o inciertos se detienen sin reintento automático y
  conservan un registro de recuperación acotado.
