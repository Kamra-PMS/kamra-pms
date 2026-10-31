# Facturación: folios, pagos y la caja

Cada estancia tiene un folio: la cuenta abierta donde se cargan las noches
de habitación, las cuentas del restaurante y los extras, y donde se
registran los pagos. Esta página trata del folio, la caja del cajero, los
depósitos, las facturas, las cuentas de empresa y los libros contables.
Aquí trabaja el personal de Recepción y de Finanzas; las notas de crédito,
los pagos de empresas y la exportación contable son para Finanzas y el
Administrador del hotel.

![Un folio de huésped: la barra de acciones arriba, la cuenta provisional con cada cargo, su impuesto y su total, un resumen por tipo de cargo y el resumen de impuestos](/img/billing/folio.png)

Los importes, los tipos de impuesto y los modos de pago de esta página
vienen del hotel de ejemplo en la India. Los suyos vienen de su paquete de
país: consulte [Country setup](/country-setup).

## Antes de empezar

1. **Abra su caja.** Los pagos, los reembolsos y las facturas se rechazan
   hasta que tenga una sesión de caja abierta: consulte [Abrir y cerrar su caja](#abrir-y-cerrar-su-caja).
2. **Decida si usa un PIN de caja.** **Configuración → Finanzas → Controles de caja →
   Exigir PIN de caja para operaciones de dinero**. Si está activado, cada persona define un
   PIN la primera vez que cobra dinero, y las operaciones de dinero lo vuelven a pedir
   cuando termina el tiempo de desbloqueo. Está desactivado por defecto.
3. **Conecte una pasarela de pago** si quiere enviar enlaces de pago:
   **Configuración → Pagos**. Las pasarelas disponibles dependen de su paquete
   de país.
4. **Configure la facturación a empresas** si tiene empresas con crédito:
   **Configuración → Finanzas → Facturación a empresas** (consulte
   [Folios de empresa](#facturar-a-una-empresa)).

## Buscar un folio

Abra **Finanzas → Facturación**. La lista **Folios** muestra todos los folios del
alojamiento, del más reciente al más antiguo, con su estado, número de factura, total, importe pagado y
saldo. Pulse una fila para abrir el folio. También puede llegar al folio de una estancia
desde la reserva.

**Finanzas → Historial del folio** muestra las cuentas y facturas cerradas. Busque por
huésped, factura o folio, filtre por estado, o indique **Cerrado desde** y
**A** para ver las cuentas cerradas en un rango de fechas.

![La pantalla de Facturación: accesos directos a Cierre del día y Mi caja, y la lista de folios con sus saldos](/img/billing/billing-list.png)

El folio se abre solo al registrar la entrada. Hasta que se liquida, es una
**Cuenta provisional** sin número de factura.

## Registrar un cargo

1. Abra el folio y baje hasta **Registrar un cargo**.
2. Elija el tipo de cargo (**Alimentos y bebidas**, **Minibar**, **Lavandería**,
   **Spa**, **Entrada anticipada**, **Salida tardía**, **Cargo por mascota**,
   **Descuento** o **Varios**).
3. Escriba una descripción y el importe sin impuestos.
4. Elija el tipo de impuesto. Para cargos de comida, bebida y minibar no hay
   elección: el formulario muestra el tipo de alimentos y bebidas de su paquete de país, por
   ejemplo **GST 5% (F&B rate)**. Marque **Alcohol** para las bebidas con
   alcohol; estas llevan el tipo que usted elija. El nombre del impuesto (GST, IVA…) depende de
   su paquete de país.
5. Pulse **Registrar**.

![Las tarjetas Registrar un cargo y Registrar un pago bajo la cuenta: un cargo de minibar muestra el tipo fijo de GST 5% para alimentos y bebidas, con la fila de bonificación debajo](/img/billing/post-charge.png)

Las noches de habitación, los planes de comidas y las tasas de alojamiento no se registran a mano: la
[auditoría nocturna](/es/night-audit) los registra cada noche. Las cuentas del restaurante
cargadas a una habitación llegan desde el [punto de venta](/es/fnb).

## Cobrar un pago

1. Abra el folio y baje hasta **Registrar un pago**.
2. Elija qué es el dinero:
   - **Pago**: a cuenta de la factura.
   - **Anticipo**: se cobra antes de la entrada o al registrarla. Paga la estancia.
   - **Depósito de garantía**: se retiene y es reembolsable, no es ingreso. Consulte
     [Depósitos de garantía](#cobrar-y-devolver-un-deposito-de-garantia).
3. Elija el modo (efectivo, tarjeta y los demás modos de su paquete de país).
   El importe se rellena con el saldo; cámbielo para un pago parcial.
4. Añada una referencia (comprobante de tarjeta, número de transferencia) si la tiene.
5. Pulse **Registrar**. El saldo al pie de la cuenta se actualiza.

![Registro de un pago UPI por el saldo de un folio, y el saldo que baja a cero](/img/billing/take-payment.gif)

Cada pago también entra en su sesión de caja, así que el
[informe de turno](#contar-el-efectivo-y-cerrar-la-caja) y los libros contables lo incluyen.

**Envíe un enlace de pago.** Cuando el folio tiene saldo y hay una
pasarela conectada, **Enlace de pago** en la barra de acciones crea un enlace
por el saldo y lo copia, listo para pegarlo al huésped (o a quien reservó,
si la reserva indica contactar a esa persona). Cuando el huésped paga, el
pago se registra solo en el folio.

**Reembolsar dinero.** En la salida no lo necesita: el paso **Pago** de la hoja de salida
calcula el reembolso, sugiere el modo por el que entró el dinero
y devuelve el depósito de garantía retenido con el reembolso propio del
depósito (consulte [Recepción](/es/front-desk)). Para cualquier otro reembolso, bajo la
lista de pagos, **Reembolsar dinero (devolución de depósito o cobro en exceso)** abre una
fila de reembolso: importe, modo y un motivo, y luego **Reembolso**. No puede reembolsar
más de lo cobrado en el folio, y un folio cerrado no admite
reembolsos. Cada reembolso queda en el registro de actividad con su nombre.

## Corregir un cargo

**Anular** elimina una línea errónea (importe equivocado, duplicado, huésped equivocado):

1. En la línea del cargo, pulse **Anular**.
2. Escriba el motivo. Es obligatorio y queda registrado.
3. Pulse **Confirmar anulación**.

![Anulación de un cargo de lavandería: el cuadro del motivo y el botón Confirmar anulación en la línea](/img/billing/void.png)

**Aplique una bonificación** cuando el cargo era correcto pero usted devuelve
dinero (compensación por un mal servicio, una reclamación): bajo **Registrar un cargo**, rellene la
fila **Aplicar una bonificación** con el importe, el tipo de impuesto del cargo que
compensa y un motivo (elija un código de motivo **Ajustar**, o escriba uno), y pulse
**Permitir**. La línea original sigue en la cuenta y la bonificación aparece como una
línea en negativo, así el historial queda claro.

### Cuando una bonificación necesita a un gerente

Active **Los ajustes necesitan aprobación de un gerente** (Configuración → Finanzas →
Controles de caja) y elija quién aprueba: **Administrador del hotel**, o
**Administrador del hotel o Finanzas**. **Solo ajustes por encima de** fija el
importe; 0 significa todas las bonificaciones. Un código de motivo marcado
**Requiere supervisor** (como el ajuste de cortesía) siempre pide aprobación,
aunque el ajuste esté desactivado. Un alojamiento nuevo empieza con la aprobación
activada (Administrador del hotel, todas las bonificaciones). Un alojamiento que ya
usa Kamra conserva su ajuste.

1. Recepción aplica la bonificación como siempre. Kamra indica **Enviado a un
   gerente** y la solicitud aparece bajo la fila de la bonificación. Todavía no se
   descuenta nada de la cuenta.
2. Un gerente en el mostrador pulsa **Un gerente aprueba ahora**, elige su nombre
   y escribe su propio PIN de cajero. O, más tarde, un gerente abre **Finanzas →
   Ajustes por aprobar**, escribe su PIN y pulsa **Aprobar**. El PIN se pide
   siempre, aunque el gerente sea quien tiene la sesión abierta y el ajuste de PIN
   de cajero esté desactivado.
3. Para denegarla, pulse **Rechazar** e indique el motivo. La solicitud se
   conserva con quién la rechazó y por qué.

La bonificación de un propio gerente se registra al momento, con él como
aprobador, en cuanto escribe su PIN. Los agentes de IA pueden pedir una
bonificación, nunca aprobarla. **Anulaciones y bonificaciones** muestra quién
aprobó cada bonificación y cada rechazo.

### El vale de bonificación

Cada bonificación que llega a una cuenta recibe un número de serie, como
`ALW-KDP-26-00012`: una serie por alojamiento, asignada cuando se registra la
bonificación (una solicitud en espera o rechazada no recibe ninguno) y nunca
reutilizada. `KDP` es el **Código corto** del alojamiento (**Configuración →
Alojamiento**, de 2 a 6 letras o dígitos, distinto en cada alojamiento).
Cambiarlo empieza una nueva serie de vales; los números ya asignados se quedan
como están. Las facturas mantienen su serie (numeración GST y ZATCA), sea cual
sea el código corto. El número aparece en la línea de la cuenta, en **Ajustes
por aprobar** (Aprobada) y en **Anulaciones y bonificaciones**.

Pulse el número, o **Imprimir vale**, para ver el vale imprimible: el
alojamiento, el número de serie, la fecha y la hora, el huésped, la habitación,
el folio, el importe y el impuesto que revierte, el código de motivo y la nota,
quién lo pidió y el gerente que lo aprobó (nombre, su cargo según **Personal y
acceso**, o su rol si no tiene cargo, "Aprobado con PIN" y cuándo), con líneas
de firma para el aprobador y para el huésped o quien lo pidió. El vale está en
`/kamra/allowance-voucher/<serial>`.

Las anulaciones solo funcionan en un folio abierto. Cuando el folio ya está facturado, use una
[nota de crédito](#anular-una-factura-o-emitir-una-nota-de-credito).

## Corregir noches cargadas

Para un hotel que descubre una tarifa equivocada después de cargar las noches.
Solo aparece cuando **Configuración → Políticas de estancia → Cambios de tarifa
durante la estancia** está en **Corregir tarifas de fechas pasadas**, y solo para
Finanzas y los Administradores del hotel.

1. Corrija primero la tarifa (tipo de habitación, temporada o plan tarifario).
2. Abra el folio del huésped. Bajo **Registrar un cargo**, **Corregir noches
   cargadas** muestra cada noche cargada con su tarifa cargada y la actual.
3. Escriba el motivo y su PIN de cajero, y pulse **Corregir**.

Kamra revierte cada noche y la vuelve a registrar con la tarifa actual. Las dos
líneas son líneas **Rate Adjustment** con fecha de hoy, con la noche en la
descripción, cada una con su propio impuesto. La línea original de la noche
sigue en el folio; no se edita nada ya registrado. La corrección queda en el
registro de actividad con el motivo, quién la aprobó y cada noche cambiada.

Cuando la tarifa de una estancia en curso cambia por cualquier otro motivo
(nuevas fechas, un cambio de habitación), las noches cargadas conservan su
tarifa o reciben un abono; consulte
[Cambiar la tarifa de un huésped alojado](/es/front-desk#cambiar-la-tarifa-de-un-huesped-alojado).

## Dividir o trasladar cargos a otro folio

Una estancia puede tener más de un folio: el folio de **Huésped**, un folio de **Empresa**,
folios de **Extra** y, para grupos, un folio de **Grupo**. Aparecen como
pestañas sobre la cuenta, cada una con su saldo.

1. Marque las líneas que quiere trasladar, o pulse **Mover** en una línea.
2. Para trasladar solo una parte de una línea, escriba un porcentaje (`30%`) o un
   importe sin impuestos (`1500`) en el cuadro junto a **solo trasladar**.
3. En **Enviar … a**, elija el folio, o **+ Nuevo folio de empresa** /
   **+ Nuevo folio de extras** para crear uno y trasladar las líneas a él.

![Una línea de spa seleccionada, 50% escrito en el cuadro de traslado parcial, y los botones para enviarla a un nuevo folio de empresa o de extras](/img/billing/move-charges.png)

**Dividir folio** en la barra de acciones añade un folio vacío a la estancia (primero un
folio de empresa, después folios de extras). Un folio de empresa o de extras vacío
se puede eliminar con la **×** de su pestaña.

## Dar a cada huésped de una habitación su propia cuenta

Cuando varios huéspedes comparten habitación y cada uno quiere su propia cuenta:

1. Añada a todos a la lista de huéspedes de la estancia (la ficha de registro).
2. En la cuenta del huésped principal, pulse **Cuenta por huésped**. Kamra abre
   una cuenta para cada uno de los demás huéspedes, con su nombre en la pestaña
   y en la factura.
3. En **Compartir cargos con las cuentas de los otros huéspedes**, mantenga el
   reparto a partes iguales o escriba un porcentaje para cada huésped, y pulse
   **Participación**. Se reparten las noches de habitación (habitación, plan de
   comidas, tasa); marque antes otras líneas para repartirlas también. Cada parte
   conserva el tipo de impuesto de su línea, y la cuenta del huésped principal se
   queda con el resto, redondeo incluido.
4. Pase los extras (un minibar, una visita al spa) a la cuenta de un huésped de
   la forma habitual: marque la línea y elija su cuenta.

Cada cuenta se liquida y se factura por separado; la salida espera hasta que
todas estén pagadas. Las noches que se cargan después (la auditoría nocturna)
van a la cuenta del huésped principal: vuelva a repartirlas antes de la salida.

## Facturar a una empresa

Cuando una estancia se reserva para una empresa, Kamra envía cada cargo al
folio correcto en el momento de registrarlo:

- Las **reglas de facturación** propias de la empresa deciden qué tipos de cargo paga
  (se definen en la empresa en **Ingresos → Empresas**, donde también se marca **Crédito
  permitido (cuentas por cobrar a empresas)**).
- Una empresa con crédito sin reglas usa **Configuración → Finanzas → Facturación
  a empresas**. La opción por defecto, **Habitación y alimentos y bebidas (alcohol a cargo del huésped)**, factura a la empresa la
  noche de habitación, su plan de comidas, las tasas, la entrada anticipada o salida tardía,
  el cargo de limpieza y la comida; lavandería, minibar, spa y varios
  quedan a cargo del huésped. **Nada (paga el huésped salvo que las reglas indiquen otra cosa)** desactiva
  la opción por defecto.
- El alcohol nunca va a un folio de empresa ni de grupo. Kamra se niega a registrarlo
  o trasladarlo allí.

En la salida, el huésped liquida su propio folio. Lo que debe la empresa
pasa solo a su cuenta de **cuentas por cobrar a empresas**, si la empresa
tiene crédito permitido.

**Cuentas por cobrar** (Finanzas → Cuentas por cobrar) reúne todas las cuentas de
empresa: quién debe qué, con cuánto retraso y cuánto crédito le queda.

- **Abrir una cuenta** (Finanzas y Administrador del hotel): pulse **Nueva
  cuenta**, elija la empresa y fije el **Número de cuenta**, el **Límite de
  crédito** (0 = sin límite), las condiciones de pago (las del alojamiento, o
  los días para pagar desde la fecha de la factura) y una **Dirección de
  facturación**. Abrir una cuenta da crédito a la empresa. La salida factura a
  esa misma cuenta.
- **Crédito renovable:** el crédito disponible es el límite menos lo que debe la
  empresa y lo que van acumulando sus estancias en curso. Cada factura lo
  consume y cada pago lo vuelve a liberar. Por encima del límite, el control de
  crédito (Configuración → Alojamiento → Crédito de empresas) avisa o bloquea la
  siguiente factura.
- **Emitir una factura sin estancia** (sala de reuniones, cuota de un contrato):
  abra la cuenta, pulse **Nueva factura**, añada una línea por cargo con su
  precio, cantidad y tipo de impuesto, y pulse **Emitir factura**. Recibe un
  número de factura, vence según las condiciones de la cuenta y envejece como
  cualquier factura. Las líneas de alimentos y bebidas llevan el tipo de
  impuesto de alimentos y bebidas del hotel.
- **Transferir una factura** a otra empresa (paga la empresa matriz o la
  agencia): pulse **Transferencia** en la factura. Pasa lo que aún se debe; lo
  pagado se queda. La factura conserva su número y su fecha.
- **Factura de fin de mes** para empresas que pagan mensualmente: elija el mes
  junto a **Factura de fin de mes** (por defecto el mes pasado) y púlselo para
  imprimirla, o **Correo electrónico** para enviarla al contacto de facturación.
  Muestra cada factura del mes con su número, base imponible e impuesto, los
  pagos de la empresa y el saldo anterior y el saldo final. Cada estancia
  conserva su propia factura fiscal; la factura de fin de mes es el resumen
  contra el que paga la empresa, con el número `SOA-<cuenta>-<AAAAMM>`.
- **Restringir una cuenta** en **Configuración de la cuenta**, con un motivo: ya
  no admite nuevas facturas ni transferencias, y la salida la pasa por el
  control de crédito. Los pagos y los estados de cuenta siguen funcionando.

**Cambiar la empresa** durante la estancia o en la salida (el huésped cambió de
empresa, o al final paga él):

1. En la cuenta, pulse **Cambiar empresa** (en la salida está en **Quién paga**).
2. Elija la nueva empresa, o **Sin empresa: paga el huésped**.
3. Elija qué pasa con los cargos ya registrados: moverlos según las reglas de
   facturación de la nueva empresa, o devolver al huésped todo lo que hay en la
   cuenta de la empresa.
4. Escriba el motivo y pulse **Cambiar empresa**.

Los cargos registrados a partir de entonces siguen las reglas de la nueva
empresa; la tarifa de la habitación se queda como se reservó. Se hace la
comprobación de crédito de la nueva empresa; si la bloquea, Finanzas o un
Administrador del hotel pueden anularla con un motivo. Kamra lo rechaza si ya
se facturó algo a la empresa anterior (su factura está emitida, o pasó a
cuentas por cobrar a empresas): cancele antes esa factura. Quién lo cambió y por
qué queda en el Registro de actividad.

**Registrar el pago de una empresa** (Finanzas y Administrador del hotel):

1. Abra **Finanzas → Cuentas por cobrar** y la empresa (o **Finanzas → Libros contables**). **Antigüedad de cuentas por cobrar a empresas** muestra el saldo de cada empresa
   por antigüedad (0-30, 31-60, 61-90, más de 90 días) y el saldo a favor sin aplicar.
2. Pulse **Registrar pago** en la fila de la empresa.
3. Indique el **Importe recibido**, el **Modo** y la **Referencia (UTR /
   n.º de cheque)**. Por defecto, el pago salda primero las facturas más antiguas;
   también puede escribir el importe de cada factura.
4. Pulse **Revisar pago**, compruebe lo que salda y luego pulse **Confirmar**.

El dinero sobrante queda en la cuenta como saldo a favor sin aplicar y paga la
siguiente factura de la empresa de forma automática.

**Enviar a una empresa su estado de cuenta** (Finanzas y Administrador del hotel):
en la fila de la empresa en **Antigüedad de cuentas por cobrar a empresas**, pulse
**Estado de cuenta** para abrirlo e imprimirlo o guardarlo en PDF, o **Enviar
estado de cuenta** para enviarlo por correo (deje la dirección en blanco para usar
el correo de facturación de la empresa). El estado de cuenta muestra cada factura
abierta con su fecha, su vencimiento, los días de retraso, lo facturado y lo
pagado, el saldo a favor sin aplicar, el saldo pendiente y la antigüedad por días
de retraso.

**Los recordatorios de pago** están desactivados hasta que active **Enviar
recordatorios de pago por correo** (Configuración → Alojamiento → Crédito de
empresas). A partir de entonces, cada mañana Kamra escribe al contacto de
facturación de la empresa 3 días antes del vencimiento de una factura, el día del
vencimiento y 15 días después, con el estado de cuenta adjunto. Cada recordatorio
se envía una vez por factura y queda en el Registro de actividad. Finanzas recibe
un aviso en la aplicación de lo enviado y de las empresas sin correo de
facturación.

**Informes:** **Vencido por empresa** y **Días de cobro (DSO)** están en
**Informes** (y, para los agentes de IA, en `run_custom_report`). El DSO es el
saldo al final del periodo dividido por lo facturado en él, multiplicado por los
días del periodo.

## Facturar a un grupo desde su habitación principal

Un grupo reservado con una habitación principal (consulte
[Reservas de grupo](/es/reservations#reservas-de-grupo-empresas-bodas)) tiene un
solo folio de **Grupo**, la cuenta del grupo, que se lleva en la habitación
principal. Al registrar cada cargo, Kamra envía a la cuenta del grupo lo que paga
la habitación principal:

- **Habitación + impuestos** (por defecto): la noche de habitación, su plan de
  comidas, las tasas, la entrada anticipada o la salida tardía, el cargo de
  limpieza y los huéspedes adicionales.
- **Habitación y alimentos y bebidas (alcohol a cargo del huésped)**: lo mismo
  más la comida.
- **Todo excepto bebidas alcohólicas**: todos los cargos.

Todo lo demás se queda en el folio propio del huésped. El alcohol nunca va a la
cuenta del grupo. Un grupo de empresa mantiene sus propias reglas de
facturación, que van primero.

**Una habitación que paga lo suyo:** marque **Paga sus propios cargos** en su fila
de la lista de huéspedes del grupo. Solo los cargos nuevos se quedan en el folio
de esa habitación; los ya registrados se trasladan con **Mover** en el
folio.

**Liquidar la cuenta del grupo:**

1. Abra el grupo. La cabecera muestra **Abrir cuenta del grupo** con su saldo.
2. Pulse **Liquidar cuenta del grupo**. Elija el medio de pago y el importe o,
   para una empresa con crédito, marque **Enviar a la cuenta por cobrar de la
   empresa**.
3. Pulse **Liquidar**. Cuando ya no queda nada pendiente, la cuenta se cierra y
   recibe su número de factura.

Puede liquidar mientras aún hay habitaciones alojadas. Kamra le avisa; sus
cargos posteriores abren una nueva cuenta del grupo.

## Cobrar y devolver un depósito de garantía

Un depósito reembolsable por daños (villas, estancias largas) se retiene para el huésped
y no cuenta como ingreso. El panel **Depósito de garantía** está en el
panel lateral de la reserva de una estancia próxima o en curso. El importe que espera el alojamiento
se define en **Configuración → Políticas de estancia → Anticipos y depósitos de garantía → Depósito de garantía**
(0 significa que no se pide).

![El panel Depósito de garantía: importes requerido, retenido, descontado y reembolsado, y los botones Cobrar un importe adicional, Retener por daños y Reembolsar depósito de garantía](/img/billing/security-deposit.png)

- **Cobrar depósito de garantía**: importe, modo de pago y, si quiere, un comprobante de tarjeta o
  una referencia de transferencia. Pasa por la caja como cualquier pago.
- **Exonerar depósito de garantía**: no se cobra dinero; el motivo es obligatorio.
- **Retener por daños**: registra un cargo por daños en el folio con su
  motivo; el depósito retenido lo paga.
- **Reembolsar depósito de garantía**: devuelve lo que sigue retenido, antes de la salida.

Un depósito cobrado desde el formulario **Registrar un pago** del folio (tipo
**Depósito de garantía**) aparece en el mismo panel.

Los **anticipos de reserva** (un pago adelantado antes de la llegada) se cobran desde el panel
**Anticipo de reserva** de la reserva: consulte [Reservas](/es/reservations). El
porcentaje que se debe puede variar según las fechas (el **Anticipo % al reservar**
de una temporada). Un viaje entre varios alojamientos puede cobrar un solo anticipo
para todas sus paradas: Kamra lo reparte y registra cada parte como anticipo en el
folio y la caja de esa parada. Consulte
[Reservar un viaje entre alojamientos](/es/reservations#reservar-un-viaje-entre-alojamientos).

## Cerrar el folio e imprimir la factura

1. Asegúrese de que el saldo es cero: cobre lo que se debe, reembolse un
   pago en exceso o deje que la parte de la empresa pase a cuentas por cobrar a empresas.
2. Pulse **Cerrar y generar factura**. Kamra asigna el siguiente número de factura
   de la serie del alojamiento y la cuenta pasa a ser una **Factura
   fiscal**.
3. Pulse **Imprimir factura**, o elija **Guardar como PDF** en el cuadro de impresión.

El título de la factura, las líneas de impuestos y el texto vienen del paquete de país. En
Arabia Saudí, una cuenta liquidada se imprime como *factura simplificada* con el
código QR de ZATCA; configure los datos del vendedor una vez en **Configuración → Facturación
electrónica ZATCA** ([Country setup](/country-setup)).

![Un folio cerrado impreso como Factura fiscal con su número de factura, líneas, resumen y resumen de impuestos](/img/billing/tax-invoice.png)

Otros botones de la barra de acciones:

- **Imprimir folio** imprime la cuenta provisional de un folio abierto.
- **Proforma** guarda una copia proforma de la cuenta tal como está y la imprime.
- **Facturar por adelantado** registra ahora las noches de habitación que faltan de la estancia,
  antes de la auditoría nocturna (para un huésped que quiere pagar todo por
  adelantado).
- **Liquidar y continuar estancia** aparece cuando un folio abierto está totalmente pagado.
  Emite una factura parcial por lo que contiene y abre un folio nuevo para
  el resto de la estancia: la forma habitual de liquidar cada pocos días en estancias largas.
  La pestaña del folio liquidado muestra entonces **Huésped ·** seguido de su número de
  factura; la pestaña del folio nuevo es **Huésped**.
- **Folio del grupo** (estancias de grupo) abre una única cuenta de empresa consolidada para
  todas las habitaciones del grupo.

## Anular una factura o emitir una nota de crédito

**Anular factura** (en un folio cerrado): escriba el motivo y pulse
**Confirmar cancelación**. El número de factura pasa al registro de
facturas anuladas, la cuenta anterior se puede seguir imprimiendo y el folio se reabre para que pueda
corregirlo y cerrarlo de nuevo con un número nuevo. Donde el país no
permite anular (Arabia Saudí), el paquete emite una nota de crédito
en su lugar.

**Nota de crédito** (Finanzas y Administrador del hotel, en un folio facturado): indique el
importe y el motivo. Kamra numera la nota de crédito con referencia a la factura
original. En una estancia de empresa que ya pasó a cuentas por cobrar a empresas, el
crédito reduce el saldo de la empresa.

## Abrir y cerrar su caja

Cada cajero tiene una sesión de caja por fecha operativa.

1. Abra **Finanzas → Mi caja**.
2. Indique el **Fondo inicial de caja** (el efectivo del cajón) y pulse
   **Abrir sesión de caja**.

![La tarjeta para abrir caja en Mi caja, con el fondo inicial y el botón Abrir sesión de caja](/img/billing/open-till.png)

Mientras la sesión está abierta, **Mi caja** muestra el fondo, el efectivo, la tarjeta y
otros cobros, los egresos, las entregas a caja central, la caja chica y el **Efectivo esperado** en
el cajón, con las transacciones recientes de la sesión debajo.

![Mi caja con una sesión abierta: fondo, efectivo recibido, tarjeta, egresos, caja chica y efectivo esperado, los formularios Egreso de caja y Entrega de efectivo a caja central, y Cerrar caja](/img/billing/my-till.png)

- **Egreso de caja**: efectivo que sale del cajón para un huésped o un proveedor. Importe y
  motivo, y luego **Registrar**.
- **Entrega de efectivo a caja central**: lleva efectivo a la caja fuerte. Importe, y luego **Entregar efectivo a caja central**.

## Contar el efectivo y cerrar la caja

1. En **Cerrar caja**, escriba el efectivo que ha contado. Kamra muestra la
   **Variación** frente al efectivo esperado mientras escribe.
2. Pulse **Cerrar sesión**.

Finanzas y el auditor nocturno también pueden cerrar la caja de otra persona, en el
paso **Cierre de caja** del [Cierre del día](/es/night-audit). **Finanzas →
Sesiones** muestra todas las sesiones con su fondo, el efectivo esperado y el contado,
y la variación.

El **Informe de turno** (**Informes → Informe de turno**) muestra cada sesión de una
fecha operativa con su efectivo, tarjeta y variación, y un diario de las
transacciones del día por tipo y modo. Indique la segunda fecha para abarcar varias
fechas operativas (hasta 92 días).

![El Informe de turno: la sesión de un cajero y el diario por tipo y modo](/img/billing/shift-report.png)

## Pagar gastos menores con caja chica

1. Abra **Finanzas → Caja chica** (o **Caja chica →** en Mi caja).
2. Rellene el **Beneficiario**, el **Importe**, una categoría (**Suministros**,
   **Mantenimiento**, **Transporte**, **Bienestar del personal**, **Varios**)
   y el **Motivo**.
3. Pulse **Registrar vale**. El efectivo sale de su caja abierta.

![La pantalla Caja chica con el formulario de vale nuevo y un vale registrado](/img/billing/petty-cash.png)

Un proveedor que envía una factura y cobra más tarde no es caja chica: regístrelo
en **Finanzas → Cuentas por pagar** (consulte [Books](/books)).

## Cambiar moneda extranjera

1. Abra **Finanzas → Cambio de moneda**.
2. Elija la moneda y la operación: **Compra (el huésped vende divisas)** o
   **Venta (el huésped compra divisas)**, y el importe en moneda extranjera.
3. Pulse **Calcular** para ver el tipo de cambio y el importe en moneda local, y luego **Registrar
   cambio de moneda**. El efectivo local pasa por su caja.

![Cambio de moneda: la calculadora con 100 USD al tipo de compra, la tabla de tipos y los cambios de hoy](/img/billing/currency-desk.png)

Finanzas y el Administrador del hotel definen los tipos de compra y venta en **Establecer tipo de cambio**
(moneda, compra, venta, y luego **Guardar**). Un tipo es la moneda del hotel por
1 unidad de la moneda extranjera, y corresponde a la fecha operativa de hoy:
guardarlo otra vez el mismo día lo actualiza.

### Obtener en línea los tipos de hoy

En lugar de escribir cada tipo, Finanzas o un Administrador del hotel pueden pulsar
**Obtener los tipos de hoy** en **Cambio de moneda**. Kamra pide a un servicio en
línea gratuito ([Exchange Rate API](https://www.exchangerate-api.com), actualizado
una vez al día) el tipo medio de mercado de cada moneda que acepta, y guarda:

- **Compra** = tipo de mercado menos su margen, **Venta** = tipo de mercado más el
  margen.
- **Origen** en línea, el tipo de mercado y quién lo obtuvo.

Se configura en **Configuración → Finanzas → Tipos de cambio**:

| Ajuste | Valor por defecto | Qué hace |
| --- | --- | --- |
| Monedas extranjeras aceptadas | Según su paquete de país (ver abajo) | Códigos ISO que se obtienen. |
| Margen sobre el tipo de mercado | 2% | Se resta para Compra y se suma para Venta. |
| Obtener los tipos automáticamente cada día | Desactivado | En cada fecha operativa se obtienen las monedas de la lista que aún no tienen tipo (se comprueba cada hora, así que también se rellena después de que la auditoría nocturna cambie la fecha). |

Hasta que defina la lista, viene del país del alojamiento, sin incluir nunca su
propia moneda:

| País | Monedas extranjeras por defecto |
| --- | --- |
| India, y países sin paquete propio | USD, EUR, GBP, AED, SAR, SGD, AUD, JPY |
| Arabia Saudí | USD, EUR, GBP, AED, INR, PKR, EGP |
| Emiratos Árabes Unidos | USD, EUR, GBP, SAR, INR, PKR, CNY, RUB |
| Brasil | USD, EUR, ARS, GBP, CLP, UYU, PYG |
| Nicaragua | USD, EUR, CRC, HNL, MXN, CAD |
| Malasia | USD, SGD, EUR, GBP, AUD, CNY, JPY, IDR |
| Indonesia | USD, SGD, AUD, EUR, JPY, CNY, MYR, SAR |
| Tailandia | USD, EUR, GBP, CNY, JPY, AUD, SGD, INR |

Finanzas y el Administrador del hotel pueden obtener los tipos o escribirlos.

Un tipo escrito por el personal es **Manual** y siempre prevalece: volver a
obtenerlos el mismo día no lo cambia, y escribir encima de un tipo obtenido lo
convierte en Manual. El impuesto de cambio y el límite por operación se heredan del
último tipo de la moneda.

Si el servicio no responde o va lento (Kamra espera 5 segundos), no cambia nada y
la pantalla muestra el error: escriba los tipos a mano. Cobrar un pago nunca
llama a internet; solo lee el tipo ya guardado para hoy.

## Cobrar un pago en moneda extranjera

Sus libros siguen en la moneda del hotel. Aun así, un huésped o una empresa pueden
pagar en USD, EUR, AED o cualquier otra moneda para la que haya fijado un tipo.

1. Fije u obtenga el tipo de hoy en **Cambio de moneda** (arriba). Los pagos usan
   el tipo de **Compra**, porque el hotel compra la moneda extranjera del huésped.
   No se usa un tipo de un día anterior: fije uno nuevo cada fecha operativa.
2. En el folio, bajo **Registrar un pago**, elija la moneda junto al medio de
   pago. Solo aparecen las monedas con tipo para hoy.
3. Elija **Efectivo** o **Transferencia bancaria** y escriba el importe en moneda
   extranjera que entrega el huésped. El formulario muestra cuánto es,
   aproximadamente, en su moneda.
4. Pulse **Registrar**. Kamra convierte al tipo de hoy y registra su moneda en el
   folio y en los libros. La línea del pago conserva el importe extranjero y el
   tipo usado, así que los cambios de tipo posteriores nunca la modifican.

Reglas que conviene saber:

- **Redondeo.** El importe registrado se redondea al céntimo (la mitad hacia
  arriba). Cuando muestra un saldo en moneda extranjera, se redondea **hacia
  arriba** al céntimo, así que pagar la cifra mostrada siempre salda la cuenta.
- **El cambio y los reembolsos van en su moneda.** Si el huésped paga de más,
  devuelva la diferencia como siempre (medio Efectivo para billetes del cajón).
- **Los billetes extranjeros quedan fuera del recuento del cajón.** La caja
  registra un pago en efectivo extranjero como **Otro**, con la moneda y el tipo
  en la nota, para que el efectivo esperado en su moneda siga cuadrando.
- **No para tarjetas ni depósitos de garantía.** Un datáfono cobra en su moneda,
  y un depósito se devuelve en su moneda, así que cobre ambos en su moneda.

**Mostrar una cuenta en otra moneda.** Bajo el total, **Mostrar en** muestra las
monedas con tipo para hoy. Al elegir una se añade una línea como
"Approx. USD 120.40 (balance USD 60.20) at 83.10". Es solo una guía para el
huésped: la factura fiscal, sus totales y su importe en letras siguen en su
moneda.

## Revisar los libros contables

**Finanzas → Libros contables** muestra los cuatro libros de folios de una fecha: **Huésped**
(lo que deben los huéspedes alojados), **Anticipo de reserva** (anticipos y depósitos de garantía
retenidos), **AR** (lo que deben las empresas, cuentas por cobrar) y **Paquete**. Debajo están el
diario por código de transacción y la antigüedad de cuentas por cobrar a empresas.

![La pantalla Libros contables: el aviso verde que indica que los libros coinciden con los folios, los cuatro libros, el diario por código de transacción y la antigüedad de cuentas por cobrar a empresas](/img/billing/ledgers.png)

El aviso de arriba compara los libros con los folios de la
fecha operativa actual. **Los libros coinciden con los folios** significa que los libros de Huésped y de
Anticipo de reserva suman lo que tienen los folios. Los débitos superan a los
créditos en lo que deben los huéspedes; es lo esperado. Si un folio no coincide,
el aviso se pone ámbar y lo muestra (consulte
[Solución de problemas](#solucion-de-problemas)). Para cualquier otra fecha solo muestra los totales.

Cada cargo, pago, anulación, traslado y bonificación genera un asiento en el libro.
Una anulación o un traslado no borra el historial: registra un asiento inverso.

## Códigos de transacción y códigos de motivo

**Finanzas → Códigos de transacción** es el catálogo de códigos de cargo y de pago
del folio (grupo de ingresos, impuesto por defecto, indicador de alcohol). Si el alojamiento está en blanco, el código vale para todos
los alojamientos. Kamra crea códigos por defecto; añada uno solo cuando su contabilidad lo necesite.
Desactívelo en lugar de eliminarlo si el diario ya lo usó.

**Finanzas → Códigos de motivo** guarda motivos codificados para anulaciones, reembolsos,
bonificaciones, cambios de tarifa y egresos de caja. Kamra incluye motivos por defecto; añada aquí
los códigos propios del alojamiento. Un código marcado como **Requiere supervisor** necesita
a Finanzas o al Administrador del hotel cuando se usa.

Las dos pantallas también están enlazadas desde **Configuración → Finanzas**.

## Revisar anulaciones y bonificaciones

**Informes → Anulaciones y bonificaciones**
muestra cada anulación, bonificación y factura anulada del alojamiento: cuándo,
en qué folio, quién lo hizo y el motivo, y el número de vale de cada
bonificación. Lo ven los usuarios de Finanzas y el Administrador del hotel.

1. Indique las fechas. Al principio muestra los últimos 30 días.
2. Pulse **Anular**, **Bonificación** o **Factura anulada** para ver un solo tipo;
   **Todos** los muestra todos, con el número de cada uno.
3. Busque por folio, nombre del empleado o motivo. Pulse un folio para abrirlo.
4. Pulse **Imprimir** para obtener una copia en papel.

![Anulaciones y bonificaciones: el rango de fechas, los filtros con sus cifras y cada anulación, bonificación y factura anulada con su folio, quién lo hizo y el motivo](/img/billing/voids-allowances.png)

## Configuración

| Opción | Dónde | Valor por defecto | Qué hace |
| --- | --- | --- | --- |
| Gestionar dinero mediante cajas | Configuración → Finanzas → Controles de caja | Activado | El personal abre su caja (con un fondo inicial) antes de cobrar o devolver dinero, y la cierra con un recuento de efectivo. Las hojas de entrada, de llegada sin reserva y de salida ofrecen **Abrir mi caja** en el momento. Desactivado, para un establecimiento pequeño sin cajón de efectivo: los pagos y reembolsos se registran sin caja; los egresos, las entregas a caja central, la caja chica y el cambio de moneda siguen necesitando una. |
| Cuando cambia la tarifa de una estancia con noches ya cargadas | Configuración → Políticas de estancia → Cambios de tarifa durante la estancia | Mantener las noches cargadas | Mantener: las noches cargadas conservan su tarifa. Abonar la diferencia: una tarifa más baja se abona por cada noche cargada. Corregir tarifas de fechas pasadas: Finanzas o un Administrador del hotel pueden [corregir noches cargadas](#corregir-noches-cargadas). |
| Exigir PIN de caja para operaciones de dinero | Configuración → Finanzas → Controles de caja | Desactivado | Los pagos, las facturas, las bonificaciones, las anulaciones, los reembolsos y las acciones de caja piden el PIN del cajero. Los agentes de IA están exentos; sus acciones quedan registradas. |
| Bloquear un PIN después de | Configuración → Finanzas → Controles de caja | 5 intentos fallidos | Bloquea el PIN tras este número de intentos fallidos. |
| Duración del bloqueo / desbloqueo | Configuración → Finanzas → Controles de caja | 15 min | Cuánto tiempo sigue bloqueado un PIN bloqueado, y cuánto tiempo siguen desbloqueadas las operaciones de dinero tras un PIN correcto. |
| Cuando una empresa con crédito no tiene reglas de facturación | Configuración → Finanzas → Facturación a empresas | Habitación y alimentos y bebidas (alcohol a cargo del huésped) | Qué cargos paga una empresa con crédito cuando no tiene reglas propias. |
| Los ajustes necesitan aprobación de un gerente | Configuración → Finanzas → Controles de caja | Desactivado (Administrador del hotel en alojamientos nuevos) | Quién aprueba una bonificación: Administrador del hotel, o Administrador del hotel o Finanzas. Hasta que se aprueba, no se descuenta de la cuenta. |
| Solo ajustes por encima de | Configuración → Finanzas → Controles de caja | 0 | Las bonificaciones menores se registran al momento. 0 significa que todas necesitan aprobación. |
| Enviar recordatorios de pago por correo | Configuración → Alojamiento → Crédito de empresas | Desactivado | Escribe al contacto de facturación de cada empresa 3 días antes del vencimiento de una factura, el día del vencimiento y 15 días después, una vez por factura y etapa. |
| Pasarela de pago | Configuración → Pagos | Ninguno | La pasarela y las claves que se usan para los enlaces de pago. |

## Conviene saber

- **Un folio solo se cierra en cero.** Kamra no cierra un folio mientras
  se deba dinero, ni mientras se deba un reembolso al huésped.
- **Los impuestos son una regla del hotel, no del cajero.** Los cargos de comida, bebida y
  minibar llevan el tipo de alimentos y bebidas de su paquete de país, así que el formulario
  muestra ese tipo en lugar de una elección. Un cargo debe ser un importe positivo
  con uno de los tipos de impuesto de su paquete; para reducir una cuenta, anule o aplique una
  bonificación.
- **Toda anulación, bonificación y anulación de factura necesita un motivo** y queda
  registrada con quién la hizo. Finanzas puede verlas todas en
  [Anulaciones y bonificaciones](#revisar-anulaciones-y-bonificaciones).
- **Los cargos solo se trasladan dentro de una estancia** (o dentro de un grupo), y solo
  entre folios abiertos.
- **Un folio de Huésped o de Grupo no se puede eliminar**, ni tampoco ningún folio con cargos
  o pagos.
- **El tiempo de desbloqueo es por persona.** Tras un PIN correcto, las
  operaciones de dinero de esa persona siguen abiertas durante el tiempo de desbloqueo en cualquier pantalla.

## Solución de problemas

**"NO_OPEN_SESSION: open your till under Finance → Cashier first."** Abra
su caja en **Finanzas → Mi caja** y vuelva a intentarlo.

**"Cannot close the folio: … is still owed."** Cobre el saldo, o
traslade la parte de la empresa a su folio para que pase a cuentas por cobrar a empresas en
la salida.

**No aparece el botón Enlace de pago.** Solo aparece en un folio abierto
con saldo, en un país cuyo paquete tenga pasarelas de pago. Si al pulsarlo
indica que no hay ninguna pasarela configurada, configure una en **Configuración → Pagos**.

**"Alcohol cannot be billed to a company folio."** Registre o traslade la bebida
al folio propio del huésped.

**El aviso de Libros contables dice "Ledger differs from folios".** El aviso
comprueba que los libros de Huésped y de Anticipo de reserva coinciden con el saldo de cada folio,
para la fecha operativa actual. Si no coinciden, muestra cada
folio con diferencias, con el saldo del folio y el saldo del libro: un
registro llegó al folio pero no al libro, o al revés.
Abra el folio desde el enlace y compare sus líneas con el diario.
Que los débitos superen a los créditos no es un problema por sí solo: es lo que
los huéspedes aún deben.

## Para desarrolladores

Las acciones del folio son herramientas MCP para agentes de IA (`get_folio`,
`add_folio_charge`, `record_payment`, `void_charge`, `apply_allowance`,
`allowance_requests`, `open_guest_bills`, `share_folio_charges`,
`change_stay_company`, `move_charges`, `split_folio_charge`, `close_folio`, `send_payment_link`,
`collect_security_deposit`, `exchange_rates`, `folio_in_currency` y más): consulte [MCP tools](/mcp-tools#billing).
Los endpoints REST están en `kamra.api` (folios, pagos, depósitos),
`kamra.cashier` (sesiones de caja, caja chica, informe de turno),
`kamra.ledger` (libros contables, cuentas por cobrar a empresas, notas de crédito, proforma, cambio de moneda) y
`kamra.statements` (estados de cuenta de empresas y recordatorios de pago). La
pantalla **Anulaciones y bonificaciones** lee `kamra.reports.void_allowance_report`
(Finanzas, Administrador del hotel). Consulte la
[API reference](/api-reference#core-front-desk-folios-guests-rooms) y
[Ledgers](/api-reference#ledgers-trial-balance-city-ledger-ar-fx-desk).
