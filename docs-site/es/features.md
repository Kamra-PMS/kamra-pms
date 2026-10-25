# Funciones de un vistazo

Qué hace Kamra, módulo por módulo, con un enlace a la guía completa de cada
uno. Todo lo que aparece aquí está en la aplicación de código abierto; no
hay ediciones.

**Última versión estable:** [v2.6.20](/releases). Mapa del sistema y
arquitectura: [Cómo funciona Kamra](/es/how-it-works).

## Recepción

La pantalla **Hoy** muestra las llegadas, las salidas, los huéspedes
alojados y el estado de cada habitación. El registro de entrada muestra lo
preparada que está una estancia (registro en línea, documento de identidad
y justificante de domicilio, datos de contacto), sugiere una habitación e
imprime la ficha de registro con un escaneo del documento de cada ocupante.
Los huéspedes sin reserva previa se atienden en una sola pantalla, y los
huéspedes pueden registrar su entrada en línea con un enlace.

![La pantalla Hoy](/img/front-desk/today.png)

[Guía de recepción →](/es/front-desk)

## Reservas

Reserve a partir de una cotización que calcula el precio de cada noche, con
extras, regímenes de comidas, facturación a empresa y varias habitaciones a
la vez. El **Calendario de ocupación** muestra las habitaciones por fecha
con la situación del hotel de cada día; el calendario vende por tipo de
habitación. Los grupos, los bloqueos de habitaciones, la lista de espera,
los depósitos antes de la llegada y la cancelación con el cargo de la
política vienen incluidos, y la **Central de reservas** busca en todos los
alojamientos que usted gestiona.

![El calendario de ocupación](/img/reservations/tape-chart.png)

[Guía de reservas →](/es/reservations)

## Facturación y caja

Folios con un tipo de impuesto por línea, facturación dividida y dirigida
(una empresa paga la habitación, el huésped paga el bar), pagos y enlaces de
pago, depósitos de garantía, facturas y notas de crédito, cuentas de
empresa con antigüedad de saldos, y una caja con informes de turno, caja
chica y cambio de divisas. Las anulaciones y las bonificaciones siempre
necesitan un motivo.

![Un folio de huésped](/img/billing/folio.png)

[Guía de facturación →](/es/billing)

## Auditoría nocturna

El asistente de **Cierre del día** revisa las llegadas, las salidas, las
cuentas abiertas del restaurante y las cajas, le permite confirmar o
corregir cada una, y después registra las noches, aplica la política de no
presentación y guarda un paquete de auditoría con los informes del día.
También se ejecuta solo a las 03:00.

![El asistente de Cierre del día](/img/night-audit/wizard.png)

[Guía de auditoría nocturna →](/es/night-audit)

## Informes y paneles

Un resumen gerencial de ayer y del mes, paneles del alojamiento y de la
cartera (ocupación, ADR, RevPAR, cobros), presupuesto frente a resultados,
aportación por origen, empresa y agencia, el informe de SLA de solicitudes
de huéspedes y una exportación contable para Tally, Zoho Books o ERPNext.

![El resumen gerencial](/img/reports/manager-flash.png)

[Guía de informes →](/es/reports)

## Limpieza

Un panel de habitaciones para los supervisores y una aplicación móvil para
el personal de piso: tomar una habitación de la bolsa, aceptar o rechazar,
empezar y terminar con una foto. Las tareas tienen plazos y se escalan
cuando van con retraso. El registro del minibar, la lavandería de
huéspedes desde la recogida hasta el folio, los objetos perdidos y el
traspaso de turno están en las mismas pantallas.

![El panel de habitaciones de limpieza](/img/housekeeping/room-board.png)

[Guía de limpieza →](/es/housekeeping)

## Solicitudes de huéspedes

Anote la solicitud de un huésped (toallas, un grifo que gotea), envíela a un
departamento, siga su plazo según la prioridad y vea cómo trabajó cada
departamento en el informe de SLA. Una solicitud de mantenimiento puede
convertirse en una tarea de limpieza.

![Solicitudes de huéspedes abiertas](/img/operations/guest-requests.png)

[Guía de solicitudes de huéspedes →](/es/operations)

## Alimentos y bebidas: punto de venta y cocina

Un punto de venta para restaurante con plano de mesas, varias cuentas por
mesa, servicio a la habitación, comida para llevar y a domicilio; una
pantalla de cocina por estación; impresoras de cocina que envían cada plato
a la impresora de quien lo cocina; cargos a la habitación que se registran
en el folio; y existencias de cocina que se descuentan al enviar el pedido.
**Auto-KOT** opcional: envíe el pedido y la comanda de cocina se imprime sin
un paso de aceptación aparte.

![El punto de venta del restaurante](/img/fnb/pos-bill.png)

[Guía de alimentos y bebidas →](/es/fnb)

## Banquetes y grupos

Desde la primera consulta hasta la cotización, la orden de evento (BEO), los
recibos y el cierre, con una agenda y una vista mensual de cada salón, un
catálogo de menús y servicios, listas de comprobación para cada evento y
registros.

![Un evento de banquete](/img/banquets/function.png)

[Guía de banquetes →](/es/banquets)

## Ingresos y tarifas

Tipos de habitación, planes de tarifas, temporadas, regímenes de comidas,
vales, tarifas negociadas para empresas y agencias de viajes, precios según
la demanda (tarifas mínimas por demanda) y límites de tarifas: un mínimo y
un máximo de los que no pueden salirse los cambios de tarifa hechos por un
agente de IA o la API. Las cotizaciones siempre las calcula el código de
precios de Kamra, nunca las inventa un modelo.

![Planes de tarifas](/img/revenue/rate-plans.png)

[Guía de ingresos →](/es/revenue)

## Motor de reservas

Su propia página de reservas en `/book`, con tarifas y disponibilidad en
tiempo real, extras y experiencias, reserva inmediata o solicitud de
reserva, y pago en el hotel, un anticipo, un cargo de reserva o el importe
completo en línea.

![La página de reservas para huéspedes](/img/booking-engine/book.png)

[Guía del motor de reservas →](/es/booking-engine)

## Los impuestos de su país

El país del alojamiento elige un **paquete de localización**: reglas y
etiquetas de impuestos, textos de la factura, moneda y formato de números,
los documentos de identidad que acepta la recepción y las formas de pago.
Hay paquetes para la India (GST), Indonesia, Tailandia, Malasia, los
Emiratos Árabes Unidos y Arabia Saudí (con facturación electrónica ZATCA),
además de un paquete de impuesto único para el resto de países. Añadir un
país es un solo archivo de Python. Consulte
[Configuración por país](/country-setup).

## Alquileres de corta estancia

Ponga el tipo de alojamiento en **Alquiler de corta estancia** y la página
de reservas se convierte en un catálogo de lugares, cada uno vendido por
habitaciones privadas o como casa completa. Reservar la villa completa
retira sus habitaciones de la venta. Las cotizaciones incluyen cargos de
limpieza y depósitos reembolsables. Consulte
[Motor de reservas](/es/booking-engine).

## Varios alojamientos

Un solo acceso con selector de alojamiento, perfiles de huéspedes
compartidos entre sus alojamientos, acceso a alojamientos por persona,
central de reservas y un panel de cartera. Consulte
[Configuración y personal](/es/settings) e [Informes](/es/reports).

## Cambiar desde otro PMS

Exporte sus reservas desde eZee, Cloudbeds o cualquier sistema que genere
un CSV. El importador reconoce las columnas y el formato de fecha de cada
proveedor, empareja los tipos de habitación y muestra una vista previa de
lo que se importará y por qué se omitiría cada fila antes de escribir nada.
Las estancias pasadas entran como historial del huésped, así que los
huéspedes que vuelven se reconocen desde el primer día. Consulte la
[lista de puesta en marcha](/go-live).

## WhatsApp

Conecte **su propio** número de Meta Cloud API. Las confirmaciones de
reserva, los enlaces de registro de entrada, las solicitudes de pago y una
bandeja de conversaciones funcionan desde Kamra. Las plantillas y la
limpieza de datos privados siguen la configuración del alojamiento.

[Guía de WhatsApp →](/whatsapp)

## Channel manager (OTA)

Envíe disponibilidad y tarifas, y reciba reservas y modificaciones a
través del conector del channel manager. Los secretos son obligatorios; los
webhooks sin firma se rechazan.

[Guía del channel manager →](/channel-manager)

## Privacidad (DPDP y conservación)

Borrado de datos del huésped y exportación para el derecho de acceso,
plazos de conservación para los archivos de documentos de identidad y el
texto de los chats, y un aviso de privacidad para huéspedes en varias
lenguas de la India. Los datos de contacto no se envían al proveedor de IA.

## IA, de forma segura

Kamra está hecho para que una IA pueda trabajar en él sin confiar en ella a
ciegas:

- Conecte Claude (o cualquier cliente MCP) y trabaja como un miembro del
  personal, con los roles de esa persona y solo los módulos que el
  alojamiento tiene activados.
- El **Agente Kamra** integrado usa su propia clave de IA.
- Los precios, los impuestos y los cargos siempre los calcula el código de
  Kamra, y los límites de tarifas impiden que un agente de IA fije una
  tarifa fuera del mínimo y el máximo.
- Cada acción está en el **Registro de actividad**: quién, qué, por qué, y
  el registro antes y después.

Consulte [Conecte su IA](/ai-and-mcp), las
[herramientas MCP](/mcp-tools) y [Cómo funciona Kamra](/es/how-it-works).

## Administración

**Administración → Estado del sistema** compara su versión con la última
publicada, hace diagnósticos del sitio e indica los pasos de actualización
para su tipo de instalación. Nunca actualiza por su cuenta.

## Formas de instalación

| Forma | Guía |
| --- | --- |
| Docker en su VPS | [Inicio rápido](/quickstart) |
| Guías por proveedor | [Instalación en su servidor](/self-hosting/) |
| Frappe Cloud Marketplace | [Frappe Cloud](/self-hosting/frappe-cloud) |
| Bench clásico | [Instalar con bench](/self-hosting/bench) |
| Mismo sitio que ERPNext / RR. HH. | [ERPNext y Frappe HR](/self-hosting/erpnext-hr) |
