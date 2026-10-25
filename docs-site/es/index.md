---
layout: home

hero:
  name: Kamra
  text: El PMS hotelero que los agentes pueden operar de verdad
  tagline: PMS de código abierto con una capa MCP controlada. Claude (o cualquier agente) cotiza, reserva y registra cargos como un usuario con permisos verificados. Los precios se calculan en el código. Cada acción queda auditada.
  image:
    src: /kamra-mark.svg
    alt: Kamra
  actions:
    - theme: brand
      text: Conectar Claude (MCP)
      link: /ai-and-mcp
    - theme: alt
      text: Referencia de herramientas MCP
      link: /mcp-tools
    - theme: alt
      text: API · Postman
      link: /developers
    - theme: alt
      text: Demo en vivo
      link: /demo

features:
  - title: MCP es la ventaja del producto
    details: Más de 100 herramientas controladas en /mcp. La misma lista permitida que la recepción. Limitadas por rol y por módulo, con registro completo. El modelo nunca inventa una tarifa.
    link: /ai-and-mcp
  - title: Todas las herramientas MCP
    details: Nombre, argumentos y endpoint de todo el registro de herramientas, generado a partir del código en cada compilación de la documentación.
    link: /mcp-tools
  - title: Cómo funciona Kamra
    details: Una sola vía de escritura para la interfaz, REST y los agentes. Diagramas de arquitectura, ciclo de la estancia y reglas del dinero.
    link: /es/how-it-works
  - title: API REST y Postman
    details: Llame a los mismos métodos desde su sistema. Descargue la colección de Postman y empiece.
    link: /developers
  - title: Funciones y última versión
    details: De la recepción a los banquetes, Alimentos y bebidas, WhatsApp y paquetes fiscales por país, además de las novedades de la v2.6.17.
    link: /es/features
  - title: Instalación
    details: Docker en un VPS, bench clásico o Frappe Cloud Marketplace. La misma aplicación AGPL completa.
    link: /self-hosting/
---

## Qué hace diferente a Kamra

La mayoría del software hotelero añade un chatbot a un SaaS cerrado. **Kamra
está hecho para que un agente y un recepcionista compartan una única vía de
escritura controlada.**

1. **Primero MCP.** Conecte Claude (o cualquier cliente MCP) a `/mcp`. Las
   herramientas se filtran según los roles del usuario que inició sesión y
   los módulos activados en el alojamiento.
2. **Dinero determinista.** Las cotizaciones, los impuestos, la
   disponibilidad y los cargos por cancelación salen de `pricing.py` y del
   libro del folio, nunca del modelo. Los límites rechazan las tarifas fuera
   de rango.
3. **Auditoría completa.** Cada llamada a una herramienta que modifica datos
   queda en el Registro de actividad con quién, qué y por qué.
4. **Las mismas API para todos.** La interfaz de recepción, REST, MCP y el
   Agente Kamra integrado llaman a las mismas funciones `@frappe.whitelist`.
   No hay un segundo escritor.

Empiece aquí: **[Conecte su IA (MCP)](/ai-and-mcp)** ·
**[Referencia de herramientas MCP](/mcp-tools)** ·
**[Cómo funciona Kamra](/es/how-it-works)** ·
**[Accesos rápidos para desarrolladores](/developers)**

**Versión estable actual:** [v2.6.17](/releases) ·
[Demo en vivo](https://demo.kamrapms.com) ·
[Frappe Cloud Marketplace](https://frappecloud.com/marketplace/apps/kamra)

![Pantalla Hoy de Kamra: llegadas, salidas, el panel de habitaciones y los huéspedes alojados](/img/front-desk/today.png)

## Por dónde empezar

- **Le interesa la parte de IA:** [Conecte su IA](/ai-and-mcp) y después
  la [referencia de herramientas MCP](/mcp-tools). Arquitectura y la vía
  única de escritura: [Cómo funciona Kamra](/es/how-it-works).
- **Va a integrar Kamra:** [API, MCP y Postman](/developers): conceptos
  básicos de REST, la [referencia completa de la API](/api-reference),
  [colección de Postman ↓](https://kamrapms.com/docs/kamra.postman_collection.json).
- **Usted dirige el hotel:** [Guías por rol](/es/user-guide) y las guías de
  cada módulo en la barra lateral.
- **Va a instalar Kamra:** [Inicio rápido](/quickstart),
  [Instalación en su servidor](/self-hosting/) o
  [Frappe Cloud](/self-hosting/frappe-cloud).

**Enlaces rápidos:** [Conectar MCP](/ai-and-mcp) · [Herramientas MCP](/mcp-tools) ·
[Conceptos básicos de la API](/api) · [Referencia de la API](/api-reference) ·
[Postman ↓](https://kamrapms.com/docs/kamra.postman_collection.json) ·
[Novedades](/releases) ·
[registro de cambios](https://github.com/Kamra-PMS/kamra-pms/blob/main/CHANGELOG.md)
