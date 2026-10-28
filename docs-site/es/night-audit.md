# Auditoría nocturna: cierre del día

La auditoría nocturna cierra la fecha operativa del hotel. Registra los cargos
de habitación de la noche para cada huésped alojado, aplica la política de no presentados, guarda
un paquete de auditoría con los informes del día y avanza la fecha operativa un
día. Puede ejecutarla a mano desde la lista de comprobaciones del **Cierre del día**, y se ejecuta
sola a las 03:00. Pueden ejecutarla los usuarios de Recepción, Finanzas, el Auditor nocturno y el
Administrador del hotel.

![El asistente de Cierre del día: los doce pasos a la izquierda con su estado, y el paso Preparar con la fecha operativa, la fecha del servidor, la hora del alojamiento y cada comprobación previa con su gravedad](/img/night-audit/wizard.png)

## Antes de empezar

1. **Revise las reglas de no presentados.** **Configuración → Recepción → Auditoría nocturna y
   no presentados** decide cuándo una llegada que nunca se produjo pasa a ser No presentado;
   el cargo está en **Configuración → Políticas de estancia → Cargo por no presentación**. Consulte
   [Configuración](#configuracion).
2. **Decida qué bloquea la auditoría.** **Configuración → Recepción → Lista de comprobaciones de
   auditoría nocturna** define qué comprobaciones detienen una ejecución manual, el umbral de
   saldo elevado y qué hace la ejecución de las 03:00 cuando algo sigue pendiente.
3. **Asigne el rol de Auditor nocturno a su auditor nocturno** si no tiene
   Recepción ni Finanzas: **Configuración → Personal y acceso**. Con ese rol puede ejecutar el Cierre del
   día y confirmar bloqueos, registrar entradas y salidas de huéspedes, cerrar sesiones
   de caja y ver folios, el resumen por cajero y los informes.

## Abrir el cierre del día

Abra **Finanzas → Cierre del día** (también en **Recepción**, o escriba *night
audit*, *end of day* o *EOD* en la búsqueda, Ctrl/Cmd+K). **Gestionar cierre del
día** muestra una tarjeta por alojamiento: su fecha operativa y su hora local,
las llegadas y salidas pendientes, las cajas abiertas, las cuentas abiertas del punto de venta, y
**Listo** o el número de bloqueos.

![Gestionar cierre del día: una tarjeta por alojamiento con las llegadas y salidas pendientes, las cajas abiertas y las cuentas abiertas del punto de venta, y el historial de auditoría debajo](/img/night-audit/manage.png)

Pulse **Administrar** en el alojamiento (muestra **Continuar** si ya
empezó esta noche). Su progreso se guarda sobre la marcha, así que puede salir y
volver al mismo paso.

## Completar la lista de comprobaciones

Los pasos aparecen a la izquierda, cada uno con un estado (pendiente, hecho,
bloqueado, omitido) y el número de elementos encontrados. El paso 1 muestra la
fecha operativa, la fecha del servidor y la hora del alojamiento una junto a otra, y
cada comprobación con su gravedad. Pulse **Iniciar** y después **Continuar** al terminar
cada paso.

| # | Paso | Qué hace usted |
| --- | --- | --- |
| 1 | Preparar cierre del día | Lea las comprobaciones previas. |
| 2 | Llegadas pendientes de registrar | **Registrar entrada**, **Marcar como no presentado** o Continuar. Cada fila muestra lo que hará con ella la política de no presentados. |
| 3 | Salidas pendientes de registrar | **Registrar salida**, **Extender estancia** o **Registrar rápidamente la salida** de todas las salidas sin saldo a la vez. Bloquea por defecto. |
| 4 | Folios abiertos y saldos elevados | Folios de huéspedes alojados que deben más del umbral, saldos de estancias ya terminadas, empresas por encima de su límite de crédito. |
| 5 | Puntos de venta y cargos a habitaciones | Cuentas de restaurante abiertas (bloquean por defecto) y cada cuenta de punto de venta cargada hoy a una habitación, para que un cargo a la habitación equivocada se vea. |
| 6 | Verificación de tarifas | Noches de habitación registradas con una tarifa distinta de la reservada, y habitaciones con tarifa cero o de cortesía. |
| 7 | Estado de la habitación | Habitaciones en las que recepción y el tablero de habitaciones no coinciden, y habitaciones libres. |
| 8 | Cierre de caja | Cuente cada caja abierta y pulse **Cerrar sesión**. Bloquea por defecto. |
| 9 | Notas | Notas para el gerente (tiempo, incidentes). Se imprimen en el paquete de auditoría. |
| 10 | Registrar los cargos de habitación e impuestos y avanzar la fecha operativa | Ejecuta la auditoría. |
| 11 | Imprimir informes finales | El paquete de auditoría. |
| 12 | Finalizar | Resumen. |

![Paso 2, Llegadas pendientes de registrar: cada llegada con su tipo de habitación, habitación, número de personas y origen bajo el nombre del huésped, la fecha de llegada y las noches, la tarifa, lo que hará la política de no presentados, y los botones Registrar entrada y Marcar como no presentado](/img/night-audit/arrivals.png)

**Marcar como no presentado** aplica la política del alojamiento de inmediato: la estancia
pasa a No presentado y el cargo se registra en la fecha operativa, o se exonera
si es una reserva de una OTA. Solo se puede marcar una llegada Confirmada prevista para la
fecha operativa o antes.

## Resolver o confirmar un bloqueo

Tres comprobaciones bloquean la auditoría por defecto: cajas abiertas, cuentas de
restaurante abiertas y huéspedes con salida prevista que siguen alojados. Un paso bloqueado muestra
una señal roja y no tiene botón **Continuar**. Resuélvalo (registre la salida del huésped,
liquide la cuenta del restaurante, cierre la caja) o confírmelo:

1. Escriba el motivo en el cuadro bajo la lista, por ejemplo *"Salidas
   tardías aprobadas por el gerente de turno"*.
2. Pulse **Confirmar revisión**.

![Paso 3, Salidas pendientes de registrar: dos huéspedes con salida prevista que siguen alojados, el botón para registrar rápidamente la salida y el cuadro para confirmar el bloqueo con un motivo](/img/night-audit/departures.png)

Su nombre, la hora y el motivo se guardan en la auditoría, se imprimen en el
paquete y quedan en el Registro de actividad. Las comprobaciones de advertencia nunca bloquean: se
muestran y usted pulsa **Continuar**.

## Cerrar las cajas

El paso 8 muestra cada caja que sigue abierta en la fecha operativa con su fondo,
sus transacciones y el efectivo cobrado. Escriba el efectivo contado en una fila y pulse
**Cerrar sesión**; **Esperado vs contado** debajo muestra la variación
de cada sesión.

![Paso 8, Cierre de caja: una caja abierta con su fondo y el efectivo cobrado, el cuadro del efectivo contado y Cerrar sesión](/img/night-audit/cashier-closure.png)

Un cajero también puede cerrar su propia caja en **Finanzas → Mi caja**: consulte
[Facturación](/es/billing#contar-el-efectivo-y-cerrar-la-caja).

## Ejecutar la auditoría

1. Vaya al paso 10, **Registrar los cargos de habitación e impuestos y avanzar la fecha operativa**. Si un
   paso que bloquea sigue pendiente, el paso lo nombra y el botón sigue
   desactivado.
2. Pulse **Registrar los cargos de habitación e impuestos y avanzar la fecha operativa**.
3. Kamra registra la noche y muestra lo que ha hecho: las noches de habitación registradas y
   su importe, los no presentados y la nueva fecha operativa.

![Ejecución del Cierre del día: confirmación de los bloqueos, cierre de la caja, una nota y registro de los cargos de habitación e impuestos](/img/night-audit/run-end-of-day.gif)

No se puede deshacer. La auditoría solo cierra la fecha operativa actual del alojamiento,
y solo cuando ese día ya ha empezado en el servidor: no
puede ejecutar esta noche la auditoría de mañana.

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

## Imprimir el paquete de auditoría

El paso 11 muestra los informes finales a la izquierda. Elija uno para leerlo y luego
**Imprimir** o **Descargar PDF** (elija *Guardar como PDF* en el cuadro de impresión);
**Imprimir todo** imprime el paquete completo en A4:

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
- Comprobaciones previas e incidencias, con cada confirmación

![Los informes finales del paquete de auditoría de una fecha operativa cerrada](/img/night-audit/audit-pack.png)

El paquete se guarda en la auditoría cuando se ejecuta, así que reimprimir una noche pasada
da exactamente lo que se imprimió esa noche. Encuentre las auditorías pasadas en **Historial
de auditoría** al pie de **Gestionar cierre del día**: busque por fecha y pulse
**Imprimir** en la columna **Paquete de auditoría**. Las ejecuciones automáticas (03:00) aparecen
ahí con el origen **Programado**. Si falta un paquete, pulse
**Reconstruir paquete**: vuelve a crear los informes imprimibles sin registrar
cargos otra vez.

En la tarjeta del alojamiento, **Imprimir paquete** abre el paquete de la última ejecución, si
se guardó uno.

![Historial de auditoría: cada fecha operativa cerrada con su estado, origen, noches de habitación, importe registrado, no presentados, incidencias y un enlace a su paquete de auditoría](/img/night-audit/history.png)

## La ejecución de las 03:00

La hora es configurable por alojamiento en **Configuración → Recepción →
Auditoría nocturna automática**: **Ejecutar la auditoría nocturna
automáticamente** (activado por defecto), **Ejecutar a las** (03:00 por
defecto, hora local según la **Zona horaria** del alojamiento) y **Esperar
después de esa hora** (0 a 120 minutos). Kamra comprueba cada 15 minutos y
cierra un día por comprobación. Cada ejecución, automática o manual, aparece
en **Ejecuciones de la auditoría nocturna** en esa misma página, con su
resultado (Cerrado, Retenido, Omitido o Fallido) y el motivo; un fallo avisa
a los usuarios Hotel Admin. Un día retenido, omitido o fallido se intenta una
vez al día. Con la ejecución automática desactivada, solo el personal cierra
el día.

Cada noche a las 03:00, Kamra ejecuta la auditoría de cada alojamiento cuya
fecha operativa va por detrás de la fecha del calendario. Hace el mismo trabajo
que la ejecución manual. Si una comprobación que bloquea sigue pendiente, sigue lo indicado en
**Acción de la auditoría automática de las 03:00 si hay bloqueos**:

- **Ejecutar y registrar incidencias** (por defecto): la fecha avanza y los elementos
  pendientes se registran como incidencias en el paquete.
- **Detener y avisar**: la fecha operativa no cambia, y los usuarios Administrador del hotel
  y Finanzas reciben una notificación en la aplicación y un correo electrónico. Gestionar
  cierre del día muestra **03:00 en espera**: resuelva los bloqueos y pulse **Ejecutar cierre del
  día**, y luego imprima el paquete.

Si alguien ya cerró el día a mano, la ejecución de las 03:00 lo omite.

Si se saltaron algunos días (por ejemplo, porque el servidor estuvo caído), la ejecución de las 03:00
los cierra uno a uno, del más antiguo al más reciente, hasta tres días. Un alojamiento con más
de tres días de retraso no se cierra automáticamente: el Administrador del hotel y
Finanzas reciben un aviso, para que alguien revise las estancias en curso y las llegadas
antes de que se registren semanas de noches de habitación y cargos por no presentación. Cierre esos días
desde el Cierre del día.

### Si la fecha operativa parece atascada

Una auditoría completada para la fecha operativa abierta sin que la fecha haya avanzado
(tras una restauración o un cambio de operaciones) muestra **Fecha sin actualizar**. Pulse **Avanzar
la fecha operativa**: Kamra avanza la fecha operativa sin volver a registrar noches de
habitación. No puede deshacer una auditoría nocturna completada. La ejecución de las 03:00
hace lo mismo sola cuando encuentra una fecha atascada, y después cierra el día
que realmente toca.

## Configuración

![Configuración → Recepción → Lista de comprobaciones de auditoría nocturna](/img/night-audit/settings.png)

| Opción | Dónde | Valor por defecto | Qué hace |
| --- | --- | --- | --- |
| Las cajas abiertas bloquean la auditoría | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | Activado | Desactivado, muestra las sesiones de caja abiertas como advertencia. |
| Las cuentas de restaurante abiertas bloquean la auditoría | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | Activado | Desactivado, las muestra como advertencia. |
| Las salidas pendientes de registrar bloquean la auditoría | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | Activado | Desactivado, las muestra como advertencia. |
| Marcar los folios de huéspedes alojados cuyo saldo supere | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | 50000 | 0 desactiva la comprobación de saldo elevado. |
| Tolerancia de diferencia de tarifa | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | 1 | Cuánto (en unidades de moneda) puede alejarse una noche registrada de la tarifa reservada antes de aparecer en la lista. |
| Acción de la auditoría automática de las 03:00 si hay bloqueos | Configuración → Recepción → Lista de comprobaciones de auditoría nocturna | Ejecutar y registrar incidencias | O **Detener y avisar**. |
| Marcar huéspedes no presentados | Configuración → Recepción → Auditoría nocturna y no presentados | En la auditoría de la fecha de llegada | **Un día después** mantiene la llegada como prevista hasta la auditoría del día siguiente. |
| Mantener las reservas de llegada tardía hasta la próxima auditoría | Configuración → Recepción → Auditoría nocturna y no presentados | Activado | Una llegada prevista para el día que se cierra sigue como prevista si está marcada como **Llegada tardía** o si su hora estimada de llegada es posterior al momento en que se ejecuta la auditoría. Una hora estimada anterior a las 06:00 cuenta como después de medianoche. |
| No aplicar cargos por no presentación a reservas de agencias en línea | Configuración → Recepción → Auditoría nocturna y no presentados | Activado | Las reservas de OTA se siguen marcando como No presentado, pero no se registra ningún cargo. |
| Liberar las reservas de llegada sin garantía a las | Configuración → Recepción → Auditoría nocturna y no presentados | En blanco (desactivado) | A esta hora, las llegadas de hoy sin anticipo, pago ni depósito, y que no vienen de una OTA ni de una empresa, se cancelan sin cargo. |
| Cargo por no presentación | Configuración → Políticas de estancia → Cancelación y no presentación | Primera noche | **Ninguno**, **Primera noche** o **Toda la estancia**. |

## Conviene saber

- **Cualquiera que pueda ejecutar el Cierre del día puede confirmar un bloqueo.** La comprobación
  se hace por rol (Recepción, Finanzas, Auditor nocturno, Administrador del hotel), y
  se registran el nombre y el motivo.
- **Las noches de habitación se cobran con la tarifa confirmada al reservar.** Un cambio de tarifa
  posterior o una temporada nueva nunca cambia una estancia confirmada.
- **La auditoría nunca registra una noche después de la fecha de salida.** Un huésped que
  sigue alojado después de su fecha de salida no recibe cargo de noche hasta que usted
  extiende la estancia.
- **Los paneles y los informes cuentan las noches de habitación registradas**, así que la
  ocupación y los ingresos por habitaciones de hoy aparecen cuando se ha ejecutado la auditoría.

## Solución de problemas

**"Night audit is blocked: …"** Una comprobación que bloquea todavía tiene elementos. Resuélvalos,
o confirme cada uno con un motivo en su paso.

**"Business date … is already ahead of today."** La auditoría de hoy ya
se ha ejecutado. La siguiente se puede ejecutar cuando empiece el siguiente día del calendario.

**"Night audit can only close the current business date."** La auditoría
cierra una fecha cada vez: la que aparece en la tarjeta.

**La ejecución de las 03:00 no avanzó la fecha.** El alojamiento está configurado en **Detener y
avisar** y algo estaba bloqueando. Revise el aviso, resuelva los elementos y
ejecute el Cierre del día a mano.

## Para desarrolladores

Los agentes ejecutan la misma lista de comprobaciones con la herramienta MCP `night_audit_precheck` y
la auditoría con `run_night_audit` (los bloqueos se confirman con una nota):
consulte [MCP tools](/mcp-tools#night-audit). Los endpoints del asistente
(`kamra.night_audit.eod_session`, `eod_progress`, `eod_acknowledge`,
`eod_mark_no_show`, `eod_overview`, `night_audit_pack`,
`night_audit_history`) están en la
[API reference](/api-reference#night-audit-end-of-day-checklist-audit-pack).
