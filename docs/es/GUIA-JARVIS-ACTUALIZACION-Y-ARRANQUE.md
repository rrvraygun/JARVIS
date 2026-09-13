# JARVIS: actualizaciones, capacidades y guía de inicio

Actualizado: 11 de septiembre de 2026.

En Conversación, el selector especializado y los botones de acción ahora forman una vertical
barra lateral: **Nuevo**, **Historial**, **Copiar** y **Borrar** permanecen debajo del selector.
Cuando se abre el selector, su menú se superpone a la barra lateral sin mover los botones.

La pestaña **Agentes** incluye un selector de **Modelo global**. Una opción se aplica a todos
especialistas y se guarda en `runtime/jarvis-model.json` para nuevos turnos; giros activos
mantener su modelo actual. Las opciones son GPT-6 Astra, GPT-5.6 Sol, GPT-5.6 Terra,
GPT-5.6 Luna y GPT-5.5. **Se guardan el esfuerzo de razonamiento** y la **Ventana de contexto**
con el modelo. Las opciones de contexto son Automático, 8k, 16k, 32k, 64k, 128k, 256k, 512k,
800k, 1M y 1,05M. Los controles tienen su propio tamaño visible y se abren por dentro.
la pestaña **Agentes**.

La actividad en vivo se representa dentro del panel de Conversación. Se queda debajo de tu
pregunta mientras el agente trabaja y se mueve debajo de la respuesta del agente tan pronto como
aparece. Muestra fase, tiempo transcurrido, fragmentos, herramienta y consulta; detalles privados
y los resultados no desinfectados permanecen ocultos.

El riel de acción tiene un ancho fijo dentro del contenedor de conversación. **Nuevo**,
**Historial**, **Copiar** y **Borrar** ya no se mueven con un ancla en el borde de la pantalla;
Los controles de los puestos de control permanecen con su mensaje.

El punto de control conserva la etiqueta **↶ Punto de control** y su tamaño original. esta colocado
en su propia fila debajo del mensaje, alineado a la derecha con un separador superior y un breve
margen lateral. Su menú se construye después del botón y se abre debajo de él en un formato fijo.
capa vertical. El ancho de la conversación permanece fijo y el botón permanece
accesible. El menú nunca se superpone al botón ni recalcula el borde lateral.

### Correcciones de conversaciones y actividades: 12 de septiembre

Se corrigieron los formatos de permisos y la negociación del servidor de aplicaciones para que se pueda enviar un saludo.
completo. Una prueba autenticada arrojó "¡Oye!". La inspección del paquete ahora acepta
alias `inspect_packages` del especialista en instalación y reconoce la naturaleza
solicitudes como "nodo". Una consulta MCP en vivo confirmó Node.js 22 y 24 con datos nuevos
observaciones.

Los avisos internos de falta de observación ahora aparecen en el estado de actividad en lugar de
Insertar mensajes de marcador de posición duplicados en el chat. El indicador de actividad
muestra streaming y herramientas; un error de herramienta nunca se presenta como exitoso
inspección. Reinicie JARVIS para cargar estos cambios.

## Estado de entrega

La interfaz y la fuente actualizadas se guardan en:```text
/home/tipexxx/Escritorio/Proyecto/codex-agent-system/runtime/staged/jarvis-2026-09-11-recovered
```Los ejecutores de arranque y actualización se instalan y registran con Polkit. Su
Los propietarios y las huellas dactilares se comprobaron mediante un proceso separado. El principal anterior
La instalación de JARVIS no fue reemplazada; Comience desde el camino anterior para usar estos
cambios.

El terminal normal pasó una prueba visible con un comando real, y el habitual
Se comprobó la conexión de la cuenta. Ninguno de los resultados demuestra un giro completo del agente o
una verdadera actualización del sistema.

## Inicio paso a paso

### 1. Ingrese la nueva versión

Abra una terminal normal y no inicie JARVIS como root:```bash
cd /home/tipexxx/Escritorio/Proyecto/codex-agent-system/runtime/staged/jarvis-2026-09-11-recovered
```Ejecute los siguientes comandos desde este directorio. Los albaceas no necesitan ser
instalado nuevamente.

### 2. Pruebe la interfaz y el terminal inmediatamente```bash
.venv/bin/python scripts/smoke-normal-terminal.py --approve-printf-smoke
```Esta prueba abre la interfaz, muestra una revisión de un `printf` fijo, lo ejecuta
una vez en el terminal normal, y comprueba el retorno a la interfaz. Confirmación
está automatizado sólo para ese comando inofensivo. No utiliza el modelo ni la raíz.
ejecutores.

El resultado final debe incluir `JARVIS_VISIBLE_SMOKE_PASSED`. Capturas SVG y un
Los resultados JSON se almacenan en un nuevo directorio en `runtime/validation/`, cuya ruta
las impresiones de prueba.

### 3. Abra la interfaz sin conectarse al agente```bash
PYTHONPATH="$PWD/tui/src" .venv/bin/python -m jarvis_tui --bundle-root "$PWD"
```Utilícelo para explorar las vistas y comprobar que se abre la interfaz. no lo hace
permitir la conversación modelo por sí solo. Agregue `--plain` para etiquetas que dependan menos de
color.

### 4. Prepara el perfil privado de esta versión.

La copia recuperada no incluía `runtime/codex-home/config.toml`. Antes del
primer inicio conectado, cree el perfil con el renderizador incluido en el código:```bash
PYTHONPATH="$PWD/tui/src" .venv/bin/python - <<'PY'
from pathlib import Path
from jarvis_tui.runtime_profile import render, check

bundle = Path.cwd()
profile = bundle / "runtime/codex-home/config.toml"
si no es perfil.exists() y no perfil.is_symlink():
    profile.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with profile.open("x") as stream:
        stream.write(render(bundle))
    profile.chmod(0o600)
check(bundle)
print("JARVIS profile verified")
PY
```Esto crea sólo la configuración JARVIS local. No copia credenciales ni
cambiar la configuración habitual del Codex. Se comprueba un perfil existente sin
siendo sobrescrito. Si la verificación falla, mantenga el error para revisión en lugar de
cambiar los controles para forzar el inicio.

### 5. Comience con una conexión de agente```bash
bash scripts/launch-tui.sh
```El lanzador verifica que importa este checkout y se conecta a la aplicación
Servidor que utiliza `runtime/codex-home`. Incluso si se aprobara la investigación de cuenta habitual, esto
Un perfil separado puede solicitar el inicio de sesión.

Si aparece **Iniciar sesión con ChatGPT**, completa el inicio de sesión en el navegador oficial.
luego seleccione **Actualizar sesión**. No copie archivos de credenciales en el proyecto
o pegar contraseñas y tokens en el chat.

Como primera solicitud escriba: “Responder solo JARVIS listo, sin utilizar herramientas”. comprobar
que la sesión esté conectada y que llegue una respuesta. Un completo conectado
La prueba de conversación no se registra como completada aquí. La entrada de texto no es un comando
aprobación.

## Nuevas capacidades y mejoras

| Área | Implementación y uso | Estado y alcance |
| --- | --- | --- |
| Terminales normales | **Ejecutar en terminal normal** en **Desarrollo**, con revisión de comandos, directorios y autoridad de usuario. | Probado con un mando real; Utiliza los permisos, E/S y red normales del usuario. |
| Aprobación de terminales | Revisión separada de ejecución aislada, con reserva duradera antes del lanzamiento. | Aprobación de un solo uso, caducidad y rechazo de repetición. |
| Entorno de mando | Vincula el entorno a la revisión y detecta cambios antes de la ejecución. | Los valores del entorno no se almacenan en el registro. |
| Resultado del comando | Registra el intento, la salida del proceso y el modo, luego regresa a la interfaz. | La salida cero no prueba el objetivo completo ni la finalización del proceso hijo. |
| Carga aislada | Ejecuta check, build, test, fmt y clippy en una copia del proyecto. | Los límites y el aislamiento permanecen separados del terminal normal. |
| Dependencias | Prepara los cambios en una copia y ofrece la solicitud revisada al original. | Se conservan los originales y los metadatos; La aplicación necesita su propia revisión. |
| Descargas de dependencias | Descarga de una URL/suma de comprobación con una aprobación independiente. | Los archivos verificados pueden consumirse mediante compilaciones aisladas; Cargo no tiene una red ilimitada. |
| Ejecución privilegiada | Entradas de arranque/actualización separadas, módulo raíz compartido y políticas de Polkit. | Instalado y reconocido; cada operación todavía necesita una solicitud exacta y evidencia independiente. |
| Selección de granos | Prepara una entrada instalada para el próximo arranque. | Implementado; No se produjo ningún cambio de kernel ni reinicio en estas pruebas. |
| Reparación de initramfs | Genera una nueva imagen; La publicación es una operación revisada que preserva la imagen anterior. | Simulado y probado; no certifica la capacidad de arranque. |
| Actualizaciones | Reproduce una transacción DNF5 preparada con RPM firmados y verifica el conjunto instalado esperado. | Se rechazan las diferencias que se ignoran/omiten; no se aplicó ninguna transacción real en este cierre. |
| Prevención de cambios concurrentes | Vuelve a comprobar el estado de arranque y la huella digital de la transacción antes de los efectos. | El mantenimiento de raíces debe ser exclusivo; JARVIS no bloquea a otros administradores. |
| MCP y especialistas | Respeta al especialista seleccionado y limita las herramientas por proceso y alcance. | `recovery_plan` registro corregido. |
| Interfaz | Vistas de estado, desarrollo, red, seguridad y recuperación. | Pruebas gráficas completadas; Los avisos de tareas lentas por sí solos no son un bloqueo. |
| Puntos de control | Preserva el contexto y separa la recuperación del chat de la recuperación de la operación. | La recuperación total sólo existe cuando una operación vinculada es recuperable. |
| Registros operativos | Resultados desinfectados, límites de tamaño/recuento y una política de siete días para nuevos registros. | Sin entorno completo, credenciales o razonamiento privado. |
| Recuperación | Planifica cinco límites del sistema y recuperación del proyecto acotado. | La automatización completa de Restic y la recuperación ante desastres siguen siendo ámbitos separados. |
| Embalaje | El manifiesto y el inventario se calculan a partir de la raíz de entrega. | Se rechazan los manifiestos vacíos causados ​​por un directorio principal `runtime`. |
| Instalación | Hashes fijados, rechazo de destinos existentes y limpieza de objetos recién creados en caso de falla. | Instalación completada; no crea aprobaciones de operación. |## Cómo funcionan los permisos

El terminal normal se ejecuta como el usuario actual. Las rutas privilegiadas utilizan Polkit y
puede mostrar un cuadro de diálogo de autenticación del sistema. La autenticación por sí sola no aprueba una
cambio: la operación debe coincidir con su solicitud, estado previo, aprobación independiente,
y requisitos de recuperación.

La instalación creó:```text
/usr/libexec/jarvis-boot-control
/usr/libexec/jarvis-update-control
/usr/libexec/jarvis_privileged_control.py
/usr/share/polkit-1/actions/org.jarvis.boot-control.policy
/usr/share/polkit-1/actions/org.jarvis.update-control.policy
```El estado protegido se almacena en `/var/lib/jarvis/privileged-control`, incluido
aprobaciones, reservas, resultados, transacciones y copias requeridas. Sin aprobación
para cambiar paquetes o estado de arranque.

Los ejecutores rechazaron solicitudes vacías de Polkit con `blocked_or_indeterminate`; eso
Era el resultado esperado de la investigación. En una operación real el mismo estado requiere
revisión y no es un éxito.

## Cheques disponibles

Para comprobar la disponibilidad habitual de la cuenta sin iniciar un turno:```bash
.venv/bin/python scripts/smoke-authenticated.py --approve-account-probe
```El resultado esperado es `account_available: true`. Su alcance es
`authenticated_connection_only`; no prueba una conversación completa.

Para verificar archivos de entrega:```bash
.venv/bin/python scripts/verify-release-manifest.py
```Para ejecutar la puerta de validación completa:```bash
bash scripts/quality-gate.sh --full
```Déjalo terminar porque las pruebas gráficas pueden tardar varios minutos. En una caja de arena,
las pruebas de encaje pueden restringirse; esas pruebas se verificaron por separado en el host.

## Lo que aún no está completo

- Sustitución de la instalación principal anterior por esta versión.
- Un turno completo de agente autenticado utilizando el perfil privado de esta entrega.
- Un kernel, initramfs o operación de paquete real aprobado y su verificación.
- Automatización de copia de seguridad completa cuando el disco externo está conectado y retención del
  últimos diez ejemplares.
- Arranque de recuperación demostrado y restauración actual completa de la estación de trabajo.

## Dónde encontrar detalles

- [Registro actualizado de instalación y autenticación](../../runtime/staged/INSTALACION-2026-09-11.md).
- [Validación de la copia recuperada](../../runtime/staged/jarvis-2026-09-11-recovered/VALIDACION.md).
- [Guía técnica del parche](../../runtime/staged/jarvis-2026-09-11-recovered/docs/PARCHE-GUIDE-2026-09.md).

Esta guía describe el estado después de la instalación del ejecutor. Cuando un histórico
El documento dice que un componente está pendiente, use el registro de instalación actual.
para el estado actual.
