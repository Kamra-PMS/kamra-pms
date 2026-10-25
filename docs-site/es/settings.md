# Configuración

Todo lo que configura un alojamiento está en **Configuración** (el engranaje
de la barra lateral). Cada parte de Kamra tiene su propia página, y cada
página indica quién puede cambiarla. Cada cambio se comprueba contra sus
límites y se guarda en el **Registro de actividad** con el valor anterior y
el nuevo.

![El centro de configuración: páginas agrupadas en Alojamiento, Módulos, Acceso, Integraciones y Tú](/img/settings/hub.png)

## Buscar un ajuste

Escriba en **Buscar en configuración** (o pulse **/**) y elija el
resultado. Se abre la página correcta y se desplaza hasta el ajuste.

![Búsqueda de "no-show" en la configuración y salto al ajuste](/img/settings/search.gif)

## Cambiar un ajuste

1. Abra la página (por ejemplo **Recepción**).
2. Cambie los valores. Cada ajuste cambiado muestra un punto ámbar, y una
   barra en la parte inferior cuenta los cambios sin guardar.
3. Pulse **Guardar cambios** en esa barra (o **Descartar**). Si un valor
   está fuera de rango ("no puede ser mayor que 60"), no se guarda nada y
   la página indica cuál es.

Un ajuste que no tiene su valor predeterminado muestra debajo
**Restablecer valores predeterminados**.

![Una página de configuración de módulo con sus secciones y el interruptor del módulo](/img/settings/module-page.png)

Solo ve las páginas que su rol puede cambiar. La línea **Cambiado por**
bajo el título de cada página indica esos roles; el Administrador del hotel
puede cambiarlas todas.

## Las páginas

| Página | Qué contiene | Guía |
| --- | --- | --- |
| Alojamiento | Nombre, razón social, logotipo, país (que elige el paquete de impuestos y facturación), moneda, zona horaria, dirección, número de registro fiscal | [Configuración por país](/country-setup) |
| Políticas de estancia | Horas de entrada y salida, estancia mínima, plazo de cancelación gratuita, cargos por cancelación y no presentación, depósitos | [Reservas](/es/reservations) |
| Privacidad y datos | Cuánto tiempo se conservan los datos y mensajes de los huéspedes, el contacto de privacidad | |
| Recepción | Llegadas, retenciones, no presentaciones y la vista del día | [Recepción](/es/front-desk) |
| Limpieza | Plazos de las tareas, rotación de habitaciones y precios de lavandería | [Limpieza](/es/housekeeping) |
| Operaciones | Plazos de las solicitudes de huéspedes según la prioridad | [Operaciones](/es/operations) |
| Alimentos y bebidas | Aceptación automática de comandas (KOT), comprobantes de anulación, ventana de reserva de mesas, impresoras de cocina, comprobación de velocidad del punto de venta | [Alimentos y bebidas](/es/fnb#configuracion) |
| Banquetes y grupos | Márgenes de las cotizaciones, hitos de pago, seguimientos | [Banquetes](/es/banquets) |
| Ingresos | Cuánto puede sobrevender el hotel, precios según la demanda | [Ingresos](/es/revenue) |
| Finanzas | Impuesto de habitación, cargos, controles de caja (PIN, límites de reembolso en efectivo) | [Facturación](/es/billing) |
| Motor de reservas | La página pública `/book`: activada o no, reserva inmediata o solicitud de reserva, cómo pagan los huéspedes | [Motor de reservas](/es/booking-engine) |

Las páginas de las partes de Kamra que se pueden desactivar (Limpieza,
Operaciones, Alimentos y bebidas, Banquetes, Ingresos, Motor de
reservas…) tienen un interruptor **Módulo activado** arriba. Solo el
Administrador del hotel puede activar o desactivar módulos. Un módulo
desactivado desaparece de la barra lateral para todos, y sus herramientas
se ocultan a los agentes de IA.

## Agregar personal y dar acceso

**Configuración → Personal y acceso** muestra a todas las personas que
pueden iniciar sesión, con sus roles y los alojamientos a los que acceden.

![Personal y acceso: los roles y el acceso a alojamientos de cada persona](/img/settings/staff.png)

1. Pulse **Agregar personal**.
2. Escriba su **Nombre completo** y su **Correo electrónico** (inicia
   sesión con él).
3. Marque sus **Roles**. Cada rol indica qué abre.
4. Elija el **Acceso a alojamientos**: todos los alojamientos (incluidos
   los que se añadan después) o solo algunos.
5. Deje activado **Envíeles por correo electrónico un enlace para
   establecer una contraseña** para enviar una invitación, o desactívelo y
   comparta usted el acceso.

![El panel Agregar personal con las descripciones de los roles](/img/settings/add-staff.png)

Para cambiar a alguien más adelante, pulse **Administrar** en su fila.
Desde ahí puede cambiar roles y alojamientos, **Restablecer PIN de
cajero** o **Desactivar** a la persona. El personal desactivado no puede
iniciar sesión, y su historial se conserva. No puede cambiar su propio
acceso, y solo TI puede cambiar a un administrador de TI.

## Qué puede hacer cada rol

**Configuración → Roles y permisos** muestra qué aplicaciones abre cada rol
y qué páginas de configuración puede cambiar. Los roles son conjuntos
fijos: cada pantalla, llamada a la API y herramienta de IA los comprueba en
el servidor.

![La matriz de roles: aplicaciones que abre cada rol y ajustes que puede cambiar cada rol](/img/settings/roles.png)

| Rol | Día a día |
| --- | --- |
| Administrador del hotel | Dirige el alojamiento: todas las aplicaciones, toda la configuración, el personal y el acceso |
| Recepción | Reservas, entradas y salidas, huéspedes, folios, la caja |
| Responsable de ingresos | Tarifas, temporadas, límites de tarifas, canales, el motor de reservas, ventas de banquetes |
| Finanzas | Facturación, libros contables, auditoría nocturna, exportaciones, controles de impuestos y de caja |
| Auditor nocturno | Cierre del día: llegadas, salidas, cierre de caja, el paquete de auditoría |
| Supervisor de limpieza | El panel de habitaciones, inspecciones, plazos de las tareas, precios de lavandería |
| Limpieza | Sus propias tareas, estado de las habitaciones, objetos perdidos, normalmente en la aplicación móvil |

TI (Administrador del sistema) también gestiona las claves de
desarrollador y añade alojamientos.

## Desactivar módulos

**Configuración → Módulos** muestra cada módulo con su interruptor, para
que pueda desactivar lo que este alojamiento no usa (una casa de huéspedes
sin restaurante desactiva Alimentos y bebidas). Sus aplicaciones
desaparecen del lanzador, de la búsqueda y de las herramientas del agente
de IA para todos. Recepción y Administración siempre están activados. No se
borra nada; al volver a activar un módulo, vuelve tal como estaba.

![Configuración → Módulos](/img/settings/modules.png)

## Integraciones

- **Pagos**: la pasarela que se usa para los enlaces de pago (anticipos,
  depósitos, liquidación del folio). Las pasarelas disponibles dependen del
  paquete del país. Consulte [Facturación](/es/billing).

  ![Configuración de pagos](/img/settings/payments.png)

- **Asistente de IA**: use su propia clave de IA (cualquier servicio
  compatible con OpenAI) para el **Agente Kamra** en la consola. Los campos
  de contacto y de documento de identidad del huésped se eliminan antes de
  enviar nada al modelo.

  ![Configuración del asistente de IA: proveedor, modelo y clave](/img/settings/ai.png)

- **Acceso de IA (MCP)** (en Acceso): quién puede conectar Claude, ChatGPT
  u otro cliente MCP (sin acceso, MCP Read o MCP Manage, por persona), si
  el acceso de IA está activado aquí, **Bloquear herramientas de
  escritura**, herramientas bloqueadas una a una, los clientes conectados
  con **Desconectar**, y direcciones adicionales de inicio de sesión OAuth
  (solo TI). Consulte
  [Who can use MCP](/ai-and-mcp#who-can-use-mcp).

  ![Acceso de IA (MCP): los interruptores del alojamiento, el rol MCP de cada persona, los clientes conectados y las herramientas bloqueadas](/img/settings/ai-access.png)
- **Facturación electrónica ZATCA**: solo aparece para Arabia Saudí.
  Consulte [Configuración por país](/country-setup).

## Apariencia

**Configuración → Apariencia** define el tema (claro, oscuro o el del
sistema) y el idioma
solo para este navegador. Al elegir árabe, el diseño pasa a leerse de
derecha a izquierda.

![Apariencia: tema e idioma](/img/settings/appearance.png)

## Conviene saber

- La configuración es por alojamiento. Con varios alojamientos, cambie de
  alojamiento en la parte superior de la pantalla antes de modificarla.
- Nada más escribe estos valores: la auditoría nocturna, el motor de
  reservas y el punto de venta leen la misma configuración, así que un
  cambio se aplica de inmediato.
- El Registro de actividad (**Administración → Registro de actividad**)
  muestra quién cambió cada ajuste, cuándo, y de qué valor a cuál.
- Para ver quién inició sesión en Kamra y cuándo, elija **Inicios de sesión
  del personal** en el filtro del Registro de actividad. Muestra los
  inicios de sesión, los cierres de sesión y los intentos fallidos del
  personal de este alojamiento. Solo para Administrador del hotel, Finanzas
  y TI.

## Para desarrolladores

Las páginas y los valores vienen de un único registro en
`kamra/settings.py` (`settings_schema`, `save_settings`); el código lee un
valor con `get_setting(property, key)`. El personal y los roles están en
`kamra/staff.py`. Consulte la [referencia de la API](/api-reference).
