# Ingresos: tarifas, temporadas y ofertas

La aplicación Ingresos reúne todo lo que decide cuánto cuesta una habitación: los precios
por tipo de habitación, los planes tarifarios, las temporadas, los planes de comidas, los cupones, las experiencias, los
límites de tarifas del propietario y los precios según la demanda, además de las empresas y las agencias
de viajes que venden sus habitaciones. La ven los Responsables de ingresos y los Administradores del hotel.
**Tipos de habitación** está en la aplicación Ingresos y en la aplicación Administración.

![La lista de Temporadas: una temporada alta de fin de año a +25% y una oferta de temporada de lluvias a -400 en las habitaciones Standard](/img/revenue/seasons.png)

## Cómo calcula Kamra un precio

Cada cotización (en el formulario de reserva de recepción, en la [página de reservas](/es/booking-engine),
desde el asistente de IA o por la API) sale del mismo código. Ningún modelo de IA
calcula nunca importes de dinero. Para cada noche de una estancia:

1. **Precio del tipo de habitación.** El precio base cubre los adultos incluidos en él;
   los adultos adicionales y los menores añaden su propio precio por noche. Un único huésped
   paga la tarifa de ocupación individual cuando hay una definida.
2. **Temporada.** La temporada que cubre esa fecha sube, baja o sustituye el
   precio. Una temporada para un tipo de habitación gana sobre una de todo el establecimiento; dentro de
   cada grupo gana la de mayor **Prioridad**.
3. **Demanda.** Cuando el establecimiento se va llenando, se suma el recargo por demanda
   y se mantiene la tarifa mínima. Consulte
   [Precios según la demanda](#precios-segun-la-demanda-tarifas-minimas).

Después, para toda la estancia:

4. **Plan tarifario.** Su ajuste se aplica al total de habitación de la estancia.
5. **Plan de comidas.** Precio por adulto y por menor, por noche.
6. **Cupón.** Se descuenta del total de habitación y comidas.
7. **Cargos e impuestos.** Cargo de limpieza, mascotas, tasa de alojamiento y después impuestos. Los tipos de impuesto
   y si sus precios incluyen impuestos vienen de **Configuración → Finanzas**
   y de su [paquete de país](/country-setup).

Cuando una reserva se confirma, sus tarifas por noche quedan fijadas. Una temporada,
un cambio de tarifa o un recargo por demanda posterior nunca cambia lo que paga un huésped confirmado.

## Ver la tarifa de cualquier fecha

El precio base de un tipo de habitación es su **BAR**, la mejor tarifa disponible: el precio
antes de que lo modifique una temporada, una regla de demanda, un plan tarifario o un cupón.

- **Calendario de tarifas** (Ingresos, Calendario de tarifas) muestra la tarifa de cada tipo de habitación
  para los próximos 7 a 31 días. Las noches en ámbar están por encima de la BAR y las azules
  por debajo. Un punto indica que una temporada o una regla de ocupación alta ha cambiado la noche;
  selecciónela para ver cuál y en cuánto. La página también enlaza al lugar donde
  se cambia cada capa.
- **En una reserva o en una llegada sin reserva previa**, el formulario tiene un panel Tarifas para estas fechas.
  Muestra la tarifa de cada noche y qué la cambió, la estancia completa con cada
  plan tarifario junto a la tarifa estándar (seleccione uno para usarlo), y si
  el cupón es válido y cuánto descuenta.

Estas pantallas explican un precio. Nunca lo fijan: cada cifra sale del
mismo código que la cotización, así que lo que ve es lo que se cobra.

## Definir los precios por tipo de habitación

1. Abra **Ingresos → Tipos de habitación** (o **Administración → Tipos de habitación**) y elija un
   tipo de habitación, o pulse **Nuevo**.
2. Indique el **Precio base / noche** y los **Adultos incluidos en el precio base**.
3. Indique **Adulto adicional / noche**, **Menor / noche** y, si vende la
   habitación a una sola persona por menos, **Tarifa de ocupación individual**.
4. Indique **Máximo de adultos** y **Máximo de menores**. La página de reservas no vende
   más huéspedes que esto.
5. Pulse **Guardar**.

![La lista de Tipos de habitación con el precio base, la ocupación base, el precio por adulto adicional y el tipo de impuesto](/img/revenue/room-types.png)

![El tipo de habitación Deluxe: nombre, código, identificador del anuncio, precio base, adultos incluidos, ocupación individual, adulto adicional y campos de grupo pequeño](/img/revenue/room-type-form.png)

Dos precios opcionales:

- **Umbral de grupo pequeño (adultos)** y **Tarifa de grupo pequeño / adulto**:
  por debajo de ese número de adultos, se cobra por persona en lugar de la tarifa de la habitación.
  Limítelo a algunos días con **Días para grupos pequeños**.
- **Identificador de la URL pública (/stay/…)** da al tipo de habitación su propia página
  en el motor de reservas, por ejemplo `/stay/deluxe`.

## Agregar una temporada

Una temporada cambia el precio por noche entre dos fechas.

1. Abra **Ingresos → Temporadas → Nuevo**.
2. Indique un **Nombre**, una **Fecha de inicio** y una **Fecha final (inclusive)**.
3. Elija un **Tipo de habitación (en blanco = todos)**, o déjelo en blanco para todo el
   establecimiento.
4. Elija un **Ajuste**:
   - **Porcentaje**: `20` suma un 20%, `-10` descuenta un 10%.
   - **Importe**: suma (o, si es negativo, descuenta) un importe fijo por
     noche.
   - **Precio fijo**: fija el precio por noche en este valor.
5. Opcional: **Días de la semana (p. ej., fri, sat)** para aplicarla solo esos
   días. `weekend` significa sábado y domingo; `weekday` significa de lunes a
   viernes.
6. Opcional: **Mínimo de noches** (estancia más corta en estas fechas) y
   **No reembolsable** (una estancia que toque estas fechas no se puede cancelar
   sin cargo).
7. Indique una **Prioridad** y pulse **Guardar**.

![Creación de una temporada nueva: nombre, fechas, Porcentaje, 20, prioridad y mínimo de noches](/img/revenue/season-new.gif)

![La temporada alta de fin de año: +25%, prioridad 10, un mínimo de dos noches y no reembolsable](/img/revenue/season-form.png)

## Crear un plan tarifario

Un plan tarifario cambia el total de habitación de toda la estancia: mejor tarifa disponible,
no reembolsable, empresa.

1. Abra **Ingresos → Planes tarifarios → Nuevo**.
2. Indique un **Nombre** y un **Código**.
3. Elija un **Tipo de ajuste** y un **Valor del ajuste**: **Porcentaje** con
   `-10` es un 10% de descuento; **Importe** suma un importe fijo a la estancia;
   **Precio fijo** sustituye el total de habitación.
4. Opcional: una línea de **Política de cancelación**, y **Plan predeterminado**.
5. Pulse **Guardar**.

![Tres planes tarifarios: Best Available Rate al 0%, Non-refundable al -10% y Corporate al -15%](/img/revenue/rate-plans.png)

Una reserva usa un plan tarifario cuando indica uno. En el formulario **Nueva
reserva** de recepción, elíjalo en **Plan tarifario**; **Tarifa estándar (sin plan)**
no usa ninguno. Las reservas hechas con el asistente de IA, las
[MCP tools](/mcp-tools), la API y un
[channel manager](/channel-manager) conectado también pueden indicar uno. La página
pública de reservas no tiene selector de plan tarifario.

Una reserva para una empresa con un **Plan tarifario negociado** recibe ese plan
cuando no se elige otro. El formulario muestra entonces **Tarifa de empresa: …** en
**Plan tarifario**. El plan se guarda en la reserva, así que un cambio posterior en el
contrato de la empresa no cambia su precio.

## Agregar planes de comidas

1. Abra **Ingresos → Planes de comidas → Nuevo**.
2. Elija un **Código**: EP, CP, MAP o AP.
3. Dele una **Etiqueta** que los huéspedes entiendan, como "Alojamiento y desayuno".
4. Indique el **Precio por adulto / noche** y el **Precio por menor / noche**.
5. Marque **Predeterminado** en el plan con el que debe empezar el formulario de reserva de recepción.
6. Pulse **Guardar**.

![Dos planes de comidas: CP alojamiento y desayuno y MAP desayuno y cena, con precio por adulto y por menor por noche](/img/revenue/meal-plans.png)

La página de reservas muestra todos los planes de comidas, además de **Solo habitación**.

## Crear un cupón

1. Abra **Ingresos → Vales → Nuevo**.
2. Indique un **Código**. Los huéspedes pueden escribirlo en mayúsculas o minúsculas; Kamra lo guarda en
   mayúsculas.
3. Elija un **Tipo** (**Porcentaje** o **Importe**) y un **Valor**.
4. Opcional: **Válido desde**, **Válido hasta**, **Mínimo de noches** y
   **Máximo de usos (0 = ilimitado)**.
5. Pulse **Guardar**.

![Dos cupones: WELCOME500 con 500 de descuento y STAYLONGER con un 10% de descuento en estancias de tres noches o más](/img/revenue/vouchers.png)

Los huéspedes indican un cupón en **¿Tienes un código?** en la página de reservas; en
recepción se indica en el formulario de reserva. **Usado** cuenta cada reserva que
lo ha canjeado.

## Agregar experiencias

Las experiencias son complementos que se venden con una estancia: un ritual de spa, una excursión, una
cena a la luz de las velas, un traslado al aeropuerto.

1. Abra **Ingresos → Experiencias → Nuevo**.
2. Indique el **Nombre**, elija una **Categoría** (Spa, Excursión, Gastronomía, Actividad,
   Transporte, Otro) e indique el **Precio** y el **Impuesto (%)**.
3. Opcional: **Duración (p. ej., 90 min, medio día)**, **Descripción (visible
   para los huéspedes)** y una **Foto**.
4. Marque **Mostrar en la página pública de reservas** para ofrecerla en `/book`.
5. Pulse **Guardar**.

![La lista de Experiencias: complementos de spa, excursión, gastronomía, actividad y transporte con su precio, duración y un 1 donde cada uno aparece en la página de reservas](/img/revenue/experiences.png)

Marque **Deshabilitado** para dejar de vender una sin eliminarla. Consulte
[Motor de reservas](/es/booking-engine) para ver lo que ven los huéspedes.

## Definir el mínimo y el máximo (límites de tarifas)

Los límites de tarifas son los topes que pone el propietario a los cambios de tarifa.

1. Abra **Ingresos → Límites de tarifas → Nuevo**.
2. Elija un **Tipo de habitación (en blanco = todos)**.
3. Indique el **Precio mínimo / noche** y el **Precio máximo / noche**.
4. Opcional: **Días de la semana (p. ej., fri, sat)**, para que el mínimo del fin de semana pueda estar
   por encima del de entre semana.
5. Pulse **Guardar**.

![Tres límites de tarifas: uno para todo el establecimiento de 2.200 a 15.000, Deluxe de 3.500 a 9.000, y Deluxe el viernes y el sábado de 4.500 a 11.000](/img/revenue/guardrails.png)

Cuando más de un límite cubre un día, gana el más específico: tipo de
habitación y días, después tipo de habitación, después todo el establecimiento con días, y por último
todo el establecimiento.

Los límites de tarifas controlan **los cambios de tarifa hechos con el asistente de IA, la herramienta MCP
`set_room_rate` o la API**. Un cambio fuera de los límites se rechaza
indicando el motivo. Cada cambio aceptado se guarda como una temporada llamada
"Rate set …" con prioridad 100, para que pueda verlo y deshacerlo en la
pantalla Temporadas. Los límites de tarifas no controlan las temporadas que el personal crea a mano.

## Precios según la demanda (tarifas mínimas)

1. Abra **Ingresos → Configuración**.
2. En **Tarifas según demanda y ocupación**, pulse **Agregar nivel**.
3. Indique **Ocupación ≥** (por ejemplo `80`), un porcentaje de **Recargo +**
   y, si quiere un mínimo, un importe de **Tarifa mínima**.
4. En **Para**, deje **Todos los tipos de habitaciones** o elija un tipo de habitación.
5. Pulse **Guardar**.

![Configuración de Ingresos: límite de sobreventa y tres niveles de demanda, al 70% (+10%) y al 85% (+20%, mínimo 6.500) para todos los tipos de habitación, y al 85% (+25%) solo para Deluxe](/img/revenue/settings.png)

Para cada noche, Kamra cuenta las reservas confirmadas y con entrada registrada frente a
las habitaciones del alojamiento. Cuando esa ocupación alcanza un nivel, la cotización suma
el recargo sobre el precio de temporada, y la noche nunca se vende por debajo de
la tarifa mínima. Se aplica el nivel más alto alcanzado. Un tipo de habitación con sus propios
niveles usa esos: un nivel de tipo de habitación alcanzado gana sobre los niveles
para todos los tipos. Un cambio de tarifa por IA o por API que quede por debajo de la tarifa mínima se rechaza.

Los límites de tarifas no limitan el recargo por demanda. Solo acotan las tarifas fijadas
con `set_room_rate` (Kamra Agent, MCP o la API), no los recargos por
demanda, las temporadas del personal ni las cotizaciones.

La misma página contiene el **Límite de sobreventa**: cuánto por encima de la capacidad
pueden venderse las reservas sin habitación asignada. `0` no sobrevende nunca.

## Agregar una empresa o una agencia de viajes

Las **Empresas** son cuentas corporativas:

1. Abra **Ingresos → Empresas → Nuevo**.
2. Indique el **Nombre de la empresa**, el número fiscal y un contacto.
3. Opcional: un **Plan tarifario negociado**. Las reservas de la empresa lo reciben
   cuando no se elige otro plan.
4. Marque **Crédito permitido (cuentas por cobrar a empresas)** si la empresa paga
   a crédito.
5. Pulse **Guardar** y vuelva a abrir la empresa para definir sus **Reglas de
   facturación**: qué tipos de cargo van al folio de la empresa. Consulte
   [Facturación](/es/billing).

![Una ficha de empresa con contacto, plan tarifario negociado, crédito permitido y reglas de facturación](/img/revenue/company-form.png)

Las **Agencias de viajes** son orígenes de reserva con comisión. Abra
**Ingresos → Agencias de viajes → Nuevo**, indique el **Nombre de la agencia**, el **Tipo**
(Agencia de viajes, OTA, Operador turístico, Departamento corporativo) y la **Comisión (%)**.
En recepción se elige la agencia en el formulario de reserva, y Kamra calcula la
comisión de las reservas de esa agencia.

## Configuración

| Opción | Dónde | Valor por defecto | Qué hace |
| --- | --- | --- | --- |
| Límite de sobreventa | **Configuración → Ingresos** | 0% | Cuánto por encima de la capacidad pueden venderse las reservas sin habitación asignada. |
| Niveles de demanda | **Configuración → Ingresos** | ninguno | Recargo y tarifa mínima según la ocupación prevista, para todos los tipos de habitación o para uno. |
| Las tarifas mostradas incluyen impuestos | **Configuración → Finanzas** | desactivado | Si está activado, sus precios incluyen impuestos y Kamra descuenta el impuesto del precio. |
| Modalidad de impuesto, umbral de tramo y tipos | **Configuración → Finanzas** | del paquete de país | El impuesto sobre las noches de habitación. |
| Cargo de limpieza, cargo por mascota, tasa de alojamiento | **Configuración → Finanzas** | 0 | Líneas adicionales en cada cotización. |

## Conviene saber

- Una temporada con **Precio fijo** fija el precio antes del recargo por demanda, así que
  una noche con mucha ocupación todavía puede venderse por encima.
- **Mínimo de noches** y **No reembolsable** en una temporada se aplican a cualquier estancia
  que toque esas fechas, no solo a las estancias que caen dentro de ellas.
- Un cupón no puede descontar más que el total de habitación y comidas. No
  descuenta las líneas de limpieza, mascotas ni tasas.
- Un nivel de demanda se aplica a todo el establecimiento salvo que elija un tipo de habitación
  en **Para**.
- El **Plan tarifario negociado** de una empresa se aplica a una reserva nueva de esa
  empresa cuando la reserva no indica otro plan. En un alojamiento del mismo grupo,
  se aplica el plan con el mismo **Código**; si no hay ninguno, la estancia se cotiza
  sin plan.

## Solución de problemas

**Una temporada no cambia el precio.** Revise las fechas (la fecha final está
incluida), **Días de la semana**, **Deshabilitado**, y si una temporada para ese
tipo de habitación, o una con mayor **Prioridad**, cubre la misma noche.

**"Voucher … needs a stay of at least … nights".** El cupón tiene un
**Mínimo de noches** mayor que la estancia. Los demás rechazos indican el motivo:
aún no ha empezado, ha caducado, se ha canjeado por completo o ya no está activo.

**El asistente de IA dice que una tarifa está "Blocked by guardrail".** La tarifa está
fuera de un límite de tarifas para ese tipo de habitación y ese día. Cambie la tarifa, o el
límite en **Ingresos → Límites de tarifas**.

## Para desarrolladores

Las cotizaciones salen de `kamra/pricing.py` (`quote`). Los cambios de tarifa pasan por
`kamra.api.set_room_rate`, que comprueba los límites de tarifas y las tarifas mínimas. Los agentes de IA
usan las herramientas `quote`, `booking_options` y `set_room_rate`: consulte
[MCP tools](/mcp-tools) y la [API reference](/api-reference).
