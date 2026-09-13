# Observación del anfitrión delimitada y operaciones preparadas.

Esta revisión agrega una construcción útil orientada al host sin ampliar la vida
Autoridad H1. `vm-lab/scripts/lighting_observation.py` es un adaptador pasivo para
Luz de fondo fija, teclado LED y rutas de identificación de tarjeta DRM pasiva. Utiliza descriptores seguros,
lecturas limitadas y rechaza enlaces simbólicos, controles de terminal, campos de gran tamaño y
solicitudes de activación del dispositivo. No tiene shell, red, credencial, registro protegido,
identificador de dispositivo o ruta de escritura.

`diagnose()` convierte la observación limitada en hallazgos vinculados a la evidencia;
nunca escribe ni recomienda una reparación no observada. el preparado
La operación `lighting_repair_plan.py` puede vincular un diagnóstico y un estado previo a un
objetivo exacto y nivel de recuperación, pero su ejecutor siempre falla cerrado hasta que
adaptador independiente, autorización del sistema operativo, revisión independiente y puerta de implementación
existir.

El observador de iluminación pasiva ahora está registrado en Jarvisd, propiedad exclusiva del propietario.
límite del servicio después de la promoción explícita del usuario. Sigue siendo de un solo uso,
efímero y de solo lectura; la TUI no puede llamarlo directamente. El TuneD/PPD
El adaptador de perfil de energía y todas las rutas de mutación de reparación de iluminación permanecen
no registrado y discapacitado. Los manifiestos de operación niegan explícitamente la red,
autoridad de credencial, lectura protegida y activación de dispositivo.
