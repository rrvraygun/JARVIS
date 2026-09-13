# Contrato de adaptador de plataforma

Los adaptadores traducen un procedimiento genérico en lectura y cambio específicos de la plataforma
operaciones. No otorgan autoridad. Un adaptador debe declarar detección,
Versiones compatibles, comandos, privilegios requeridos, efectos de lectura/escritura, red.
efectos, simulaciones, instantáneas, reversión, validación, análisis de estabilidad y
combinaciones inseguras conocidas.

La selección se basa en evidencia y se realiza antes de la planificación del procedimiento. Nunca infieras
un administrador de paquetes desde un único ejecutable cuando hay múltiples capas de host/contenedor
puede existir. No instale automáticamente una herramienta adaptadora faltante. Comandos que
cambiar la semántica entre versiones necesita puertas y accesorios de versión.

Cada adaptador mutante debe probarse en un entorno representativo desechable,
incluyendo ejecución interrumpida, falla parcial, falla de reversión, estado obsoleto,
y expansión inesperada del objetivo.
