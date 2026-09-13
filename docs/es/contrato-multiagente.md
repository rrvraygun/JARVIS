# Contrato multiagente

## Roles

- Agente primario de Jarvis: descompone, encamina, concilia, autoriza a través del
  plano de control, y posee el resultado final y el cierre de la auditoría.
- Explorador de sistemas: evidencia acotada de solo lectura.
- Planificador de cambios: plan registrado listo para aprobación.
- Verificador de resultados: resultado independiente y verificación invariante.
- Auditor de políticas: control independiente y revisión del libro mayor.
- Revisor de recuperación: evaluación independiente de reversión, copia de seguridad y rescate.

## Reglas de delegación

Delegue únicamente trabajo independiente y delimitado. Indique las entradas exactas, las herramientas permitidas,
modo de permiso, propiedad del archivo/destino, resultado esperado, fecha límite y parada
condiciones. Los subagentes no pueden otorgar autoridad, ampliar el alcance, aceptar riesgos, aprobar una
cambiar o marcar su propia salida verificada de forma independiente.

Utilice pruebas y agentes de revisión separados para trabajos de alto impacto. No filtre un
conclusión prevista en un mensaje de evaluación independiente. Las primarias deben esperar
para obtener los resultados requeridos, reconciliar contradicciones, volver a aplicar políticas deterministas y
seguirá siendo responsable de la decisión final.

## Forma de transferencia

Conclusión de retorno; evidencia observada y procedencia; inferencias; incógnitas;
objetivos tocados; comandos o herramientas utilizadas; validación; preocupaciones políticas; y el siguiente
acción. Nunca devuelvas un simple "se ve bien".
