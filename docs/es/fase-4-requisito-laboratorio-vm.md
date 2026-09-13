# Requisito previo de la fase 4: estructura de laboratorio de escenarios de Fedora

## Resultado

Se implementa el requisito previo de laboratorio sin ejecución y
dispositivo validado. Define el sistema mensurable: capas gemelas, aislamiento
reglas, bloqueo de imagen oficial, línea de base limpia y ciclo de vida de superposición, registro de ejecución,
techo de promoción, brechas físicas, matriz de plano de control entre dominios y el
iluminación/matriz de diagnóstico NVIDIA.

Esta no es la finalización operativa de la Fase 4. Quedan observaciones registradas
deshabilitado hasta que un invitado Fedora desechable real sea aprovisionado por separado y el
Los adaptadores exactos pasan sus pruebas.

Sin escaneo de host, consulta de paquete, sonda de preparación de virtualización, resolución de imagen o
descarga, creación/inicio de VM, conexión de hipervisor, paso a través, iluminación
observación, instalación, limpieza, actualización, reparación, acción privilegiada, sistema
Se produjo una mutación o una automodificación del agente.

## Evidencia

- 37 escenarios de regresión seleccionados pasan sus oráculos deterministas.
- La matriz de iluminación evalúa 64.512 casos estatales y los aplica en cuatro
  Contextos de visualización externa: 258.048 casos lógicos.
- La matriz de sysadmin evalúa 60.480 casos de políticas/evidencias y los aplica
  en 17 dominios de capacidad aceptados: 1.028.160 casos lógicos.
- Cada oráculo es accesible y cada par declarado está cubierto.
- Diez brechas de hardware/firmware/físicas permanecen abiertas por diseño.
- El futuro bloqueo de la imagen oficial de Fedora no está resuelto y la adquisición está cancelada.
- La plantilla gemela no registra vinculación de host, ni escaneo, ni hardware o
  hechos de software.
- Toda bandera de autoridad operativa es falsa.
- Las pruebas estáticas rechazan importaciones y ejecutables de procesos/redes/virtualización.
  claves de interfaz de los activos de la máquina.
- El techo de promoción de evidencia de fijación es la etapa de madurez 1.

Los recuentos y los resúmenes del espacio de estado están fijados en vm-lab/coverage/expected.json;
cambiar una dimensión u oráculo falla la validación hasta que se revisa el contrato
La revisión actualiza la expectativa.

## Lo que esto prueba

Demuestra un manejo determinista de la política declarada y el espacio de falla,
incluyendo denegación nunca positiva, fracaso de la auditoría, ambigüedad/expansión del objetivo,
estado obsoleto, salida hostil y mal formada, tiempo de espera, denegación de permiso, alcance
confusión, repetición, ampliación, efectos sorpresa, bloqueo de mutaciones, recuperación
Falla, contradicción y ramificación de diagnóstico de iluminación.

No prueba:

- que la virtualización esté instalada o sea utilizable en la estación de trabajo;
- la versión actual de Fedora, kernel, paquetes, controladores, hardware, firmware o
  configuración;
- que una futura imagen de Fedora sea auténtica;
- que un reinicio de invitado sea realmente limpio;
- que cualquier adaptador de observación Fedora se comporte correctamente;
- que una VM normal reproduzca la GPU física, el panel, el teclado, ACPI/EC,
  teclas de acceso rápido, suspender sincronización, batería, térmicas o cableado de conectores;
- que la correlación notificada por NVIDIA es causal;
- que se haya observado o reparado la luminosidad o iluminación del teclado.

## Límite actual

vm-lab/scripts/labctl.py lee solo el JSON versionado del proyecto e imprime informes.
No tiene shell, proceso, red, hipervisor, privilegios, dispositivo, recopilador de host,
controlador invitado o API de persistencia. El registro de ejecución de ejemplo establece explícitamente
que no se inició ninguna VM, no se observó ningún huésped y no se intentó ninguna mutación.

El diseño completo y los puntos de control futuros se encuentran en vm-lab/README.md.

## Punto de control estructural posterior

El futuro límite del controlador VM escrito y la estación de trabajo exacta de solo lectura
La propuesta de inscripción ya está preparada y validada en
`phase-4-l1-controller-enrollment.md`. No se realizó ninguna observación. L1 permanece
operativamente incompleto hasta la propuesta, adaptadores, almacenamiento cifrado,
corredor de observación, ensayos de VM y un nuevo pase de decisión de inscripción explícita
sus propias puertas.El siguiente punto de control estático está documentado en
`phase-4-l2-full-vm-blueprint.md`: cuatro analizadores de dispositivos de nivel 0, un Fedora completo
Diseño de estación de trabajo con perfiles gráficos y sin cabeza, dieciocho niveles de preparación para L2
definiciones y ocho puertas de aprovisionamiento cerradas. Tampoco realizó ningún anfitrión.
observación o acción de VM.
