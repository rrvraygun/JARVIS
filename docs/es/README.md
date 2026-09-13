# Índice de documentación de JARVIS

Esta carpeta contiene la versión española paralela de la documentación del
repositorio. Mantiene la misma estructura que la versión inglesa principal para
que cada documento pueda localizarse en ambos idiomas.

## Orden de autoridad

1. `AGENTS.md` define las invariantes del repositorio y este mapa documental.
2. `current-product-state.md` define el comportamiento implementado actualmente.
3. Los contratos vigentes definen los límites de cada subsistema.
4. `generated/` es un inventario generado por máquinas y nunca una autoridad de
   ejecución.
5. `audits/` y `sessions/` son registros de evidencias.
6. `history/` indexa diseños sustituidos y no modifica los contratos actuales.

## Contratos actuales

- Estado del producto y mapa de código: `current-product-state.md`.
- Seguridad y evidencias compartidas: `shared-contract.md`.
- Límites de plataforma y amenazas: `platform-architecture.md`, `threat-model.md`.
- TUI y operaciones del equipo: `tui-contract.md`, `tui-mutation-executor.md`,
  `host-inspection-executor.md`.
- Auditoría, datos, recuperación y despliegue: `audit-and-state.md`,
  `data-lifecycle.md`, `direct-host-deployment-and-recovery.md`,
  `r2-system-recovery-set.md`.

Los documentos de esta carpeta deben mantenerse sincronizados con la versión
inglesa cuando cambie el comportamiento del producto. Los nombres técnicos,
las rutas, los comandos, los identificadores de protocolo y los fragmentos de
código se conservan literalmente para que sigan siendo ejecutables.
