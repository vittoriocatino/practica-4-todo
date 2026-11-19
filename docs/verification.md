# Verificación real de la práctica

Alumno: Vittorio Catino. Fecha: 18 de noviembre de 2026.

Este registro enlaza ejecuciones reales; no sustituye las capturas del reporte.

| Comprobación | Evidencia |
| --- | --- |
| CI: 12 tests aprobados | [CI](https://github.com/vittoriocatino/practica-4-todo/actions/runs/44422924667) |
| Gate de main: CI fallido bloqueado y corrección integrada | [Pull Request 1](https://github.com/vittoriocatino/practica-4-todo/pull/1) |
| Terraform: 15 recursos de aplicación creados y smoke test RDS correcto | [Provision infrastructure](https://github.com/vittoriocatino/practica-4-todo/actions/runs/44422468293) |
| Tag y ZIP publicado | [Release](https://github.com/vittoriocatino/practica-4-todo/actions/runs/44422930434), [v1.0.0](https://github.com/vittoriocatino/practica-4-todo/releases/tag/v1.0.0) |
| Deploy SSM: checksum correcto y /version v1.0.0 | [Deploy](https://github.com/vittoriocatino/practica-4-todo/actions/runs/44422992734) |
| /health: RDS OK, versión y timestamp | [Health check](https://github.com/vittoriocatino/practica-4-todo/actions/runs/44423511976) |
| Caída real de RDS y recuperación: alarma ALARM y luego /health OK | [Validación exitosa](https://github.com/vittoriocatino/practica-4-todo/actions/runs/44423705652) |
| Destrucción completada y estado de aplicación vacío | [Destroy exitoso](https://github.com/vittoriocatino/practica-4-todo/actions/runs/44425106823) |

El estado remoto se verificó en
`s3://vittorio-practica4-state-912612781510/practica4/terraform.tfstate`.
Las credenciales no están en este registro ni en el repositorio.

Durante la prueba, RDS pasó a `stopping` y la API respondió HTTP 503. CloudWatch
pasó a ALARM a las 23:49 UTC; RDS llegó a `stopped` a las 23:52 UTC. Tras iniciar
RDS, el smoke test de las 23:56 UTC confirmó `/health: OK`, versión `v1.0.0` y
creación/consulta de una nueva tarea. No se inyectaron métricas falsas ni se usó
`set-alarm-state`.

El usuario confirmó la suscripción SNS de `vittorio.catino@iteso.mx`. Las capturas
reales se conservan localmente en `evidence/`, fuera de Git. El reporte se genera
en `output/pdf/practica-4-todo-vittorio-catino.pdf`: dos páginas de contenido y
anexos separados. La limpieza final se verifica con el estado de Terraform vacío;
el bucket de estado se conserva intencionalmente. Destroy terminó correctamente:
EC2 y RDS se eliminaron y el secreto quedó programado para borrado recuperable en
siete días. La API ya no está activa tras la limpieza autorizada.
