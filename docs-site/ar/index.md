---
layout: home

hero:
  name: Kamra
  text: نظام إدارة فندقية يستطيع الوكلاء تشغيله فعلا
  tagline: نظام إدارة فندقية مفتوح المصدر مع طبقة MCP خاضعة للصلاحيات. يقدّم Claude (أو أي وكيل) عروض الأسعار، ويحجز، ويرحّل الرسوم كمستخدم تُفحص صلاحياته. الأسعار تبقى في الكود. كل إجراء مسجّل في سجل التدقيق.
  image:
    src: /kamra-mark.svg
    alt: Kamra
  actions:
    - theme: brand
      text: اربط Claude (MCP)
      link: /ai-and-mcp
    - theme: alt
      text: مرجع أدوات MCP
      link: /mcp-tools
    - theme: alt
      text: API · Postman
      link: /developers
    - theme: alt
      text: العرض الحي
      link: /demo

features:
  - title: MCP هو ما يميّز المنتج
    details: أكثر من 100 أداة خاضعة للصلاحيات على /mcp. القائمة نفسها المسموح بها في واجهة الموظفين. محصورة حسب الدور، ومرتبطة بالوحدات المفعّلة، ومسجّلة بالكامل. النموذج لا يخترع سعرا أبدا.
    link: /ai-and-mcp
  - title: كل أدوات MCP
    details: الاسم والمعاملات ونقطة النهاية لكل أداة في السجل، يُعاد إنشاؤها من الكود في كل بناء للوثائق.
    link: /mcp-tools
  - title: كيف يعمل Kamra
    details: مسار كتابة واحد للواجهة وREST والوكلاء. مخططات البنية، ودورة حياة الإقامة، وقواعد المال.
    link: /ar/how-it-works
  - title: REST API و Postman
    details: استدعِ الدوال نفسها من أنظمتك. نزّل مجموعة Postman وابدأ.
    link: /developers
  - title: الميزات وآخر إصدار
    details: من الاستقبال إلى المآدب، والمأكولات والمشروبات، وWhatsApp، وحزم الضرائب لكل دولة، مع الجديد في v2.6.17.
    link: /ar/features
  - title: التثبيت
    details: Docker على خادم VPS، أو bench التقليدي، أو سوق Frappe Cloud. التطبيق نفسه كاملا برخصة AGPL.
    link: /self-hosting/
---

## ما الذي يميّز Kamra

معظم برامج الفنادق تضيف روبوت محادثة إلى خدمة SaaS مغلقة. **بُني Kamra
بحيث يتشارك الوكيل وموظف الاستقبال مسار كتابة واحدا خاضعا للصلاحيات.**

1. **MCP أولا.** اربط Claude (أو أي عميل MCP) بـ `/mcp`. تُصفّى الأدوات
   حسب أدوار المستخدم المسجّل دخوله والوحدات المفعّلة في العقار.
2. **مال محسوب بالكود.** عروض الأسعار والضرائب والتوفر ورسوم الإلغاء
   تأتي من `pricing.py` ودفتر الفاتورة، ولا تأتي من النموذج أبدا. وترفض
   الحدود أي سعر خارج النطاق.
3. **تدقيق كامل.** كل استدعاء أداة يغيّر البيانات يُسجَّل في سجل النشاط
   مع من فعل، وماذا فعل، ولماذا.
4. **الواجهات البرمجية نفسها للجميع.** واجهة الموظفين وREST وMCP ووكيل
   Kamra داخل التطبيق تستدعي دوال `@frappe.whitelist` نفسها. لا يوجد
   كاتب ثانٍ.

ابدأ من هنا: **[اربط ذكاءك الاصطناعي (MCP)](/ai-and-mcp)** ·
**[مرجع أدوات MCP](/mcp-tools)** ·
**[كيف يعمل Kamra](/ar/how-it-works)** ·
**[اختصارات المطورين](/developers)**

**الإصدار المستقر الحالي:** [v2.6.17](/releases) ·
[العرض الحي](https://demo.kamrapms.com) ·
[سوق Frappe Cloud](https://frappecloud.com/marketplace/apps/kamra)

![شاشة اليوم في Kamra: الوصول والمغادرة ولوحة الغرف والضيوف المقيمون](/img/front-desk/today.png)

## من أين تبدأ

- **تريد قصة الذكاء الاصطناعي:** [اربط ذكاءك الاصطناعي](/ai-and-mcp)، ثم
  [مرجع أدوات MCP](/mcp-tools). البنية ومسار الكتابة الواحد:
  [كيف يعمل Kamra](/ar/how-it-works).
- **تعمل على التكامل:** [API و MCP و Postman](/developers): أساسيات REST،
  و[مرجع API](/api-reference) الكامل، و
  [مجموعة Postman ↓](https://kamrapms.com/docs/kamra.postman_collection.json).
- **تدير الفندق:** [أدلة حسب الدور](/ar/user-guide) وأدلة الوحدات في
  الشريط الجانبي.
- **تقوم بالتثبيت:** [البدء السريع](/quickstart)، أو
  [الاستضافة الذاتية](/self-hosting/)، أو
  [Frappe Cloud](/self-hosting/frappe-cloud).

**روابط سريعة:** [ربط MCP](/ai-and-mcp) · [أدوات MCP](/mcp-tools) ·
[أساسيات API](/api) · [مرجع API](/api-reference) ·
[Postman ↓](https://kamrapms.com/docs/kamra.postman_collection.json) ·
[الجديد](/releases) ·
[سجل التغييرات](https://github.com/Kamra-PMS/kamra-pms/blob/main/CHANGELOG.md)
