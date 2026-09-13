# Asistente JARVIS para estaciones Fedora

Esta es la entrada en español del repositorio. La documentación principal está
en inglés en [`README.md`](README.md). Su espejo español se encuentra en
[`docs/es/`](docs/es/README.md) y conserva la misma estructura de archivos.

JARVIS es una interfaz TUI local para Fedora con inspección acotada del equipo,
flujos de paquetes, energía e iluminación, conversación mediante Codex App Server
y artefactos auditados del plano de control.

Antes de usarlo, lee [`AGENTS.md`](AGENTS.md) y
[`docs/es/runbook.md`](docs/es/runbook.md). Para validar el bundle:

```bash
./scripts/validate-bundle.sh
```

La validación usa fixtures y archivos temporales aislados. No realiza escaneos
del equipo, instalaciones, limpieza, actualizaciones, reparaciones, acciones
privilegiadas ni auto-modificación del agente.

La documentación española mantiene las rutas, comandos, identificadores de
protocolo y fragmentos de código exactamente como aparecen en inglés. Cuando
una traducción requiere una decisión técnica, la versión inglesa y los contratos
actuales siguen siendo la autoridad.
