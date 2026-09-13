# Entrega recuperada - 11 de septiembre de 2026

Estado: candidato persistente probado; no activado o instalado como sistema
actualizar. La versión activa anterior se conserva y no es necesario revertirla.

## Evidencia de esta copia

- Los cambios de código se recuperaron de las llamadas de edición registradas para esta tarea;
  Los comandos históricos no se ejecutaron y las credenciales no se copiaron.
- Suite TUI: 350 pruebas en 69.213 segundos, 349 aprobadas y un error ambiental
  mientras se crea un socket local dentro del sandbox. Ambas pruebas del módulo de socket
  Pasó fuera de la caja de arena. El error no se atribuye a Textual.
- Las dos pruebas `recovery_plan` faltantes fueron restablecidas y aprobadas con un especialista
  y pruebas de raíz (17 pruebas en ese momento).
- La revisión independiente agregó controles de cambio de estado antes de los efectos raíz y tres
  pruebas de regresión; Se pasaron 13 pruebas de raíz.
- Prueba visible: `printf` se ejecutó una vez, salió de 0 y regresó a la interfaz.
  Las capturas y el recibo están en `runtime/validation/visible-y5i3l9cl/`.
- Ruff pasó; mypy pasó para los tres nuevos módulos de ejecución.
- La validación del paquete fue aprobada con 817 entradas antes de que se agregara este informe. el
  El manifiesto final se regenera después del informe.

Los registros se almacenan en el directorio principal con el
Prefijo `jarvis-2026-09-11-recovered-`. Se realizó una repetición combinada fuera del sandbox.
rechazado antes de la ejecución por la cuota de revisión automática; no se reporta como
pasado.

## Correcciones adicionales

La generación de inventario y manifiesto ahora excluye las rutas relativas al candidato:
un directorio principal llamado `runtime` ya no crea una entrega vacía. el
El verificador rechaza manifiestos vacíos. La prueba visible guarda evidencia persistente.

## Pendiente de instalación completa

Instalación de política/ayudante raíz, aprovisionamiento de aprobación independiente, el
La prueba autenticada y la activación de la versión no se realizaron. el completo
El plan no está terminado. El ensayo de restauración tampoco prueba el arranque de recuperación o
una copia completa de la estación de trabajo actual.

El despliegue raíz debe garantizar un mantenimiento exclusivo y una publicación inmutable.
de transacciones preparadas: el bloqueo auxiliar no serializa otras operaciones administrativas
herramientas. Volver a verificar los hashes reduce el riesgo de cambios simultáneos pero no elimina las carreras
con otro administrador raíz. Este candidato no es promovido como productor.
software de ejecución privilegiado listo.

## Pruebe el terminal

Desde este directorio:```bash
.venv/bin/python scripts/smoke-normal-terminal.py --approve-printf-smoke
```Esta prueba utiliza un modelo simulado y ejecuta solo el `printf` fijo mostrado.
La guía de capacidades es `docs/PATCH-GUIDE-2026-09.md`.
