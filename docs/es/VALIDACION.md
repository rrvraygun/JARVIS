# Entrega recuperada — 11 de septiembre de 2026

Estado: candidato persistente probado; no activado ni instalado como actualización
del sistema. La versión activa anterior se conserva y no necesita rollback.

## Evidencia de esta copia

- Recuperados los cambios de código desde las llamadas de edición del historial
  de esta tarea; no se ejecutaron comandos históricos ni se copiaron credenciales.
- Suite TUI: 350 pruebas en 69,213 segundos, 349 correctas y un error ambiental
  al crear un socket local dentro de la sandbox. Las dos pruebas del módulo de
  socket pasaron fuera de ella. No se atribuye ese error a Textual.
- Después se recuperaron los dos tests de recovery_plan que faltaban y pasaron
  junto a los de especialistas y root (17 pruebas en ese momento).
- Tras revisión independiente se añadieron controles de cambio de estado antes
  de efectos root y tres regresiones: 13 pruebas root correctas.
- Prueba visible real: printf ejecutado una vez, salida 0 y regreso a la interfaz.
  Capturas y recibo en runtime/validation/visible-y5i3l9cl/.
- Ruff pasó; mypy pasó en los tres módulos nuevos de ejecución.
- Validación del bundle pasó con 817 entradas antes de añadir este informe.
  El manifiesto final se regenera después del informe.

Los logs están en la carpeta superior con prefijo
jarvis-2026-09-11-recovered-. La repetición conjunta fuera de la sandbox fue
rechazada antes de ejecutarse por límite de uso del revisor automático.
No se afirma que esa repetición haya pasado.

## Correcciones adicionales

El inventario y manifiesto ahora excluyen rutas relativas al candidato: una
carpeta antecesora llamada runtime ya no produce una entrega vacía. El verificador
rechaza manifiestos vacíos. La prueba visible guarda evidencia persistente.

## Pendiente para instalación completa

La instalación de helpers/políticas root, provisión independiente de aprobaciones,
prueba autenticada y activación de release no se han realizado. El plan completo
no está finalizado. El ensayo de restauración tampoco demuestra arranque de
recuperación ni una copia actual completa del equipo.

El despliegue root debe garantizar mantenimiento exclusivo y publicación inmutable
de las transacciones preparadas: el lock del helper no controla otras herramientas
de administración. Revalidar hashes reduce cambios concurrentes pero no elimina
la carrera con otro administrador root. No se promociona este candidato como
ejecutor privilegiado listo para producción.

## Probar la terminal

Desde esta carpeta:

```bash
.venv/bin/python scripts/smoke-normal-terminal.py --approve-printf-smoke
```

Esta prueba usa un modelo simulado y únicamente ejecuta el printf fijo mostrado.
La guía de capacidades está en docs/PARCHE-GUIDE-2026-09.md.
