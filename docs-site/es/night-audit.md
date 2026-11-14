# Auditoría nocturna

La auditoría nocturna cierra la fecha operativa del hotel. Registra los cargos
de habitación de la noche para cada huésped alojado, aplica la política de no
presentados, guarda un paquete de auditoría con los informes del día y avanza la
fecha operativa un día. Puede cerrar el día a mano desde **Auditoría nocturna**,
y se ejecuta sola cada noche a la hora fijada para cada alojamiento (las 03:00
si no la cambia). Pueden ejecutarla los usuarios de Recepción, Finanzas, el
Auditor nocturno y el Administrador del hotel.

## Antes de empezar

1. **Revise las reglas de no presentados.** **Configuración → Recepción → Auditoría nocturna y
   no presentados** decide cuándo una llegada que nunca se produjo pasa a ser No presentado;
   el cargo está en **Configuración → Políticas de estancia → Cargo por no presentación**. Consulte
   [Configuración](#configuracion).
2. **Decida qué bloquea la auditoría.** **Configuración → Recepción → Lista de comprobaciones de
   auditoría nocturna** define qué comprobaciones detienen una ejecución manual, el umbral de
   saldo elevado y qué hace la ejecución automática cuando algo sigue pendiente.
3. **Asigne el rol de Auditor nocturno a su auditor nocturno** si no tiene
   Recepción ni Finanzas: **Configuración → Personal y acceso**. Con ese rol puede
   cerrar el día y autorizar excepciones a los bloqueos, registrar entradas y
   salidas de huéspedes, cerrar sesiones de caja y ver folios, el resumen por
   cajero y los informes.

## Abrir la auditoría nocturna

Abra **Finanzas → Auditoría nocturna** (también en **Recepción**, o escriba *night
audit*, *end of day* o *EOD* en la búsqueda, Ctrl/Cmd+K). Verá una tarjeta por
alojamiento: su fecha operativa y su hora local, las llegadas y salidas
pendientes, las cajas abiertas, las cuentas abiertas del punto de venta, y
**Listo** o el número de bloqueos. Pulse **Cerrar el día** (o **Revisar y
cerrar** cuando algo bloquea).

![Auditoría nocturna: una tarjeta por alojamiento con las llegadas y salidas pendientes, las cajas abiertas y las cuentas abiertas del punto de venta, y el historial de auditoría con las fechas De y A y Exportar CSV](/img/night-audit/manage.png)

## La página de cierre del día

Una sola página muestra todo lo de la fecha operativa:

- **La línea de arriba**: la fecha que cierra, una etiqueta (**Listo**, **N por
  revisar** o **Fecha sin actualizar**) y el botón **Cerrar**.
- **N de M comprobaciones correctas**, con una barra, y lo que impide el cierre.
- **Requiere su atención**: solo las comprobaciones que encontraron algo, primero
  las que bloquean. Cada una tiene su lista y los botones para resolverla.
- **Informativas**: las comprobaciones que solo informan (las habitaciones
  libres, por ejemplo) y las comprobaciones en las que autorizó una excepción.
- **Todo correcto**: cada comprobación que no encontró nada, reunidas en una
  sola línea.
- **Cajas en esta fecha**: el efectivo esperado y el contado de cada sesión.
- **Notas para el administrador**: el tiempo, los incidentes, el relevo de turno.
  Se guardan al salir del cuadro y se imprimen en el paquete de auditoría.

![Cerrar el día: la fecha y el botón Cerrar arriba, cuántas comprobaciones están correctas y, en Requiere su atención, las salidas que siguen alojadas con Cómo resolverlo y la lista](/img/night-audit/close-day.png)

Qué hace cada comprobación cuando encuentra algo:

| Comprobación | Qué hace usted |
| --- | --- |
| Llegadas pendientes de registrar | **Registrar entrada** o **Marcar como no presentado**. Cada fila muestra lo que hará con ella la política de no presentados. |
| Salidas que siguen alojadas | **Registrar salida**, **Extender estancia** o **Registrar rápidamente la salida** de todas las salidas sin saldo a la vez. Bloquea por defecto. |
| Saldos elevados, saldos de estancias ya terminadas, empresas por encima de su límite, facturas de empresa vencidas | Revíselos; abra el folio o Cuentas por cobrar. |
| Cuentas abiertas del punto de venta | Liquídelas en el punto de venta. Bloquea por defecto. |
| Cuentas del punto de venta cargadas a habitaciones | Busque un cargo a la habitación equivocada. |
| Diferencia de tarifa y habitaciones con tarifa cero | Noches de habitación registradas con una tarifa distinta de la reservada. |
| Estado de la habitación | Habitaciones en las que recepción y el tablero de habitaciones no coinciden. |
| Cajas abiertas | Escriba el efectivo contado y pulse **Contar y cerrar**. Bloquea por defecto. |

Cada lista se puede buscar y ordenar.

**Marcar como no presentado** aplica la política del alojamiento de inmediato:
la estancia pasa a No presentado y el cargo se registra en la fecha operativa, o
se exonera si es una reserva de una OTA. Solo se puede marcar una llegada
Confirmada prevista para la fecha operativa o antes.

El mismo botón **Marcar como no presentado** está en la tarjeta de Llegadas de
**Hoy** (para una llegada prevista para la fecha operativa o antes) y en la página
de la reserva, para Recepción y el Auditor nocturno. Antes de registrar nada, un
paso de confirmación muestra el cargo que registrará la política con impuestos (o
por qué no hay ninguno), lo que el huésped ya pagó y lo que sobra. Al confirmar,
la habitación queda libre al momento para un huésped sin reserva previa: los canales
reciben la nueva disponibilidad y las demás pantallas de recepción abiertas se
actualizan.

### Cuando el huésped pagó más que el cargo

Si el anticipo es mayor que el cargo por no presentación, el resto queda como
saldo a favor en el folio. El paso de confirmación ofrece entonces:

- **Reembolsarlo al huésped**: elija cómo y dé un motivo. Pasa por el reembolso
  normal (caja abierta, PIN de cajero) y sale del libro de anticipos.
- **Retenerlo como anticipo perdido**: dé un motivo. Kamra registra una línea
  **Anticipo retenido (no presentado)** con el tipo de impuesto de la habitación
  para que el folio quede en cero.

**Configuración → Recepción → Auditoría nocturna y no presentados → Cuando un no
presentado pagó más que el cargo** decide cuál aparece elegido primero. **Decidir
después** deja el saldo a favor en el folio; el paquete de auditoría muestra cada
no presentado que sigue con saldo a favor en **No presentados con saldo a favor**,
para la mañana.

## Resolver un bloqueo o autorizar una excepción

Tres comprobaciones bloquean el cierre por defecto: cajas abiertas, cuentas de
restaurante abiertas y huéspedes con salida prevista que siguen alojados. Mientras
una tenga elementos, el botón **Cerrar** sigue desactivado. Resuélvala (registre
la salida del huésped, liquide la cuenta del restaurante, cierre la caja) o
autorice una excepción:

1. Lea **Cómo resolverlo** bajo la comprobación: las soluciones habituales,
   **Pídale ayuda al agente Kamra** y lo que pasa **Si autoriza la excepción**.
2. Escriba el motivo en el cuadro bajo la lista, por ejemplo *"Salidas
   tardías aprobadas por el gerente de turno"*.
3. Pulse **Autorizar excepción con un motivo**. La comprobación pasa a **Informativas**.

Su nombre, la hora y el motivo se guardan en la auditoría, aparecen bajo las
notas, se imprimen en el paquete y quedan en el Registro de actividad. Las
advertencias nunca bloquean: revíselas y cierre.

Un cajero también puede cerrar su propia caja en **Finanzas → Mi caja**: consulte
[Facturación](/es/billing#contar-el-efectivo-y-cerrar-la-caja).

## Cerrar el día

1. Cuando nada bloquee, pulse **Cerrar** arriba (lleva la fecha).
2. Kamra registra la noche y muestra lo que ha hecho: las noches de habitación
   registradas y su importe, los no presentados y la nueva fecha operativa.
3. El paquete de auditoría se abre en la misma página. Cada tabla tiene
   **Exportar CSV**.

![Cerrar el día: autorizar excepciones a los bloqueos con un motivo, contar y cerrar la caja, añadir una nota y pulsar Cerrar](/img/night-audit/run-close.gif)

No se puede deshacer. La auditoría solo cierra la fecha operativa actual del
alojamiento, y solo cuando ese día ya ha empezado en el servidor: no puede
ejecutar esta noche la auditoría de mañana.

## Qué registra la auditoría

Para cada huésped alojado en la fecha operativa:

- una noche de **Habitación** con la tarifa confirmada al reservar para esa noche
  (temporada, precios según la demanda y plan tarifario incluidos), enviada al folio de
  empresa cuando la empresa paga la habitación;
- el **Plan de comidas** de la noche, si la estancia lo tiene;
- la **Tasa de alojamiento** (tasa municipal o turística), si el alojamiento la tiene;
- un cargo de **Huéspedes adicionales**, si la estancia lo tiene acordado.

Las noches que ya están en el folio se omiten, así que volver a ejecutarla, o una
salida que ya registró la noche, nunca cobra dos veces. Si falta el folio del
huésped, se abre.

Para las llegadas que nunca se produjeron se aplica la política de no presentados: la estancia
pasa a **No presentado** y el **Cargo por no presentación** (primera noche o toda la estancia)
se registra en la fecha que se cierra, salvo que la llegada se mantenga como llegada
tardía o el cargo se exonere por ser una reserva de una OTA.

La auditoría también elimina las entradas de la lista de espera dos días después de su fecha de
salida solicitada.

## Enviar informes por correo tras la auditoría

Cualquier informe personalizado puede salir por correo en cuanto la auditoría
cierra el día: ábralo en **Informes → Informes personalizados**, ponga
**Programación de correo** en **Después de la auditoría nocturna**, añada los
destinatarios y pulse **Guardar**. Cada uno se envía para la fecha operativa
recién cerrada, en CSV. Consulte
[Crear un informe personalizado](/es/reports#crear-un-informe-personalizado).

## Imprimir el paquete de auditoría

Tras el cierre, el paquete muestra los informes finales a la izquierda. Elija uno
para leerlo y luego **Imprimir** o **Descargar PDF** (elija *Guardar como PDF* en
el cuadro de impresión); **Imprimir todo** imprime el paquete completo en A4. Cada
tabla tiene **Exportar CSV**, con las cifras sin formato:

- Informe de auditoría nocturna: el día, el mes en curso y el año en curso uno al
  lado del otro (noches de habitación, ocupación, habitaciones, ADR, RevPAR,
  comida, bebida, banquetes, plan de comidas y minibar, otros, total); la comida y
  la bebida de cada punto de venta; los banquetes; y las cuentas de huéspedes, los
  anticipos y las cuentas por cobrar a empresas con su saldo anterior, el
  movimiento del día y el saldo final. La comida y la bebida salen de las cuentas
  del restaurante, pagadas en el punto de venta o cargadas a una habitación, con
  las bebidas alcohólicas como bebida. En India el año empieza el 1 de abril. Las
  auditorías cerradas antes de este informe no tienen copia de él.
- Resumen gerencial
- Diario por cajero y código de transacción
- Resumen por cajero
- Detalle de cuentas de huéspedes
- Resumen de cuentas por cobrar a empresas
- Saldo de depósitos y anticipos
- Balance de comprobación, cuya línea de total indica si los libros coinciden con los
  folios: **Concuerda con los folios** o **Hay una diferencia de** un importe **respecto a los folios**
- Ocupación e ingresos (% de ocupación, ADR, RevPAR)
- No presentados y cancelaciones
- Diferencia de tarifa
- Comprobaciones previas e incidencias, con cada autorización

![Los informes finales del paquete de auditoría de una fecha operativa cerrada](/img/night-audit/audit-pack.png)

El paquete se guarda en la auditoría cuando se ejecuta, así que reimprimir una
noche pasada da exactamente lo que se imprimió esa noche. Encuentre las auditorías
pasadas en **Historial de auditoría**, al pie de **Auditoría nocturna**: elija las
fechas **De** y **A**, pulse **Exportar CSV** para la lista, o **Imprimir** en la
columna **Paquete de auditoría**. Las ejecuciones automáticas aparecen ahí con el
origen **Programado**. Si falta un paquete, pulse **Reconstruir paquete**: vuelve
a crear los informes imprimibles sin registrar cargos otra vez.

En la tarjeta del alojamiento, **Imprimir paquete** abre el paquete de la última
ejecución, si se guardó uno.

![Historial de auditoría: cada fecha operativa cerrada con su estado, origen, noches de habitación, importe registrado, no presentados, incidencias y un enlace a su paquete de auditoría](/img/night-audit/history.png)

## La ejecución automática

Kamra comprueba cada 15 minutos. Cuando el reloj de un alojamiento pasa su hora de
**Ejecutar a las** (03:00 por defecto, más el tiempo de **Esperar después de esa
hora**) y su fecha operativa sigue por detrás de la fecha del calendario, ejecuta
la auditoría de ese alojamiento. El reloj es la **Zona horaria** del alojamiento
(Configuración → Alojamiento), así que dos hoteles en zonas horarias distintas
cierran cada uno a sus 03:00. Desactive **Ejecutar la auditoría nocturna
automáticamente** para cerrar el día solo a mano; la tarjeta de Auditoría nocturna
muestra entonces **auditoría automática desactivada**. Estas opciones están en
**Configuración → Recepción → Auditoría nocturna automática**, y las puede cambiar
el Administrador del hotel.

La ejecución automática hace el mismo trabajo que la manual. Si una comprobación
que bloquea sigue pendiente, sigue lo indicado en **Auditoría programada cuando
hay bloqueos**:

- **Ejecutar y registrar incidencias** (por defecto): la fecha avanza y los
  elementos pendientes se registran como incidencias en el paquete.
- **Detener y avisar**: la fecha operativa no cambia, y los usuarios
  Administrador del hotel y Finanzas reciben una notificación en la aplicación y
  un correo electrónico. La tarjeta de Auditoría nocturna muestra **Auditoría
  retenida**: resuelva los bloqueos y pulse **Revisar y cerrar**, y luego imprima
  el paquete.

Si alguien ya cerró el día a mano, la ejecución automática lo omite. Un día
retenido, omitido o fallido se intenta una vez al día, no cada 15 minutos. Un
fallo avisa a los usuarios Administrador del hotel.

Cada ejecución, automática o manual, aparece en **Ejecuciones de la auditoría
nocturna** en esa misma página de configuración: cuándo empezó, quién la ejecutó
(o el programador), el resultado (Cerrado, Retenido, Omitido o Fallido) y el
motivo. Auditoría nocturna muestra la próxima ejecución automática en cada tarjeta
de alojamiento.

Si se saltaron algunos días (por ejemplo, porque el servidor estuvo caído), la
ejecución automática los cierra uno en cada comprobación de 15 minutos, del más
antiguo al más reciente, hasta tres días. Un alojamiento con más de tres días de
retraso no se cierra automáticamente: el Administrador del hotel y Finanzas
reciben un aviso, para que alguien revise las estancias en curso y las llegadas
antes de que se registren semanas de noches de habitación y cargos por no
presentación. Cierre esos días desde Auditoría nocturna.

### Si la fecha operativa parece atascada

Una auditoría completada para la fecha operativa abierta sin que la fecha haya
avanzado (tras una restauración o un cambio de operaciones) muestra **Fecha sin
actualizar**. Pulse **Avanzar la fecha operativa**: Kamra avanza la fecha operativa
sin volver a registrar noches de habitación. No puede deshacer una auditoría
nocturna completada. La ejecución automática hace lo mismo sola cuando encuentra
una fecha atascada, y después cierra el día que realmente toca.

## Configuración

![Configuración → Recepción → Lista de comprobaciones de auditoría nocturna](/img/night-audit/settings.png)

| Opción | Dónde | Valor por defecto | Qué hace |
| --- | --- | --- | --- |
| Las cajas abiertas bloquean la auditoría | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | Activado | Desactivado, muestra las sesiones de caja abiertas como advertencia. |
| Las cuentas de restaurante abiertas bloquean la auditoría | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | Activado | Desactivado, las muestra como advertencia. |
| Las salidas pendientes de registrar bloquean la auditoría | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | Activado | Desactivado, las muestra como advertencia. |
| Extender una noche las salidas sin check-out | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | Desactivado | Activado: un huésped que sigue alojado después de su fecha de salida recibe una noche más cuando se ejecuta la auditoría, por el mismo camino que **Extender estancia**, y esa noche se registra. Una estancia que no se puede extender (la habitación está reservada) sigue en la lista de comprobaciones. La comprobación de salidas muestra a estos huéspedes como advertencia y no como bloqueo. |
| Marcar los folios de huéspedes alojados cuyo saldo supere | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | 50000 | 0 desactiva la comprobación de saldo elevado. |
| Tolerancia de diferencia de tarifa | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | 1 | Cuánto (en unidades de moneda) puede alejarse una noche registrada de la tarifa reservada antes de aparecer en la lista. |
| Ejecutar la auditoría nocturna automáticamente | Configuración → Recepción → Auditoría nocturna automática | Activado | Desactivado: solo el personal cierra el día. |
| Ejecutar a las | Configuración → Recepción → Auditoría nocturna automática | 03:00 | Hora local del alojamiento. |
| Esperar después de esa hora | Configuración → Recepción → Auditoría nocturna automática | 0 min | Hasta 120 minutos más, para los puntos de venta que aún registran. |
| Auditoría programada cuando hay bloqueos | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | Ejecutar y registrar incidencias | O **Detener y avisar**. |
| Marcar huéspedes no presentados | Configuración → Recepción → Auditoría nocturna y no presentados | En la auditoría de la fecha de llegada | **Un día después** mantiene la llegada como prevista hasta la auditoría del día siguiente. |
| Mantener las reservas de llegada tardía hasta la próxima auditoría | Configuración → Recepción → Auditoría nocturna y no presentados | Activado | Una llegada prevista para el día que se cierra sigue como prevista si está marcada como **Llegada tardía** o si su hora estimada de llegada es posterior al momento en que se ejecuta la auditoría. Una hora estimada anterior a las 06:00 cuenta como después de medianoche. |
| No aplicar cargos por no presentación a reservas de agencias en línea | Configuración → Recepción → Auditoría nocturna y no presentados | Activado | Las reservas de OTA se siguen marcando como No presentado, pero no se registra ningún cargo. |
| Cuando un no presentado pagó más que el cargo | Configuración → Recepción → Auditoría nocturna y no presentados | Reembolso | **Reembolso** o **Retener como anticipo perdido**: la opción que se ofrece primero para el resto del anticipo. |
| Liberar las reservas de llegada sin garantía a las | Configuración → Recepción → Auditoría nocturna y no presentados | En blanco (desactivado) | A esta hora, las llegadas de hoy sin anticipo, pago ni depósito, y que no vienen de una OTA ni de una empresa, se cancelan sin cargo. |
| Cargo por no presentación | Configuración → Políticas de estancia → Cancelación y no presentación | Primera noche | **Ninguno**, **Primera noche** o **Toda la estancia**. |

## Conviene saber

- **Cualquiera que pueda cerrar el día puede autorizar una excepción a un
  bloqueo.** La comprobación se hace por rol (Recepción, Finanzas, Auditor
  nocturno, Administrador del hotel), y se registran el nombre y el motivo.
- **Las noches de habitación se cobran con la tarifa confirmada al reservar.** Un cambio de tarifa
  posterior o una temporada nueva nunca cambia una estancia confirmada.
- **La auditoría nunca registra una noche después de la fecha de salida.** Un huésped que
  sigue alojado después de su fecha de salida no recibe cargo de noche hasta que usted
  extiende la estancia.
- **Los paneles y los informes cuentan las noches de habitación registradas**, así que la
  ocupación y los ingresos por habitaciones de hoy aparecen cuando se ha ejecutado la auditoría.

## Solución de problemas

**"Night audit is blocked: …"** Una comprobación que bloquea todavía tiene
elementos. Resuélvalos, o autorice una excepción para cada uno con un motivo bajo
su lista.

**"Business date … is already ahead of today."** La auditoría de hoy ya
se ha ejecutado. La siguiente se puede ejecutar cuando empiece el siguiente día del calendario.

**"Night audit can only close the current business date."** La auditoría
cierra una fecha cada vez: la que aparece en la tarjeta.

**La ejecución automática no avanzó la fecha.** Revise el motivo en
**Ejecuciones de la auditoría nocturna**. Lo normal es que el alojamiento esté
configurado en **Detener y avisar** y algo estuviera bloqueando: revise el aviso,
resuelva los elementos y cierre el día a mano. Si las ejecuciones automáticas
están desactivadas, nada se ejecuta solo.

## Para desarrolladores

Los agentes ejecutan la misma lista de comprobaciones con la herramienta MCP
`night_audit_precheck` y la auditoría con `run_night_audit` (los bloqueos se
autorizan con una nota): consulte [MCP tools](/mcp-tools#night-audit). Los
endpoints de la página (`kamra.night_audit.eod_session`, `eod_progress` para las
notas, `eod_acknowledge`, `eod_mark_no_show`, `eod_overview`, `night_audit_pack`,
`night_audit_history`, `night_audit_schedule`) están en la
[API reference](/api-reference#night-audit-end-of-day-checklist-audit-pack).
