# Informes y paneles

Los informes de Kamra responden a las preguntas de cada día: qué ocupación
tuvimos, cuánto ingresamos, qué se cobró, si vamos según el presupuesto, de
dónde viene el negocio y si las solicitudes de huéspedes se atienden a
tiempo. **Informes** (en los menús de Recepción, Ingresos, Operaciones y
Finanzas) reúne todos los informes en un solo lugar y muestra solo los que
su rol puede abrir. Las cifras clave del día están en
[Hoy](/es/front-desk); el Responsable de ingresos, Finanzas y el
Administrador del hotel también tienen el panel de ingresos y las vistas de
cartera.

![Informes: todos los informes en un solo lugar, agrupados en Diario, Ingresos, Finanzas y Operaciones](/img/reports/hub.png)

![El Resumen gerencial: ocupación, ADR, RevPAR, RevPAX y los ingresos del día, los últimos 14 días, el movimiento de hoy, los cobros y los próximos 7 días](/img/reports/manager-flash.png)

## Antes de empezar

- **Ejecute la auditoría nocturna.** La ocupación, el ADR, el RevPAR y los
  ingresos por habitaciones cuentan las noches de habitación registradas en
  los folios, y la [auditoría nocturna](/es/night-audit) es la que las
  registra. Hasta que se ejecute la auditoría de esta noche, hoy no muestra
  ingresos por habitaciones.
- **Defina sus metas mensuales** si quiere ver el presupuesto frente a los
  resultados: consulte
  [Seguir el mes frente al presupuesto](#seguir-el-mes-frente-al-presupuesto).
- El dinero se muestra en la moneda del alojamiento y las columnas de
  impuestos siguen el paquete de su país
  ([Configuración por país](/country-setup)).

## Ver el día de un vistazo

Las cifras principales de hoy, los cobros, el saldo pendiente y el ADR, el
RevPAR y la ocupación acumulados del mes están en **Recepción → Hoy**; cada
recuadro abre la lista o el informe que hay detrás. Para la vista del
departamento, abra **Ingresos → Panel de ingresos** (también en
**Informes**). **Este alojamiento** muestra:

- **Ocupación** de hoy, **ADR** y **RevPAR** (acumulado del mes),
  **Ingresos** y **Cobros** de hoy, y **Saldo pendiente** (lo que se debe
  en folios abiertos);
- **Estadísticas (acumulado del mes)**: ocupación, ingresos, ADR, RevPAR y
  habitaciones vendidas;
- **Limpieza**: habitaciones limpias, sucias, inspeccionadas y fuera de
  servicio, tareas abiertas y vencidas;
- **Finanzas**: cobrado hoy, saldo pendiente y folios abiertos.

![El panel del alojamiento: recuadros principales, estadísticas acumuladas del mes y los paneles de Limpieza y Finanzas](/img/reports/dashboard.png)

**Todos los alojamientos** (aparece cuando tiene más de un alojamiento,
para Finanzas, Responsable de ingresos y Administrador del hotel) suma las
mismas cifras de toda la cartera, con una tabla **Por alojamiento**:
ocupación, llegadas, salidas, alojados, ingresos, cobrado y saldo pendiente
de cada hotel.

![El panel de cartera: alojamientos, ocupación, llegadas, alojados, ingresos y cobros de tres alojamientos, y la tabla Por alojamiento](/img/reports/portfolio.png)

## Crear un informe personalizado

Abra **Informes → Informes personalizados**. Un informe se crea a partir de
un **conjunto de datos**: llegadas, salidas, alojados, no presentaciones y
cancelaciones, ocupación por día, cargos de folio, pagos, anulaciones,
aportación, tareas de limpieza, estado de las habitaciones, objetos
perdidos y pedidos del punto de venta. Solo ve los conjuntos de datos que
su rol puede abrir (consulte
[Informes que ve cada rol](#informes-que-ve-cada-rol)).

1. Abra **Informe nuevo**, elija un conjunto de datos, elija las columnas y
   los filtros opcionales, defina el intervalo de fechas (hasta 92 días) y
   pulse **Vista previa**.
2. Pulse **Guardar** para conservar la definición en **Mis informes**.
   Finanzas y el Administrador del hotel pueden **compartir** un informe con
   el alojamiento y programar un envío por correo **Diario** o **Semanal**
   (destinatarios y hora).
3. **CSV**, **Imprimir** y **Correo electrónico** funcionan con informes
   nuevos o guardados. Los envíos programados adjuntan el día de ayer (o
   los últimos 7 días si es semanal) en CSV.

### Agrupar y ver el detalle

Elija una columna en **Agrupar por** y pulse **Vista previa**: obtiene una
fila por valor, con las columnas numéricas sumadas. En las tareas de
limpieza, **Minutos de limpieza** es la media de las limpiezas que se
cronometraron, no una suma.

Haga clic en una fila de grupo para ver las filas que contiene. **Volver al
resumen** vuelve a la vista agrupada. La agrupación se guarda con el
informe y se usa en sus correos.

## Enviar un paquete por departamento

Abra **Informes → Paquetes por departamento**. Un paquete reúne varios
informes agrupados en una sola página:

| Paquete | Qué contiene |
|---|---|
| **Paquete de Recepción** | Ocupación por día, llegadas por origen, alojados por tipo de habitación, no presentaciones y cancelaciones |
| **Paquete de Limpieza** | Estado actual de las habitaciones, tareas por tipo y por camarera con los minutos medios de limpieza, objetos perdidos |
| **Paquete de Alimentos y bebidas** | Ventas y comensales por punto de venta, pedidos por estado |
| **Paquete del Gerente del hotel** | Ocupación e ingresos, ingresos por origen, cobros por forma de pago, cargos por tipo, anulaciones y bonificaciones |

1. Defina las fechas **De** y **A**.
2. Pulse **Abrir** para obtener una página imprimible, o **Enviar ahora** y
   escriba las direcciones.
3. Finanzas y el Administrador del hotel pueden pulsar **Enviar cada
   lunes** para enviarlo a las 07:00 cada lunes con los últimos 7 días. La
   programación aparece en **Mis informes**, donde puede abrirla, enviarla
   o eliminarla.

Un paquete solo contiene las partes que su rol puede abrir. El Paquete del
Gerente del hotel de un auditor nocturno tiene ocupación, cobros y cargos,
pero no anulaciones. La página sigue el idioma en que usa Kamra, y el árabe
se lee de derecha a izquierda.

## Informes que ve cada rol

Cada informe comprueba sus roles, igual que su pantalla, y el Agente Kamra
y Claude (MCP) siguen las mismas reglas: nunca muestran a nadie un informe
que su rol no puede abrir.

| Rol | Informes fijos | Conjuntos de datos de informes personalizados | Paquetes |
|---|---|---|---|
| Recepción | Resumen gerencial, informe de turno, SLA, panel de Alimentos y bebidas, mermas, registros de banquetes | Llegadas, salidas, alojados, no presentaciones, ocupación, tareas de limpieza, estado de las habitaciones, objetos perdidos, pedidos del punto de venta | Los cuatro |
| Auditor nocturno | Resumen gerencial, informe de turno | Llegadas, salidas, alojados, no presentaciones, ocupación, cargos de folio, pagos | Recepción, Gerente del hotel |
| Finanzas | Resumen gerencial, informe de turno, anulaciones, panel de Alimentos y bebidas, mermas, registros de banquetes | Conjuntos de datos de recepción, cargos de folio, pagos, anulaciones, aportación, pedidos del punto de venta | Recepción, Alimentos y bebidas, Gerente del hotel |
| Limpieza, Supervisor de limpieza | Ninguno | Tareas de limpieza, estado de las habitaciones, objetos perdidos | Limpieza |

El Administrador del hotel lo ve todo. Un conjunto de datos también
necesita que su módulo esté activado en el alojamiento
(**Configuración → Módulos**).

## Leer el resumen gerencial

Abra **Informes → Resumen gerencial**. El **Resumen gerencial** es el
informe de la mañana para una fecha. Elíjala en el cuadro de fecha de la
derecha. Para ver un intervalo, ponga en la fecha de la izquierda un día
anterior (hasta 92 días): los recuadros, la tabla diaria, el movimiento y
los cobros pasan a cubrir todo el intervalo, e **Ingresos (día)** pasa a
ser **Ingresos**. El acumulado del mes y los próximos 7 días no cambian.

- **Ocupación**, **ADR**, **RevPAR**, **RevPAX** e **Ingresos (día)**
  desglosados en habitación, Alimentos y bebidas y otros. RevPAX es el
  gasto total del huésped (habitación, Alimentos y bebidas, experiencias,
  extras) por huésped alojado.
- **Últimos 14 días**: % de ocupación, ADR, RevPAR e ingresos por día, con
  el total acumulado del mes.
- **Movimiento**: llegadas, salidas, alojados y no presentaciones.
- **Cobros**: lo que se cobró ese día, por forma de pago.
- **Próximos 7 días**: ocupación reservada para la próxima semana.

Pulse **Imprimir** para una copia en papel. **Informe de turno de cajero**
y **Libros contables**, arriba, abren las pantallas de caja y de libros
contables (consulte
[Facturación](/es/billing#contar-el-efectivo-y-cerrar-la-caja)). Los usuarios
de Finanzas y Administrador del hotel también tienen **Anulaciones y
bonificaciones**, la lista de cada anulación, bonificación y factura
cancelada (consulte
[Facturación](/es/billing#revisar-anulaciones-y-bonificaciones)).

El mismo resumen es el primer informe del
[paquete de auditoría](/es/night-audit#imprimir-el-paquete-de-auditoria) de
cada noche.

## Seguir el mes frente al presupuesto

Abra **Informes → Informes de ingresos**. **Presupuesto frente a
resultados** compara el acumulado del mes con sus metas: **Ingresos por
habitaciones**, **Ocupación (%)**, **ADR / ARR** y **RevPAR**, cada uno
con la desviación y cuánto de la meta ha alcanzado.

"Resultados" cuenta las noches de habitación registradas en los folios, y
el Cierre del día registra cada noche, así que esta noche cuenta después de
la auditoría de esta noche. La ocupación y el RevPAR se calculan sobre los
días del mes transcurridos hasta la fecha operativa, no sobre el mes
completo, para que se comparen de forma justa con una meta mensual. La nota
bajo la tabla indica cuántas noches de habitación están registradas y sobre
cuántos días. Si hay noches vendidas que todavía esperan el Cierre del día,
indica cuántas, en ámbar.

![Presupuesto frente a resultados del mes: acumulado real del mes, meta, desviación y grado de cumplimiento para ingresos por habitaciones, ocupación, ADR y RevPAR, con la nota sobre noches de habitación registradas y pendientes debajo](/img/reports/budget-vs-actual.png)

1. Use las flechas para elegir el mes.
2. Pulse **Definir metas** (o **Editar metas** si el mes ya las tiene).
3. Escriba las metas en la columna **Meta** y pulse **Guardar metas**.

![Edición de la meta de ADR del mes y guardado](/img/reports/set-targets.gif)

Los usuarios con Responsable de ingresos, Finanzas y Administrador del
hotel pueden guardar metas.

## Ver de dónde viene el negocio

**Análisis de aportación**, en **Informes → Informes de ingresos**, agrupa
las reservas que llegan en un intervalo de fechas **Por origen**, **Por
empresa** o **Por agencia de viajes**: reservas, noches de habitación,
ingresos y porcentaje del total.

![Análisis de aportación por origen: reservas, noches de habitación, ingresos y porcentaje para Manual, Teléfono, Agente de IA, Sitio web, OTA y Sin reserva previa](/img/reports/contribution.png)

Cuenta las reservas confirmadas, alojadas y con salida registrada por su
fecha de llegada, con el total de la reserva impuestos incluidos. Las
reservas sin origen, empresa ni agencia aparecen como **Directo**.

## Revisar los tiempos de respuesta a los huéspedes

Abra **Informes → Informe de SLA**. Para las solicitudes de huéspedes
creadas en el intervalo de fechas (por defecto, los últimos 30 días)
muestra el número de **Solicitudes**, cuántas están en **Resuelto**, el
**Porcentaje de incumplimiento** y el tiempo medio de resolución; después lo
mismo por categoría y por prioridad, y **Fuera de plazo ahora**: las
solicitudes abiertas que ya han pasado su hora límite, de la más antigua a
la más reciente.

![El informe de SLA de Operaciones: solicitudes, resueltas, porcentaje de incumplimiento y tiempo medio de resolución, el desglose por categoría y prioridad, y la cola de solicitudes fuera de plazo](/img/reports/sla.png)

Una solicitud cuenta como incumplida cuando se resolvió después de su hora
límite o sigue abierta pasada esa hora. Las horas límite vienen de
**Configuración → Operaciones**; consulte [Operaciones](/es/operations).

## Enviar las facturas a su contable

Abra **Finanzas → Exportación contable** (Finanzas y Administrador del
hotel).

1. Elija el intervalo de fechas. Por defecto son los últimos 30 días.
2. Elija el formato: **CSV genérico**, **Tally**, **Zoho Books** o
   **ERPNext**.
3. Revise la vista previa y pulse **Descargar CSV**.

![Exportación contable en CSV genérico: el intervalo de fechas, el formato, la línea de totales y una fila de vista previa por código de servicio con el artículo, SAC/HSN, % de GST, base imponible y el desglose de CGST y SGST](/img/reports/accounting-export.png)

La exportación incluye cada factura cerrada en el intervalo: número, fecha,
cliente y su identificación fiscal, lugar de prestación, base imponible, el
desglose de impuestos que usa el paquete de su país (CGST y SGST en la
India, una sola columna de impuesto en los demás) y el total. La
disposición de las filas depende del formato:

- **CSV genérico** y **Zoho Books** dan una fila por código de servicio y
  tipo de impuesto en cada factura, así que una cuenta con una habitación,
  una cena y lavandería tiene una fila para cada una. CSV genérico añade
  las columnas **Artículo**, **SAC/HSN**, el % de impuesto, **Total de
  línea** y **Total de factura**; Zoho Books usa sus propias columnas
  **Nombre del artículo**, **HSN/SAC**, **Impuesto del artículo (%)** y
  **Total del artículo**.
- **Tally** y **ERPNext** dan una fila por factura.

La vista previa muestra las 12 primeras filas; la descarga las incluye
todas.

## Conviene saber

- **Los informes de un solo día también aceptan un intervalo.** El panel
  de Alimentos y bebidas, el informe de turno de cajero, el historial del
  folio, las estadísticas de habitaciones y el embudo de banquetes tienen
  fecha **De** y **A**. Deje la fecha final como está para un solo día.
- **Los paneles y el resumen usan la fecha del calendario**, no la fecha
  operativa del hotel. Entre la medianoche y la auditoría nocturna, "hoy"
  en el panel ya es el día nuevo.
- **La ocupación cuenta las habitaciones con una noche de habitación
  registrada**, no las habitaciones con un huésped dentro.
- **Los ingresos de aportación son el valor de la reserva**, no lo
  registrado en el folio; use el presupuesto frente a resultados o el
  resumen para los ingresos registrados.
- **El paquete de auditoría conserva los informes de cada noche tal como
  eran**, así que una reimpresión de un día pasado coincide con el
  original.

## Solución de problemas

**La ocupación y los ingresos por habitaciones muestran 0 para hoy.** La
auditoría nocturna de esta noche aún no se ha ejecutado. Los días
anteriores están en la tabla de 14 días del resumen.

**Todos los alojamientos no aparece en el panel.** Solo tiene acceso a un
alojamiento.

**La exportación contable está vacía.** Solo incluye facturas cerradas.
Los folios todavía abiertos (huéspedes alojados) no aparecen.

## Para desarrolladores

Las cifras vienen de `kamra.dashboards.property_dashboard` y
`portfolio_dashboard`, y de `kamra.reports.manager_flash`,
`budget_vs_actual`, `save_budget`, `contribution` y `sla_report`; la
exportación es `kamra.accounting.export_invoices`. Finanzas y el
Administrador del hotel también pueden obtener cada anulación, bonificación
y cancelación de factura con `kamra.reports.void_allowance_report`, el
endpoint de la pantalla **Anulaciones y bonificaciones**. Consulte
[Dashboards](/api-reference#dashboards) y [Reports](/api-reference#reports)
en la referencia de la API. Los agentes obtienen la situación diaria con las
[herramientas MCP](/mcp-tools#briefings) `owner_briefing` y
`position_briefing`.
