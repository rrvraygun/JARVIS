# Guía de parches JARVIS

Actualizado el 11 de septiembre de 2026. Esta entrega es candidata a código y prueba; lo hace
no significa que la instalación activa haya sido reemplazada.

## Capacidades incluidas

| Componente | Capacidad y alcance |
| --- | --- |
| Terminales normales | **Ejecutar en terminal normal** en Desarrollo, con revisión explícita del modo, argumentos, directorio y autoridad del usuario. Hereda E/S y límites de usuario; no agrega shell ni comandos ocultos. |
| Aprobaciones | Decisiones efímeras, resumen de modo específico, reserva duradera y rechazo de repetición. El entorno está vinculado sin almacenar sus valores. Los resultados inciertos requieren reconciliación. |
| Carga | Verifique, cree, pruebe, fmt y clippy en una copia aislada, sin red ni el HOME real, con límites efectivos y verificaciones de grupos de procesos. |
| Dependencias | Copia revisada, aplicación separada de manifiestos existentes, originales retenidos y verificaciones de contenido/permiso/atributos. Se requiere una propuesta inversa separada cuando las ediciones posteriores sean incompatibles. |
| Descargas | Una descarga de crates.io por URL y suma de verificación del archivo de bloqueo, aprobada por separado. Cargo consume archivos verificados sin red. |
| Raíz | Entradas de arranque y actualización separadas, ejecutor raíz compartido y políticas Polkit sin autorización persistente. Requiere una solicitud exacta, revisión independiente y evidencia de recuperación actual. |
| Bota | Selección del siguiente arranque; Generación y publicación de nuevos initramfs a través de una operación aprobada por separado que conserva la imagen anterior. No reinicia ni prueba la capacidad de arranque. |
| Actualizaciones | Reproducción estricta de una transacción DNF5 preparada con archivos firmados y referencias dentro de su árbol. Comprueba el conjunto instalado esperado. |
| MCP y especialistas | Alcance por proceso/generación, especialista seleccionado respetado, nuevas observaciones y rechazo de herramientas o políticas fuera de alcance. |
| Interfaz | vistas de Salud, Desarrollo, Red, Seguridad y Recuperación; la revisión y los datos detallados quedan fuera de la conversación limpia. |
| Puntos de control | Preservación del contexto; recuperación completa sólo cuando existe una operación recuperable vinculada. El chat no se restaura antes de que finalice la recuperación del paquete. |
| Transcripciones | Resultados desinfectados, tamaño/recuento limitado y retención de siete días para registros nuevos. Sin entorno completo, credenciales o razonamiento privado. |
| Recuperación | Copia/restauración de proyectos delimitados y planificación para los cinco límites del sistema. La orquestación completa de Restic sigue siendo una integración separada. |

## Pruebe la interfaz y el terminal

Desde el directorio de candidatos, como usuario normal:```bash
.venv/bin/python scripts/smoke-normal-terminal.py --approve-printf-smoke
```La prueba abre Textual en una terminal real, muestra la revisión en modo normal, confirma
sólo un `printf` fijo y comprueba su recepción. Utiliza una sesión sintética con
sin modelo, cuenta, red o asistente raíz. Escribe capturas SVG y JSON en un
nuevo directorio `/tmp` e imprime su ruta. El marcador final es
`JARVIS_VISIBLE_SMOKE_PASSED`.

Para inspeccionar solo la interfaz sin una conexión de agente:```bash
PYTHONPATH="$PWD/tui/src" .venv/bin/python -m jarvis_tui --bundle-root "$PWD"
```El iniciador normal `scripts/launch-tui.sh` se conecta al servidor de aplicaciones y necesita
el perfil revisado y la autenticación normal. No copie las credenciales en el
parchearlos o pegarlos en la conversación.

El terminal normal utiliza la red y los permisos habituales del usuario. código de salida
cero confirma solo el proceso principal; no prueba el objetivo completo o el niño
finalización del proceso. La ruta normal no se habilita ejecutando JARVIS como root.

## Validación reproducible```bash
bash scripts/quality-gate.sh --full
```Espere el resultado final: las pruebas gráficas tardan unos dos minutos en este host.
Los mensajes de tareas lentas de Asyncio por sí solos no son un bloqueo. El resultado exacto para esto.
la entrega se registra en `VALIDACION.md` al lado del candidato.

## Despliegue y operaciones privilegiadas

Los archivos preparados son `jarvis_boot_control.py`, `jarvis_update_control.py`,
`jarvis_privileged_control.py` y los dos archivos `org.jarvis.*-control.policy`.
El cliente requiere archivos y políticas instalados que coincidan con el candidato y sean
propiedad de raíz. La prueba de humo no los instala.

El estado protegido se encuentra bajo `/var/lib/jarvis/privileged-control`: aprobaciones,
reservas, resultados, transacciones y copias de seguridad. Cada aprobación independiente es
vinculado a un UID, ID y resumen de solicitud, caduca e incluye evidencia R2 vinculada
a la confirmación previa al estado y al arranque de recuperación. El agente no puede crear ni inferir
esta autoridad a partir de argumentos.

Para actualizaciones, el administrador prepara un árbol DNF5 `--store` con local firmado
RPM y rutas relativas normalizadas. Se aceptan transiciones de RPM; grupos,
entornos y otros formatos se rechazan. Las opciones `ignore` y `skip` están
No estamos acostumbrados a silenciar las diferencias. La publicación de Initramfs requiere una revisión por separado
del hash de la imagen generada. Los errores y los resultados inciertos nunca provocan reintentos
o reversión automática.

## Límites de lo probado

La implementación privilegiada requiere mantenimiento exclusivo y transacción inmutable
publicación; el bloqueo auxiliar no serializa a otros administradores. Los hashes son
revisado antes de los efectos, sin pretender eliminar todas las razas con otra raíz
procesos.

- La prueba visible ejercita la TUI y un mando real; el modelo es un accesorio.
- Las descargas externas y los comandos privilegiados utilizan dispositivos; sin paquete ni arranque
  El cambio se aplicó a la estación de trabajo en este cierre.
- Autenticación real, aprovisionamiento raíz por operación y activación de candidatos
  todavía requieren controles de implementación.
- Restic superó las pruebas aportadas por el usuario. `rsync` comparaciones sin
  `-c` no certifica la igualdad de la suma de verificación. Arranque de recuperación real, partición/UEFI
  reconstrucción y una restauración actual del sistema completo no fueron demostradas.

Detalles de la corrección: `sessions/2026-09-11-validation-closeout.md`.
