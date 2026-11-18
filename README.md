# Práctica 4: To-Do List - CI/CD y Observabilidad

**Alumno:** Vittorio Catino  
**Materia:** Desarrollo en la Nube  
**Fecha:** 18 de noviembre de 2026

API FastAPI que persiste tareas en RDS MySQL. Terraform crea EC2, Security Groups,
Key Pair, RDS, Secrets Manager, SNS, tres alarmas y un dashboard. El estado se
conserva en S3 cifrado, privado, versionado y con bloqueo nativo. EC2 usa
`LabInstanceProfile`, IMDSv2 y credenciales de RDS leídas en tiempo de ejecución.
No contiene contraseñas de RDS ni claves AWS en variables de entorno o en código.
Las variables de entorno sólo guardan región, nombre, versión y ARN del secreto.

## Arquitectura

```text
PR -> CI (pytest + lint) -> main protegido -> tag vX.Y.Z
                                          -> GitHub Release (ZIP + SHA256)
                                          -> Deploy -> SSM -> EC2:8000
Terraform <-> S3 state                                 |
       crea EC2 + RDS + secreto                        +-> Secrets Manager
                                                      +-> RDS privado
EC2 CPU nativa + boto3(DatabaseErrors, DatabaseLatency) -> CloudWatch
3 alarmas -> SNS -> correo confirmado; dashboard de las 3 métricas
GitHub Actions cron */5 * * * * -> GET /health
```

## Endpoints

| Método y ruta | Resultado |
| --- | --- |
| `GET /tasks` | Lista de tareas persistidas en RDS |
| `POST /tasks` | Crea `{ "title": "Estudiar", "done": false }`, HTTP 201 |
| `GET /version` | Versión tomada de `APP_VERSION` |
| `GET /health` | `database: OK/FAIL`, `version`, timestamp UTC; HTTP 503 si RDS falla |

Swagger está en `/docs`. La práctica expone HTTP en el puerto 8000; usar únicamente
datos sintéticos. RDS no es público: sólo acepta TCP 3306 desde el SG de EC2. No se
abre SSH. El Key Pair se crea para cumplir la rúbrica, pero no se utiliza para
aprovisionar ni desplegar.

## Pruebas y ejecución local

Requiere Python 3.12 (la EC2 usa Python 3 de Amazon Linux 2023).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check src tests scripts
pytest -q
```

Los tests usan SQLite en memoria e inyección de dependencias; no acceden a AWS.
Cubren lectura vacía, escritura/lectura, títulos inválidos, versión, salud, falla
de lectura/escritura y emisión de métricas. Para correr contra RDS con tu rol AWS:

```bash
export AWS_DEFAULT_REGION=us-east-1
export DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:NAME
export APP_VERSION=dev
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

No definir DB_PASSWORD, DB_USER ni otras credenciales en el entorno. La app obtiene
el JSON del secreto (`host`, `port`, `dbname`, `username`, `password`) con boto3,
mantiene la conexión con pre-ping y vuelve a leer el secreto cada cinco minutos.

## Configurar GitHub y el Learner Lab

1. Iniciar el Learner Lab y renovar sus tres credenciales temporales. Se deben
   actualizar cuando expire la sesión; no son credenciales permanentes.
2. En **Settings > Secrets and variables > Actions**, guardar como secretos:
   `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`.
3. Configurar variables: `AWS_REGION=us-east-1`,
   `TF_STATE_BUCKET=vittorio-practica4-state-912612781510` y
   `ALERT_EMAIL=vittorio.catino@iteso.mx`.
4. Mantener el repositorio público para que `user_data` pueda clonarlo y la EC2
   descargue los releases sin almacenar tokens de GitHub.
5. Proteger `main` exigiendo Pull Request y el status check `tests`, actualizado
   respecto a main. Aplicar también a administradores y no permitir force push.
   Un PR con tests fallidos debe quedar bloqueado; no hacer bypass.

## Crear la infraestructura

Ejecutar manualmente **Actions > Provision infrastructure > Run workflow**.
El workflow crea el bucket de estado con Terraform (`terraform/bootstrap`), guarda
su pequeño estado de bootstrap dentro de ese bucket y configura el backend S3 de
la aplicación. Luego ejecuta `plan`, `apply` y valida los cuatro endpoints.
Los demás recursos también son exclusivamente Terraform, no comandos `aws create`.

El bootstrap del bucket se hace una sola vez; futuras ejecuciones recuperan su
estado de S3. La creación inicial del bucket es la única etapa con estado local
transitorio. No se publica ningún tfstate ni plan como artifact o en Git. La
configuración `prevent_destroy` protege el bucket frente a un borrado accidental.
El estado contiene valores sensibles, incluido el password generado por Terraform;
por ello se cifra y no se adjunta al reporte ni se sube al repositorio.

`user_data` clona el repositorio, instala dependencias y habilita systemd. No es
necesario entrar por SSH ni usar `scp`. Terraform administra recursos y sus
dependencias; `user_data` configura el SO al crear la instancia. `scp` sólo copiaría
archivos a un servidor ya existente y no sustituye ninguna de esas funciones.

La primera creación de RDS puede tomar 10-20 minutos. La app puede arrancar antes
de RDS y `/health` devuelve FAIL hasta que la conexión esté lista. El workflow
espera la disponibilidad; consultar sus logs antes de reintentar.

**SNS:** abrir el mensaje de AWS enviado a tu correo y pulsar **Confirm subscription**.
Sin esa confirmación las alarmas existen, pero no entregan correo. Comprobar que
la suscripción no aparezca como `PendingConfirmation`.

## Release y despliegue

1. Crear una rama, abrir PR y dejar pasar CI antes de integrar en `main`.
2. Sobre un commit integrado en main:

```bash
git checkout main
git pull --ff-only
git tag v1.0.0
git push origin v1.0.0
```

3. **Release** corre los tests, valida el tag `vX.Y.Z`, empaqueta el commit exacto
   con `git archive`, calcula SHA-256 y publica ambos archivos en GitHub Release.
4. Tras publicarlo, dispara explícitamente **Deploy** mediante `workflow_dispatch`.
   Esto resuelve la restricción de GitHub que evita que eventos producidos por
   `GITHUB_TOKEN` encadenen otros workflows. El trigger `release: published` también
   permite desplegar releases publicados directamente por un usuario.
5. **Deploy** descubre la EC2 por tags y manda un comando por SSM. La EC2 descarga
   el ZIP desde el release, valida SHA-256, crea un entorno virtual por versión,
   cambia atómicamente el symlink y reinicia systemd. Si falla la salud vuelve al
   release anterior. Al finalizar compara `/version` con el tag esperado.

El workflow `health-check.yml` consulta `/health` cada cinco minutos y verifica
base de datos, versión y timestamp. Los cron de GitHub no son un SLA: pueden
demorarse. Mientras el lab esté cerrado o destruido, deshabilitar ese workflow
para evitar ejecuciones fallidas y habilitarlo al reaprovisionar.

## Métricas, alarmas y dashboard

| Métrica | Origen | Alarma | Justificación / respuesta |
| --- | --- | --- | --- |
| `AWS/EC2 CPUUtilization` | AWS nativa, monitoreo detallado | Promedio >=80%, 2 periodos de 60 s | Saturación sostenida: revisar tráfico/procesos y capacidad |
| `TodoList DatabaseErrors` | `boto3.put_metric_data` | Suma >=1, 1 periodo de 60 s | Una falla real de RDS ya impide trabajar: revisar estado RDS, SG, secreto y recuperar conexión |
| `TodoList DatabaseLatency` | `boto3.put_metric_data` | Promedio >=500 ms, 2 periodos de 60 s | Detecta degradación antes de una caída: correlacionar errores/CPU y revisar consultas/conexiones |

Las métricas propias llevan la dimensión `Application=practica4-todo`. Se emiten
ceros para operaciones correctas y uno para cada error. La latencia mide el tiempo
de operación completo de la dependencia de datos (incluyendo conexión y
verificación inicial del esquema), no sólo el tiempo interno del motor SQL.
La cola desacopla CloudWatch de las respuestas HTTP y vacía muestras cada 10 s.
Las alarmas CPU/latencia requieren dos periodos para reducir ruido. Errores/latencia
tratan falta de muestras como no infracción; ausencia de tráfico no implica una
base caída. El monitor `/health` cubre la disponibilidad cuando no hay tráfico.
Las tres alarmas notifican ALARM y recuperación OK al mismo tópico SNS.

Dashboard: `practica4-todo`. Su fuente es
`alerting/cloudwatch-dashboard.json.tftpl`; Terraform sustituye región e ID EC2.
Las alarmas están declaradas en Terraform y resumidas en `alerting/alarms.json`.

## Validar una alarma con una falla real

1. Ejecutar tráfico de prueba y confirmar `/health: OK`.
2. En RDS detener **únicamente** la instancia `practica4-todo`.
3. Consultar `/health` y `/tasks` mientras RDS esté detenido. Deben devolver 503;
   DatabaseErrors debe crecer y la alarma `practica4-todo-database-errors` pasar a
   ALARM. No usar `set-alarm-state` ni publicar errores falsos como evidencia.
4. Capturar el dashboard, detalle/historial de la alarma y el correo SNS.
5. Iniciar nuevamente RDS, esperar `available`, consultar `/health` y verificar OK.
   Guardar evidencia de recuperación antes de destruir la infraestructura.

## Destruir la infraestructura

Ejecutar manualmente **Destroy infrastructure**, escribiendo
`DESTROY-practica4-todo` en la confirmación. Ejecuta Terraform contra el mismo
estado remoto y comprueba que el estado de la aplicación quede sin recursos.
Se eliminan EC2, RDS y sus datos de prueba, SG, Key Pair, dashboard, alarmas y SNS;
el secreto se programa para eliminación con siete días de recuperación. No se
afectan recursos ajenos a este estado. Se conserva el bucket privado/versionado
con el estado para auditoría y evidencia. El destroy debe ejecutarse también en
GitHub Actions para que la rúbrica tenga una ejecución exitosa verificable.

## Entregables y evidencia

- Reporte de máximo dos páginas, sin portada: nombre, materia, fecha, descripción,
  diagrama y las **tres** reflexiones enumeradas en la consigna.
- Anexos adicionales al límite: capturas reales del dashboard, alarma ALARM y
  objeto `practica4/terraform.tfstate` en S3. No mostrar contenido del state.
- Repositorio con este README, código instrumentado, tests, Terraform y workflows:
  provisionar/destruir, CI, release, deploy y health-check.
- No se pide video. Guardar capturas antes de destruir los recursos.

## Referencias

- https://developer.hashicorp.com/terraform/language/backend/s3
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow
- https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch/client/put_metric_data.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Alarms.html

Se utilizó Codex como apoyo para implementar, revisar y documentar la práctica.
Las ejecuciones y capturas deben corresponder al entorno real, no a simulaciones.
