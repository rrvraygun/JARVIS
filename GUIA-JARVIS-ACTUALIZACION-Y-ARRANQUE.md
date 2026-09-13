# JARVIS: mejoras, capacidades y guía de arranque

Actualizado: 11 de septiembre de 2026.

En la conversación, el selector de especialistas y la botonera forman ahora
una barra lateral vertical: **New**, **History**, **Copy** y **Clear** quedan
debajo del selector. Al abrirlo, su menú se superpone como capa absoluta y la
botonera conserva exactamente su posición.

El apartado **Agents** incluye ahora un selector **Global model**. La selección
es única para todos los especialistas, se guarda en `runtime/jarvis-model.json`
y se aplica a los nuevos turnos. Los turnos en curso conservan su modelo.
Opciones: GPT-6 Astra, GPT-5.6 Sol, GPT-5.6 Terra, GPT-5.6 Luna y GPT-5.5.
Debajo se encuentra **Context window**, con Auto, 8k, 16k, 32k, 64k, 128k,
256k, 512k, 800k, 1M y 1.05M. Modelo, razonamiento y contexto se guardan juntos
en `runtime/jarvis-model.json` y se aplican a todos los especialistas en los
nuevos turnos.
El control tiene tamaño visible propio y el menú se abre al seleccionarlo dentro
de la pestaña **Agents**.

La actividad en tiempo real vive dentro del panel de conversación: queda debajo
de tu pregunta mientras el agente trabaja y se recoloca debajo de su respuesta
cuando esta aparece. Muestra fase, tiempo, fragmentos, herramienta y consulta;
los detalles privados y resultados sin sanear permanecen ocultos.

El carril de acciones usa un ancho fijo dentro del mismo contenedor. **New**,
**History**, **Copy** y **Clear** ya no se desplazan por un anclaje al borde de
la pantalla; los controles de checkpoint permanecen junto a su mensaje.

El checkpoint conserva el texto **↶ Checkpoint** y su tamaño original, pero ahora
se sitúa en una fila propia bajo el mensaje, alineado a la derecha con una línea
de separación superior y un margen lateral corto.

El menú se compone después del botón y se abre debajo en una capa vertical fija;
su apertura conserva el tamaño del contenedor y el botón sigue siendo accesible.
La fila del checkpoint elimina el padding lateral duplicado: el botón queda a
una o dos columnas del borde derecho interior de la conversación.

Al abrirlo, el menú aparece debajo del botón como una capa vertical de cuatro
líneas. El ancho de la conversación permanece fijo; el menú no se superpone al
botón ni obliga a recalcular el borde lateral.

El checkpoint se presenta bajo el mensaje como **↶ Checkpoint**. Su menú abre
dentro de ese bloque vertical, por lo que no puede recalcular ni desplazar el
ancho lateral del contenedor de conversación.

El control compacto usa el icono **↶**, ocupa 10 columnas por 2 líneas y se
alinea a la derecha de su propia fila, con una línea de separación del mensaje
y un margen interno de una columna.

### Correcciones de conversación y actividad — 12 de septiembre

Se corrigieron los formatos de permisos y la negociación del App Server que
impedían responder incluso a un saludo. Una prueba autenticada devolvió «Hey!».
La inspección de paquetes ahora admite el alias `inspect_packages` del especialista
de instalación y reconoce búsquedas como «node» dentro de una solicitud natural.
La consulta MCP real confirmó Node.js 22 y 24 instalados con datos recién leídos.

Los avisos internos sobre falta de observación se trasladan al estado de actividad,
sin insertar respuestas prefabricadas y duplicadas en el chat. El indicador de
actividad muestra streaming y herramientas; un error de herramienta no se presenta
como una inspección realizada con éxito. Reinicia JARVIS para cargar estos cambios.

## Estado de la entrega

La nueva interfaz y sus cambios están en esta carpeta persistente:

```text
/home/tipexxx/Escritorio/Proyecto/codex-agent-system/runtime/staged/jarvis-2026-09-11-recovered
```

Los ejecutores de arranque y actualizaciones ya están instalados en el equipo
y registrados en Polkit. Sus propietarios y huellas se comprobaron desde otro
proceso. La instalación principal anterior de JARVIS no se ha sustituido:
para usar las novedades, arranca desde la carpeta indicada arriba.

La terminal normal pasó una prueba visible con un comando real. La conexión
con la cuenta habitual también se comprobó. Esto no equivale a haber completado
un turno real del agente ni a haber ejecutado una actualización del sistema.

## Arranque paso a paso

### 1. Entrar en la versión nueva

Abre una terminal normal, sin iniciar JARVIS como root:

```bash
cd /home/tipexxx/Escritorio/Proyecto/codex-agent-system/runtime/staged/jarvis-2026-09-11-recovered
```

Los comandos siguientes se ejecutan desde esa carpeta. No hace falta reinstalar
los ejecutores: ya están instalados.

### 2. Probar inmediatamente la interfaz y la terminal

```bash
.venv/bin/python scripts/smoke-normal-terminal.py --approve-printf-smoke
```

Este ensayo abre la interfaz, muestra la revisión de un `printf` fijo,
lo ejecuta una sola vez en la terminal normal y comprueba el regreso a la
interfaz. La confirmación está automatizada exclusivamente para ese comando
inocuo. No usa el modelo ni ejecutores root.

Al terminar debe aparecer `JARVIS_VISIBLE_SMOKE_PASSED`. Las capturas SVG
y el resultado JSON se guardan en una carpeta nueva dentro de
`runtime/validation/`, cuya ruta imprime la prueba.

### 3. Abrir la interfaz sin conectar al agente

```bash
PYTHONPATH="$PWD/tui/src" .venv/bin/python -m jarvis_tui --bundle-root "$PWD"
```

Sirve para explorar las vistas y comprobar que la interfaz abre. No habilita
por sí sola conversación con el modelo. Para etiquetas menos dependientes
del color, añade `--plain` al final.

### 4. Preparar el perfil propio de esta versión

Esta copia recuperada no traía `runtime/codex-home/config.toml`. Antes del primer
arranque conectado, genera el perfil con el renderizador incluido en el código:

```bash
PYTHONPATH="$PWD/tui/src" .venv/bin/python - <<'PY'
from pathlib import Path
from jarvis_tui.runtime_profile import render, check

bundle = Path.cwd()
profile = bundle / "runtime/codex-home/config.toml"
if not profile.exists() and not profile.is_symlink():
    profile.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with profile.open("x") as stream:
        stream.write(render(bundle))
    profile.chmod(0o600)
check(bundle)
print("Perfil de JARVIS verificado")
PY
```

Este paso crea únicamente configuración local de JARVIS; no copia credenciales
ni modifica la configuración habitual de Codex. Si ya existe un perfil, lo
comprueba sin sobrescribirlo. Si la comprobación falla, conserva el error para
revisión y no cambies sus controles para forzar el arranque.

### 5. Arrancar con conexión al agente

```bash
bash scripts/launch-tui.sh
```

El lanzador comprueba que carga el código de esta carpeta y conecta al App Server.
Usa el perfil propio de `runtime/codex-home`. Aunque tu cuenta habitual haya
pasado el sondeo, este perfil separado puede pedir iniciar sesión.

Si aparece **Sign in with ChatGPT**, pulsa ese botón y completa el acceso en
el navegador oficial. Después pulsa **Refresh session**. No copies archivos
de credenciales al proyecto ni pegues contraseñas o tokens en el chat.

Como primera petición puedes escribir: «Responde únicamente JARVIS listo, sin
usar herramientas». Comprueba que la sesión esté conectada y que recibes la
respuesta. Esta prueba de conversación completa aún no consta como realizada.
La petición de texto no constituye una aprobación de comandos.

## Nuevas capacidades y mejoras

| Área | Implementación y uso | Estado y alcance |
| --- | --- | --- |
| Terminal normal | Botón **Run in normal terminal** en **Development**, a partir de una propuesta de comando. Muestra argumentos, carpeta y modo antes de aprobar. | Probada con comando real; usa los permisos, entrada/salida y red normales del usuario. JARVIS no impone límites de tiempo o recursos en este modo. |
| Aprobación de terminal | El modo normal tiene una revisión propia, distinta de la ejecución aislada; registra la reserva antes de lanzar el comando. | Aprobación de un solo uso, caducidad y rechazo de repetición. |
| Entorno del comando | Vincula el entorno a la revisión y detecta cambios antes de ejecutar. | Los valores del entorno no se guardan en el expediente. |
| Resultado del comando | Registra intento, salida del proceso y modo; vuelve a la interfaz después de ejecutarlo. | Una salida cero no demuestra el objetivo completo ni que hayan terminado todos los procesos hijos. |
| Cargo aislado | Prepara check, build, test, fmt y clippy sobre una copia del proyecto. | Conserva límites y aislamiento en esta ruta, separados de la terminal normal. |
| Dependencias | Prepara cambios en copia y permite revisar una aplicación posterior al proyecto original. | Conserva originales y comprueba contenido y metadatos; la aplicación requiere su revisión. |
| Descargas de dependencias | Descarga puntual por URL y checksum del lockfile, con aprobación separada. | Después permite consumir el archivo verificado en compilación aislada. No supone acceso de red ilimitado para Cargo. |
| Ejecución privilegiada | Dos entradas root, un módulo compartido y políticas Polkit. | Instaladas y reconocidas; cada operación sigue necesitando solicitud exacta y evidencia independiente. |
| Selección de kernel | Prepara selección de una entrada instalada para el próximo arranque. | Código implementado; no se ha cambiado el kernel ni reiniciado el equipo en estas pruebas. |
| Reparación de initramfs | Genera una imagen nueva; su publicación es otra operación revisada que conserva la anterior. | Implementada y probada con simulaciones; no certifica que el sistema vaya a arrancar. |
| Actualizaciones | Reproduce una transacción DNF5 preparada con RPM firmados y verifica el conjunto instalado esperado. | No acepta diferencias mediante opciones ignore/skip. No se ha aplicado una transacción real en este cierre. |
| Prevención de cambios concurrentes | Recomprueba estado de arranque y huella de la transacción antes del efecto. | El mantenimiento root debe ser exclusivo; el bloqueo de JARVIS no controla otros administradores. |
| MCP y especialistas | Respeta el especialista seleccionado y limita herramientas por proceso y ámbito. | Corregido el registro de `recovery_plan`. |
| Interfaz | Vistas Health, Development, Network, Security y Recovery; revisión detallada fuera de la conversación. | Pruebas gráficas completadas. Las advertencias de tareas lentas no significaban por sí mismas un bloqueo. |
| Checkpoints | Conserva contexto y distingue recuperación del chat de recuperación de operaciones. | Recuperación completa solo cuando existe una operación recuperable vinculada. |
| Registros operativos | Resultados saneados, límites de tamaño/cantidad y política de siete días para registros nuevos. | No guarda entorno completo, credenciales ni razonamiento privado. |
| Recuperación | Planificación de las cinco fronteras del sistema y recuperación acotada de proyectos. | Automatización completa de Restic y recuperación de desastre siguen siendo alcances separados. |
| Empaquetado | Manifiesto e inventario calculados respecto a la raíz de la entrega. | Corregido el manifiesto vacío al estar dentro de una carpeta antecesora llamada runtime; ahora se rechazan manifiestos vacíos. |
| Instalación | Instalador con hashes fijados, rechazo de destinos existentes y limpieza de objetos recién creados si falla. | Instalación completada; no crea autorizaciones de operaciones. |

## Cómo funcionan los permisos

La terminal normal trabaja como tu usuario. La ruta privilegiada pasa por
Polkit y puede mostrar una ventana del sistema para autenticarte. Autenticarse
no aprueba cualquier cambio: la operación debe coincidir con su solicitud,
estado previo y autorización independiente, y cumplir la recuperación exigida.

La instalación creó estos archivos:

```text
/usr/libexec/jarvis-boot-control
/usr/libexec/jarvis-update-control
/usr/libexec/jarvis_privileged_control.py
/usr/share/polkit-1/actions/org.jarvis.boot-control.policy
/usr/share/polkit-1/actions/org.jarvis.update-control.policy
```

El estado protegido está en `/var/lib/jarvis/privileged-control`. Sus carpetas
contienen aprobaciones, reservas, resultados, transacciones y copias necesarias.
No se ha creado ninguna aprobación para modificar paquetes o arranque.

Los ejecutores rechazaron las peticiones vacías enviadas por Polkit con
`blocked_or_indeterminate`: era el resultado esperado de ese ensayo. Ante una
operación real, ese mismo estado necesita revisión y no equivale a éxito.

## Pruebas y comprobaciones disponibles

Para comprobar la disponibilidad de tu acceso habitual sin iniciar un turno:

```bash
.venv/bin/python scripts/smoke-authenticated.py --approve-account-probe
```

El resultado correcto es `account_available: true`. Su alcance es
`authenticated_connection_only`: no prueba una conversación completa.

Para verificar los archivos de la entrega:

```bash
.venv/bin/python scripts/verify-release-manifest.py
```

Para ejecutar la batería general de validación:

```bash
bash scripts/quality-gate.sh --full
```

Déjala finalizar: incluye pruebas gráficas que pueden tardar varios minutos.
En una sandbox, las pruebas de sockets pueden estar restringidas; durante
esta entrega se comprobaron por separado en el anfitrión. No se afirma que
la última repetición conjunta fuera de la sandbox llegara a ejecutarse.

## Lo que todavía no debe darse por terminado

- La sustitución de la instalación principal por esta versión.
- Un turno completo autenticado del agente en el perfil propio de esta entrega.
- Una operación real aprobada de kernel, initramfs o paquetes y su verificación.
- La automatización completa de backup al conectar el disco y conservación de
  las últimas diez copias: son requisitos aceptados, no prestaciones certificadas
  por esta instalación.
- La demostración de arranque de recuperación y restauración actual completa
  del equipo. La comprobación Restic aportada pasó, pero las comparaciones rsync
  sin checksum no prueban por sí solas todos los contenidos.

## Dónde encontrar los detalles

- [Registro actualizado de instalación y autenticación](runtime/staged/INSTALACION-2026-09-11.md).
- [Validación de la copia recuperada](runtime/staged/jarvis-2026-09-11-recovered/VALIDACION.md).
- [Guía técnica del parche](runtime/staged/jarvis-2026-09-11-recovered/docs/PARCHE-GUIDE-2026-09.md).

Esta guía recoge el estado posterior a la instalación de los ejecutores.
Cuando un documento histórico los describa como pendientes, consulta el registro
actualizado de instalación para esa parte del estado.
