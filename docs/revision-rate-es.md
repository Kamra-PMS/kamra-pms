# Revisión contextual de «rate» en español

Fecha: 22 de octubre de 2026. Base: commit 8f253d9b.

Se revisaron las 51 entradas existentes cuyo texto de origen contiene «rate», «rates» o una variable {rate}. Se contrastaron con los campos y cálculos que muestran las pantallas. Se corrigió una traducción existente y se añadieron tres entradas; el recurso español pasa de 2,806 a 2,809 entradas.

## Criterio

| Contexto | Término aplicado |
| --- | --- |
| Precio de alojamiento, lavandería o servicio | Tarifa |
| Porcentaje fiscal | Tasa de impuesto / tasa impositiva |
| Conversión de divisas | Tipo de cambio |
| Proporción de solicitudes fuera del plazo de atención | Porcentaje de incumplimiento |
| ADR | Tarifa media diaria; su explicación usa ingresos por habitaciones / habitaciones vendidas |

## Cambios realizados

| Ubicación | Antes | Después | Motivo |
| --- | --- | --- | --- |
| Reports.tsx: explicación del ADR | tarifa de habitación / habitación vendida | ingresos por habitaciones / habitaciones vendidas | El servidor calcula ADR como room_revenue / rooms_sold (kamra/reports.py, _day_stats). |
| CurrencyDesk.tsx: cálculo e historial | Rate (sin traducción) | Tipo de cambio | Muestra exchange_rate, la relación de conversión de la moneda extranjera a la local. |
| CurrencyDesk.tsx: configuración | Set rate (sin traducción) | Establecer tipo de cambio | Configura buy_rate y sell_rate de divisas. |
| BanquetDocument.tsx: TaxBreakup | Rate (sin traducción) | Tasa impositiva | La columna contiene r.rate seguido de % en el desglose de impuestos. |
| OpsSLA.tsx: indicador de atención | Breach rate (sin traducción) | Porcentaje de incumplimiento | Muestra breach_pct, calculado como solicitudes que incumplen el plazo / total × 100. |

En los dos contextos ambiguos se utilizan etiquetas específicas para español. La clave general «Rate» conserva «Tarifa» para los importes de alojamiento y servicios. Las etiquetas de origen de inglés y árabe conservan sus valores anteriores; no se modificaron ar.json, lib/i18n.ts ni lib/dir.ts.

Se mantienen «(tasa de impuesto de alimentos y bebidas)», «Tasa de {tax}» y «Tasa impositiva» en los campos fiscales. Las tarifas BAR, planes tarifarios, tarifas de empresa y tarifas de lavandería ya eran coherentes.

## Las 51 entradas revisadas

Las claves antiguas que solo se conservan por compatibilidad se identifican como tales. Esta tabla documenta la revisión del recurso existente; no implica que todas las pantallas de la aplicación estén traducidas.

| Clave de origen | Español tras la revisión | Contexto | Fuente |
| --- | --- | --- | --- |
| (F&B rate) | (tasa de impuesto de alimentos y bebidas) | Impuesto | screens/FolioView.tsx |
| {avail} left · sleeps {cap} · {rate}/night | Disponibles: {avail} · capacidad (adultos): {cap} · {rate}/noche | Importe de alojamiento | screens/CRS.tsx |
| {n} rooms · from {rate}/night | Habitaciones: {n} · desde {rate}/noche | Importe de alojamiento | screens/CRS.tsx |
| {tax} {rate}% | {tax} {rate}% | Impuesto | screens/FolioView.tsx |
| {tax} rate | Tasa de {tax} | Impuesto | components/RoomStayPanels.tsx; screens/FolioView.tsx |
| A channel manager sends your rooms, rates and availability to booking sites and brings their bookings back. You connect it after setup; ticking this adds it to your Finish setup list. | Un gestor de canales envía a los sitios de reserva la disponibilidad, las habitaciones y las tarifas, y sincroniza las reservas que llegan desde esos sitios. Conéctelo después de la configuración; al marcar esta opción, aparecerá en la lista «Completar configuración». | Tarifa de alojamiento o servicio | screens/Setup.tsx |
| Add rate | Agregar tarifa | Tarifa de alojamiento o servicio | screens/Laundry.tsx; screens/settings/cards.tsx |
| Amounts are inclusive of GST at the rates shown. | Los importes incluyen el GST con las tasas indicadas. | Impuesto | screens/FolioView.tsx |
| BAR (best available rate) is the base price of a room type. A season changes it for a date range, and a busy-house rule raises it when the house fills. This table shows the result per night. Rate plans and vouchers apply on top, per booking. | BAR (mejor tarifa disponible) es el precio base de cada tipo de habitación. Las temporadas pueden modificarla durante ciertos rangos de fechas, y una regla de alta ocupación la aumenta cuando hay mucha demanda. Esta tabla muestra la tarifa por noche. Los planes tarifarios y los cupones se aplican por reserva. | Tarifa de alojamiento o servicio | screens/RateCalendar.tsx |
| BAR is the best available rate: the room type's base price. A season or a busy-house (demand) rule can move it for a date. A rate plan then adjusts the whole stay, and a voucher comes off the total. | BAR es la mejor tarifa disponible: el precio base del tipo de habitación. Una temporada o una regla de alta ocupación (demanda) puede ajustarla para una fecha concreta. Después, el plan tarifario modifica el precio de toda la estancia y el cupón se resta del total. | Tarifa de alojamiento o servicio | components/RateOptions.tsx |
| Company rate | Tarifa de empresa | Tarifa de alojamiento o servicio | components/BookingDialog.tsx |
| Could not load the rates. | No se pudieron cargar las tarifas. | Tarifa de alojamiento o servicio | components/RateOptions.tsx |
| Creating sets this as your active property. Rates, seasons, vouchers and guardrails can be added later from Revenue. | Al crear el alojamiento, quedará seleccionado como activo. Después podrá configurar tarifas, temporadas, cupones y límites de precio en Ingresos. | Tarifa de alojamiento o servicio | screens/Setup.tsx |
| Everything else starts at sensible defaults. You will land on a Finish setup list: rooms and rates, the booking page, outlets, tills and your team. | El resto comienza con valores predeterminados razonables. Después verá una lista de configuración pendiente: habitaciones y tarifas, la página de reservas, puntos de venta, cajas y su equipo. | Tarifa de alojamiento o servicio | screens/Setup.tsx |
| Food & beverage is taxed at the property's F&B rate. | Los alimentos y bebidas tributan según la tasa de impuesto configurada para alimentos y bebidas en el alojamiento. | Impuesto | screens/FolioView.tsx |
| Laundry rate card | Hoja de tarifas de lavandería | Tarifa de alojamiento o servicio | screens/Laundry.tsx; screens/settings/cards.tsx |
| No rate card yet - add laundry rates in the Price menu tab. | Aún no hay tarifas de lavandería. Agréguelas en la pestaña «Tarifario». | Tarifa de alojamiento o servicio | screens/Laundry.tsx |
| No rates yet{hint} | Aún no hay tarifas{hint} | Tarifa de alojamiento o servicio | screens/Laundry.tsx |
| Or a screen, a feature (cash drop, night audit, BAR rates) or a setting. | O una pantalla, una función (entrega de efectivo, auditoría nocturna, tarifas BAR) o una configuración. | Tarifa de alojamiento o servicio | components/CommandPalette.tsx |
| Pick your region and name the property. Currency, time zone, tax and language follow the region. Add rooms, rates and the rest later, at your pace. | Seleccione su región y asigne un nombre al alojamiento. La moneda, la zona horaria, los impuestos y el idioma se configuran según la región. Después podrá agregar habitaciones, tarifas y el resto de la configuración a su ritmo. | Tarifa de alojamiento o servicio | screens/Setup.tsx |
| Rate | Tarifa | Tarifa de alojamiento o servicio | screens/Laundry.tsx; screens/RateCalendar.tsx; screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| Rate {cur} | Tarifa {cur} | Tarifa de alojamiento o servicio | screens/Laundry.tsx |
| Rate calendar | Calendario de tarifas | Tarifa de alojamiento o servicio | screens/RateCalendar.tsx |
| Rate plan | Plan tarifario | Tarifa de alojamiento o servicio | components/BookingDialog.tsx; components/RateOptions.tsx; screens/AuditPack.tsx; screens/EndOfDayWizard.tsx; screens/RateCalendar.tsx; screens/ReservationDetail.tsx; screens/Setup.tsx; kamra/settings.py |
| Rate plans | Planes tarifarios | Tarifa de alojamiento o servicio | components/RateOptions.tsx; screens/RateCalendar.tsx; screens/Setup.tsx; kamra/settings.py |
| Rates for these dates | Tarifas para estas fechas | Tarifa de alojamiento o servicio | components/RateOptions.tsx |
| room rate / room sold | ingresos por habitaciones / habitaciones vendidas | Fórmula del ADR | screens/Reports.tsx |
| Standard rate | Tarifa estándar | Tarifa de alojamiento o servicio | components/BookingDialog.tsx; components/RateOptions.tsx |
| Standard rate (no plan) | Tarifa estándar (sin plan) | Tarifa de alojamiento o servicio | components/BookingDialog.tsx |
| Step by step: choose the modules you want, then rooms, rates, and, if you run a restaurant, outlets, stations and tills. Each step asks only what it needs. | Paso a paso: elija los módulos que necesita y luego configure las habitaciones y las tarifas. Si tiene un restaurante, agregue también los puntos de venta, las estaciones y las cajas. Cada paso solicita solo la información necesaria. | Tarifa de alojamiento o servicio | screens/Setup.tsx |
| Tax rate | Tasa impositiva | Impuesto | components/CheckOutDialog.tsx; screens/BanquetDocument.tsx |
| The hotel's billing rules pick the folio, and food and drink take the hotel's food tax rate. | Las reglas de facturación determinan el folio al que se cargan los consumos. A los alimentos y bebidas se les aplica la tasa de impuesto configurada para ellos. | Impuesto | components/RoomStayPanels.tsx |
| Zero-rate and complimentary rooms | Habitaciones con tarifa cero y de cortesía | Tarifa de alojamiento o servicio | screens/AuditPack.tsx; kamra/night_audit.py |
| {property} in {city}: {count} room types from {price} per night. Best-rate direct booking, pay at hotel. {description} | {property} en {city}: {count} tipos de habitación desde {price} por noche. Reserva directamente al mejor precio y paga en el hotel. {description} | Tarifa de alojamiento o servicio | screens/PublicBooking.tsx |
| Booked rate | Tarifa reservada | Tarifa de alojamiento o servicio | screens/AuditPack.tsx; screens/EndOfDayWizard.tsx |
| CGST ({rate}%) | CGST ({rate}%) | Impuesto | Clave de compatibilidad del diccionario |
| Demand pricing (hurdle rates) | Tarifas según demanda y ocupación | Tarifa de alojamiento o servicio | screens/settings/cards.tsx |
| Every room night posted so far matches its booked rate. | Todas las noches de habitación registradas hasta ahora coinciden con la tarifa reservada. | Tarifa de alojamiento o servicio | screens/EndOfDayWizard.tsx |
| Every room night was posted at its booked rate. | Todas las noches de habitación se registraron con la tarifa reservada. | Tarifa de alojamiento o servicio | screens/AuditPack.tsx |
| GST {rate}% | GST {rate}% | Impuesto | Clave de compatibilidad del diccionario |
| IGST ({rate}%) | IGST ({rate}%) | Impuesto | Clave de compatibilidad del diccionario |
| No zero-rate rooms tonight. | No hay habitaciones con tarifa cero para esta noche. | Tarifa de alojamiento o servicio | screens/EndOfDayWizard.tsx |
| Per-item prices the app quotes and bills from. Blank express = 1.5× the normal rate. | Tarifas por prenda para cotizar y facturar. Si la tarifa exprés está en blanco, se aplica 1,5 veces la tarifa normal. | Tarifa de alojamiento o servicio | Clave de compatibilidad del diccionario |
| Rate check | Verificación de tarifas | Tarifa de alojamiento o servicio | kamra/night_audit.py |
| Rate Plans | Planes tarifarios | Tarifa de alojamiento o servicio | lib/apps.ts; lib/searchIndex.ts; screens/configs.ts |
| Rate variance | Diferencia de tarifa | Tarifa de alojamiento o servicio | screens/AuditPack.tsx; kamra/night_audit.py; kamra/settings.py |
| Rate variance tolerance | Tolerancia de diferencia de tarifa | Tarifa de alojamiento o servicio | kamra/settings.py |
| Rates, seasons, offers and the partners who sell you. | Tarifas, temporadas, ofertas y socios que comercializan su alojamiento. | Tarifa de alojamiento o servicio | lib/apps.ts |
| Room nights posted off the booked rate, and rooms at zero rate. | Noches de habitación registradas con una tarifa distinta de la reservada y habitaciones con tarifa cero. | Tarifa de alojamiento o servicio | screens/EndOfDayWizard.tsx |
| Room rate variances | Diferencias de tarifas de habitación | Tarifa de alojamiento o servicio | kamra/night_audit.py |
| SGST ({rate}%) | SGST ({rate}%) | Impuesto | Clave de compatibilidad del diccionario |

## Alcance

Se revisaron los recursos y los usos en el código. No se modificaron los importes, porcentajes, fórmulas ni reglas de cálculo. No se ha realizado un recorrido visual exhaustivo de todas las pantallas.

## Comprobaciones realizadas

- Comparación con la base: una traducción española corregida, tres agregadas y ninguna eliminada.
- Las variables de las entradas modificadas se conservan.
- Las 2,809 traducciones españolas y las 2,151 árabes coinciden con sus columnas del catálogo; no hay claves duplicadas en el catálogo.
- El diccionario árabe y los archivos compartidos lib/i18n.ts y lib/dir.ts permanecen idénticos a la base.
- Las llamadas nuevas a Set rate y Breach rate mantienen el texto de origen en inglés y árabe, ya que no tenían traducción árabe. Los casos ambiguos de Rate se condicionan al español.
- Compilación de producción correcta: npm run build (TypeScript y Vite). Se incluyeron los archivos generados que exige el repositorio.
- git diff --check sin errores.
