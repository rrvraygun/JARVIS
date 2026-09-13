# Guía del parche JARVIS

Actualizada el 11 de septiembre de 2026. Esta entrega es un candidato de código
y pruebas; no implica que se haya reemplazado la instalación activa.

## Qué incluye

| Componente | Capacidad y alcance |
| --- | --- |
| Terminal normal | Botón **Run in normal terminal** en Development. Nueva revisión explícita del modo, argumentos, directorio y autoridad del usuario. Entrada/salida heredadas, sin límites de tiempo o recursos impuestos por JARVIS. No añade una shell ni comandos ocultos. |
| Aprobaciones | Decisiones efímeras, digest propio del modo, reserva durable y rechazo de repetición. El entorno se vincula sin guardar sus valores. Los resultados inciertos requieren reconciliación. |
| Cargo | Check, build, test, fmt y clippy en copia aislada, sin red ni HOME real, con límites efectivos y comprobación del grupo de procesos. |
| Dependencias | Copia revisada, aplicación separada a manifiestos existentes, originales retenidos y comprobación de contenidos, permisos y atributos. Propuesta inversa separada cuando no hay ediciones posteriores incompatibles. |
| Descargas | Una descarga crates.io por URL y checksum del lockfile, aprobada por separado. Cargo consume después los archivos verificados sin red. |
| Root | Entradas separadas para arranque y actualización, ejecutor root compartido y políticas Polkit sin autorización persistente. Exigen solicitud exacta y revisión independiente root con recuperación vigente. |
| Arranque | Selección para el próximo arranque; generación de initramfs en archivo nuevo y publicación mediante otra operación aprobada que conserva el anterior. No reinicia el equipo ni prueba arrancabilidad. |
| Actualizaciones | Reproducción estricta de una transacción DNF5 preparada, con archivos firmados y referencias dentro de su árbol. Comprobación del conjunto instalado esperado. |
| MCP y especialistas | Ámbito por proceso/generación, especialista seleccionado respetado, observaciones frescas y rechazo de herramientas o políticas fuera de su ámbito. |
| Interfaz | Vistas Health, Development, Network, Security y Recovery; revisión y datos detallados fuera de la conversación limpia. |
| Checkpoints | Conservación del contexto; recuperación completa solo cuando existe una operación recuperable vinculada. No restaura el chat antes de que termine la recuperación de paquetes. |
| Transcritos | Resultados saneados, tamaño y cantidad acotados, siete días para registros nuevos. Sin entorno completo, credenciales ni razonamiento privado. |
| Recuperación | Copias/restauraciones acotadas de proyectos y planificación de las cinco fronteras del sistema. La orquestación automática completa de Restic sigue siendo una integración aparte. |

## Cómo probar la interfaz y la terminal

Desde el directorio del candidato, como usuario normal:

```bash
.venv/bin/python scripts/smoke-normal-terminal.py --approve-printf-smoke
```

Este ensayo abre Textual en una terminal real, muestra la revisión del modo
normal, confirma exclusivamente un printf fijo y comprueba su recibo. Usa una
sesión sintética sin modelo, cuenta, red ni helper root. Genera capturas SVG y
un resultado JSON en un directorio nuevo de /tmp cuya ruta imprime al terminar.
El indicador final debe ser `JARVIS_VISIBLE_SMOKE_PASSED`.

Para comprobar únicamente la interfaz de forma manual, sin conectar al agente:

```bash
PYTHONPATH="$PWD/tui/src" .venv/bin/python -m jarvis_tui --bundle-root "$PWD"
```

El lanzador habitual `scripts/launch-tui.sh` sí intenta conectar al App Server;
requiere un perfil revisado y la autenticación normal. No copies credenciales al
parche ni las pegues en la conversación.

La terminal normal tiene las capacidades normales de tu usuario y conectividad
del equipo. Un código de salida cero solo confirma el proceso principal; no
demuestra el objetivo completo ni que sus procesos hijos hayan terminado. La
ruta normal no se habilita ejecutando JARVIS como root.

## Validación reproducible

```bash
bash scripts/quality-gate.sh --full
```

Espera el resultado final: las pruebas gráficas tardan del orden de dos minutos
en este equipo. Los mensajes de asyncio sobre tareas lentas no son por sí solos
un bloqueo. No interrumpas una suite que sigue avanzando. Consulta el resultado
exacto de esta entrega en `VALIDACION.md`, junto al candidato.

## Despliegue y operaciones privilegiadas

Los archivos preparados son `jarvis_boot_control.py`, `jarvis_update_control.py`,
`jarvis_privileged_control.py` y las dos políticas `org.jarvis.*-control.policy`.
El cliente exige que los archivos instalados y las políticas coincidan con los
del candidato y estén bajo control de root. No se instalan al ejecutar el smoke.

El estado protegido se ubica en `/var/lib/jarvis/privileged-control`: approvals,
reservations, results, transactions y backups. Cada aprobación independiente
corresponde a un UID, ID y digest de solicitud, caduca y contiene evidencia R2
ligada al preestado y confirmación del arranque de recuperación. El agente no
puede crear esa autoridad mediante argumentos o aprobarse a sí mismo.

Para updates, el administrador prepara un árbol DNF5 --store con RPM locales
firmados y rutas relativas normalizadas. Se admiten transiciones de RPM; grupos,
entornos y otros formatos se rechazan. No se usan opciones ignore o skip para
silenciar diferencias. La publicación de initramfs exige una revisión separada
del hash de la imagen generada. Los errores o resultados inciertos no provocan
reintentos ni rollback automático.

## Límites de lo probado

El despliegue privilegiado requiere mantenimiento exclusivo y publicación
inmutable de transacciones: el lock del helper no serializa otros administradores.
Los hashes se vuelven a comprobar antes del efecto, sin afirmar que eliminen
todas las carreras con otros procesos root.

- La prueba visible ejercita el TUI y un comando real; el modelo es una fixture.
- Las descargas externas y los comandos privilegiados se prueban con fixtures;
  no se han aplicado paquetes ni cambios de arranque al equipo durante este cierre.
- La autenticación real, la provisión root por operación y la activación del
  candidato necesitan sus comprobaciones de despliegue.
- Restic pasó la comprobación aportada por el usuario. Las comparaciones rsync
  sin -c no certifican contenido por checksum. No se ha demostrado arranque real,
  reconstrucción de particiones/UEFI ni una recuperación actual de todo el sistema.

Detalle de correcciones: `sessions/2026-09-11-validation-closeout.md`.
