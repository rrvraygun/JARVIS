# Asistente JARVIS para estaciones de trabajo Fedora

Esta es la entrada en español del repositorio. La versión principal en inglés
está en [README.md](../../README.md). El índice español está en
[LEEME.md](LEEME.md).

JARVIS es una interfaz local para Fedora con inspección acotada del equipo,
flujos de paquetes, energía e iluminación, conversación mediante Codex App
Server y registros auditados del plano de control.

Antes de usar el proyecto, consulta [AGENTS.md](../../AGENTS.md), el
[estado actual del producto](estado-actual-producto.md) y el
[manual operativo](manual-operativo.md).

Para validar el bundle:

    ./scripts/validate-bundle.sh

La validación utiliza fixtures y archivos temporales aislados. No realiza
escaneos del equipo, instalaciones, limpieza, actualizaciones, reparaciones,
acciones privilegiadas ni autoactualización del agente.

Las rutas, comandos, identificadores de protocolo y fragmentos de código se
conservan en su forma técnica original. Si una traducción entra en conflicto con
un contrato técnico, el contrato vigente en inglés mantiene la autoridad.
