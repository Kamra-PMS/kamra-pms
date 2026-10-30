# Roles and access

Kamra uses Frappe's own permission system. A role is a normal Frappe
**Role**. What a role may do is set in **Role Permission Manager**, the
same screen every Frappe app uses. Nothing about access is hidden in code
that a hotel can't see or change, apart from a few safety rules listed at
the end of this page.

There are three things to set for a person:

1. **Their roles** (what they may do).
2. **Their properties** (which hotels they may do it at).
3. Optionally a **Role Profile**, a named bundle of roles such as
   "Duty Manager", so you pick one thing instead of five.

## How it works

Every staff action in Kamra (check a guest in, post a charge, close a
till, run the night audit) checks one permission on the record it touches.
For example:

| Action | Permission it checks |
| --- | --- |
| Check a guest in or out | Reservation: Check In Out |
| Post a charge, take a payment, void a charge | Folio: Bill |
| Open or close a till | Cashier Session: Operate Till |
| Run the night audit | Night Audit Run: Run Audit |
| Approve a void or a supervisor reason | Folio: Approve |
| Override a company's credit limit | Corporate Account: Override Credit |
| See an app in the app switcher | Property: App Front Desk (and one per app) |

These are **permission types**: extra tick boxes next to Read, Write and
Create in Role Permission Manager. The full list with each one's default
roles is at the bottom of this page.

The Kamra screens, the REST API, Claude (MCP) and the in-app Kamra Agent
all ask the same question, so a change in Role Permission Manager applies
everywhere at once. Menus and buttons in Kamra follow it too.

Out of the box the permissions match Kamra's built-in roles: Front Desk,
Finance, Revenue Manager, Night Auditor, Housekeeping, Housekeeping
Supervisor, Hotel Admin and the Kamra Agent.

## Who can change access

Roles and permissions are an IT task. You need the **System Manager** role
to open Role Permission Manager. A Hotel Admin can give people roles and
properties on **Settings > Staff & access** in Kamra, but can't change
what a role may do.

## Create a role

Say you want a **Concierge** who can see stays and look after guest
requests, but not touch money.

1. Open Desk: `/app/role/new`.
2. **Role Name**: `Concierge`. Leave **Desk Access** ticked (it marks the
   person as staff). Save.
3. Open **Role Permission Manager** (`/app/permission-manager`).
4. Pick the **Document Type**, for example `Service Ticket`, and press
   **Add A New Rule**. Choose the role `Concierge` and level 0.
5. Tick the boxes it needs, for example **Handle Requests** and **Work
   Requests**. Tick **Read** too if the role should be able to open the
   record in Desk. The change saves as you tick.
6. Repeat for other document types (for example `Reservation`: **View
   Stays**).

The new role now shows on **Settings > Staff & access** and can be given
to people there.

::: tip Copy a role
To start from what an existing role can do, open each document type in
Role Permission Manager and tick the same boxes for the new role. Kamra's
defaults for every box are in the table below.
:::

## Change what a built-in role may do

Open Role Permission Manager, pick the document type and tick or untick
the box for that role. For example, to stop Front Desk voiding charges
without a supervisor, untick **Folio: Bill** for Front Desk and give it to
a role your supervisors hold.

The first change to a document type copies its defaults into your own
rules, as Frappe always does. **Restore Original Permissions** puts the
defaults back.

## Give people roles

- In Kamra: **Settings > Staff & access**, open the person and tick their
  roles.
- In Desk: open the **User**, section **Roles & Permissions**.
- With a Role Profile: on the User, pick a **Role Profile**. The user
  gets exactly the roles in it, and keeps following the profile when you
  edit it.

Kamra ships these Role Profiles. Edit them in Desk at `/app/role-profile`;
Kamra never overwrites your changes.

| Role Profile | Roles |
| --- | --- |
| Receptionist | Front Desk |
| Front Office Manager | Front Desk, Night Auditor, Revenue Manager |
| Duty Manager | Front Desk, Night Auditor, Housekeeping Supervisor |
| Night Auditor | Night Auditor, Front Desk |
| F&B Manager | Front Desk, Finance |
| Finance Manager | Finance, Night Auditor |
| General Manager | Hotel Admin, Finance |

## Limit someone to one property

A chain gives each person the hotels they work at:

- In Kamra: **Settings > Staff & access**, **Property access**.
- In Desk: add a **User Permission** with **Allow** `Property` and the
  property name.

A person with no Property user permission can reach every property. A
person with one or more can reach only those. This applies to every
action, report, Desk list and REST call.

## Approvals

Approvals are permissions too:

- **Folio: Approve** decides who may approve a kitchen void, a reason code
  that needs a supervisor, and who appears in the approver list at the
  till. Default: Hotel Admin and Finance.
- **Corporate Account: Override Credit** decides who may book or bill past
  a company's credit limit. Default: Hotel Admin and Finance.

The approver still enters their own cashier PIN where the property asks
for one.

Approvals that move a document through states (for example an allowance
request waiting for a manager) use Frappe **Workflow** when they ship, so
you edit who approves in Desk at `/app/workflow`.

## Rules that don't change

Some rules are part of Kamra and no permission changes them:

- **An AI agent never approves or overrides money.** The Kamra Agent
  can't approve a void or override a credit block, even
  if its role is given that permission. A person must do it.
- **IT-only actions stay IT-only.** API keys, the Developers page and new
  properties need System Manager.
- **Administrator and System Manager** can do everything.
- **Property limits** above always apply on top of permissions.
- **Money records are read-only in Desk and REST.** Ledger entries,
  cashier transactions, credit notes, audit runs and the activity log can
  only change through Kamra's actions, which keep the books balanced and
  log who did what.

## All permissions and their defaults

Generated from the code by `docs-site/gen_permissions.py`.

<!-- permissions:start -->
| Doctype | Permission | Default roles | Endpoints |
| --- | --- | --- | --- |
| Agent Action Log | View activity (`view_activity`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `agents_api.activity_feed`, `agents_api.activity_detail` |
| Agent Action Log | View sign ins (`view_sign_ins`) | Finance, Hotel Admin, System Manager | `agents_api.staff_sign_ins` |
| Banquet Menu | Edit catalogue (`edit_catalogue`) | Finance, Front Desk, Hotel Admin, Revenue Manager, System Manager | `banquet.save_banquet_menu`, `banquet.delete_banquet_menu`, `banquet.save_service_item` and 4 more |
| Cashier Session | Configure (`configure`) | Hotel Admin, System Manager | `api.reset_cashier_pin` |
| Cashier Session | Manage cash office (`manage_cash_office`) | Finance, Hotel Admin, System Manager | `cashier.save_terminal`, `cashier.bank_deposit`, `cashier.approve_variance` |
| Cashier Session | Operate till (`operate_till`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `cashier.open_session`, `cashier.post_paid_out`, `cashier.cash_drop` and 2 more |
| Cashier Session | Set float (`set_float`) | Finance, Hotel Admin, Kamra Agent, System Manager | `cashier.set_petty_cash_float` |
| Cashier Session | Use pin (`use_pin`) | Finance, Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Revenue Manager, System Manager | `api.cashier_pin_status`, `api.set_cashier_pin`, `api.verify_cashier_pin` |
| Cashier Session | View tills (`view_tills`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Night Auditor, System Manager | `api.cash_summary`, `cashier.current_session`, `cashier.my_till` and 8 more |
| Channel Manager Connection | Configure (`configure`) | Hotel Admin, System Manager | `marketplace.disconnect_channel` |
| Channel Manager Connection | Sync channels (`sync_channels`) | Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `channel_manager.push_ari`, `channel_manager.import_room_mappings` |
| Channel Manager Connection | View channels (`view_channels`) | Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `channel_manager.connection_status` |
| City Ledger Account | Send statements (`send_statements`) | Finance, Hotel Admin, System Manager | `statements.company_statement`, `statements.email_company_statement` |
| City Ledger Account | Settle account (`settle_account`) | Finance, Hotel Admin, Kamra Agent, System Manager | `ledger.city_ledger_settle` |
| City Ledger Account | View account (`view_account`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `ledger.city_ledger_account` |
| City Ledger Entry | View financials (`view_financials`) | Finance, Hotel Admin, Kamra Agent, System Manager | `ledger.financial_activity` |
| City Ledger Entry | View ledgers (`view_ledgers`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Night Auditor, System Manager | `ledger.ledger_balances`, `ledger.journal_by_transaction_code`, `ledger.city_ledger_aging` and 1 more |
| Copilot Conversation | Ask agent (`ask_agent`) | Finance, Front Desk, Hotel Admin, Revenue Manager, System Manager | `assistant.ask`, `assistant.ask_stream` |
| Copilot Conversation | Ask help (`ask_help`) | Finance, Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Revenue Manager, System Manager | `assistant.help_ask` |
| Copilot Conversation | Configure (`configure`) | Hotel Admin, System Manager | `assistant.test_connection` |
| Copilot Conversation | Keep conversations (`keep_conversations`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `assistant.list_conversations`, `assistant.get_conversation`, `assistant.create_conversation` and 3 more |
| Copilot Conversation | View presets (`view_presets`) | Front Desk, Hotel Admin, System Manager | `assistant.provider_presets` |
| Corporate Account | Override credit (`override_credit`) | Finance, Hotel Admin, System Manager | checked inside Kamra |
| Corporate Account | Set credit (`set_credit`) | Finance, Hotel Admin, System Manager | `credit.set_company_credit_terms` |
| Corporate Account | View credit (`view_credit`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Night Auditor, Revenue Manager, System Manager | `credit.company_credit_status` |
| Corporate Account | View terms (`view_terms`) | Finance, Front Desk, Hotel Admin, Revenue Manager, System Manager | `credit.company_credit_terms` |
| Exchange Rate | Set rates (`set_rates`) | Finance, Hotel Admin, Kamra Agent, System Manager | `ledger.upsert_exchange_rate` |
| Exchange Rate | Use currency desk (`use_currency_desk`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `ledger.list_exchange_rates`, `ledger.currency_calculator`, `ledger.exchange_history` |
| Folio | Approve (`approve`) | Finance, Hotel Admin, System Manager | checked inside Kamra |
| Folio | Audit voids (`audit_voids`) | Finance, Hotel Admin, System Manager | `payments.gateway_info`, `reports.void_allowance_report` |
| Folio | Bill (`bill`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.record_advance`, `api.deposit_payment_link`, `api.security_deposit` and 28 more |
| Folio | Find invoices (`find_invoices`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `api.find_invoices` |
| Folio | Issue credit note (`issue_credit_note`) | Finance, Hotel Admin, Kamra Agent, System Manager | `ledger.issue_credit_note` |
| Folio | Post from pos (`post_from_pos`) | Hotel Admin, Kamra Agent, POS Integrator, System Manager | `pos_interface.pos_room_lookup`, `pos_interface.pos_post_room_charge` |
| Folio | View folio (`view_folio`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Night Auditor, System Manager | `api.get_folio`, `api.checkout_context`, `checkin.check_in_readiness` and 1 more |
| Folio Ledger Entry | Export books (`export_books`) | Finance, Hotel Admin, Kamra Agent, System Manager | `accounting.export_invoices` |
| Group Booking | Bill group (`bill_group`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.group_master_folio`, `api.group_folios`, `api.settle_group_bill` |
| Group Booking | Book group (`book_group`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.create_group_booking`, `api.pickup_group_room`, `ledger.group_checkout` |
| Group Booking | Manage group (`manage_group`) | Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `api.set_group_master`, `api.group_detail`, `api.save_group_blocks` |
| Guest | Configure (`configure`) | Hotel Admin, System Manager | `api.set_guest_blacklist`, `api.merge_guests`, `api.anonymize_guest` and 1 more |
| Guest | Handle guests (`handle_guests`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.guests_with_stats`, `api.guest_search`, `api.guest_alert` and 7 more |
| Guest | Verify id (`verify_id`) | Front Desk, Hotel Admin, System Manager | `api.verify_guest_id` |
| Housekeeping Task | Do housekeeping (`do_housekeeping`) | Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, System Manager | `api.hk_queue`, `api.hk_update_task`, `api.hk_upload_media` and 6 more |
| Housekeeping Task | Supervise (`supervise`) | Front Desk, Hotel Admin, Housekeeping Supervisor, Kamra Agent, System Manager | `api.hk_staff` |
| Hurdle Rate | Manage hurdles (`manage_hurdles`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `api.hurdle_rates`, `api.save_hurdle_rate`, `api.delete_hurdle_rate` |
| Ingredient | Manage stock (`manage_stock`) | Finance, Hotel Admin, System Manager | `inventory.save_ingredient`, `inventory.delete_ingredient`, `inventory.receive_stock` and 3 more |
| Ingredient | View stock (`view_stock`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `inventory.ingredients`, `inventory.recipe_overview`, `inventory.stock_list` and 3 more |
| Kamra Custom Report | Run reports (`run_reports`) | Finance, Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, Night Auditor, Revenue Manager, System Manager | `custom_reports.list_report_datasets`, `custom_reports.list_report_packs`, `custom_reports.run_report_pack` and 6 more |
| Kitchen Printer | Configure printers (`configure_printers`) | Finance, Hotel Admin, System Manager | `printing.save_printer`, `printing.delete_printer`, `printing.test_print` |
| Kitchen Printer | Print tickets (`print_tickets`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `printing.print_bill`, `printing.claim_jobs`, `printing.ack_jobs` and 3 more |
| Laundry Order | Handle laundry (`handle_laundry`) | Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, System Manager | `laundry.request_pickup`, `laundry.collect_laundry`, `laundry.laundry_status` and 3 more |
| Laundry Order | Price laundry (`price_laundry`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `laundry.save_laundry_rate`, `laundry.delete_laundry_rate`, `laundry.import_laundry_rates` and 1 more |
| Laundry Order | View laundry (`view_laundry`) | Finance, Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, System Manager | `laundry.laundry_rates`, `laundry.laundry_board` |
| Menu Item | Edit menu (`edit_menu`) | Finance, Hotel Admin, System Manager | `inventory.save_recipe`, `inventory.set_menu_availability`, `menu_import.preview_menu_import` and 2 more |
| Menu Item | View recipes (`view_recipes`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `inventory.menu_recipe` |
| Night Audit Run | Configure (`configure`) | Hotel Admin, System Manager | `api.gstr1_rows` |
| Night Audit Run | E invoicing (`e_invoicing`) | Finance, Hotel Admin, System Manager | `api.zatca_settings`, `api.zatca_invoice_xml` |
| Night Audit Run | Recover date (`recover_date`) | Finance, Hotel Admin, Kamra Agent, Night Auditor, System Manager | `night_audit.recover_stuck_business_date` |
| Night Audit Run | Run audit (`run_audit`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Night Auditor, System Manager | `api.run_night_audit`, `night_audit.night_audit_precheck`, `night_audit.night_audit_pack` and 6 more |
| Night Audit Run | Schedule audit (`schedule_audit`) | Finance, Hotel Admin, Night Auditor, System Manager | `night_audit.night_audit_schedule` |
| Outbound Webhook | Configure (`configure`) | Hotel Admin, System Manager | `webhooks.webhook_events`, `webhooks.list_webhooks`, `webhooks.save_webhook` and 6 more |
| POS Order | Manage outlet (`manage_outlet`) | Finance, Hotel Admin, System Manager | `pos.speed_check` |
| POS Order | Take orders (`take_orders`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `pos.outlets`, `pos.pos_menu`, `pos.in_house_rooms` and 36 more |
| Property | App admin (`app_admin`) | Hotel Admin, System Manager | checked inside Kamra |
| Property | App booking engine (`app_booking_engine`) | Hotel Admin, Revenue Manager, System Manager | checked inside Kamra |
| Property | App events (`app_events`) | Front Desk, Hotel Admin, Revenue Manager, System Manager | checked inside Kamra |
| Property | App finance (`app_finance`) | Finance, Front Desk, Hotel Admin, Night Auditor, System Manager | checked inside Kamra |
| Property | App fnb (`app_fnb`) | Finance, Front Desk, Hotel Admin, System Manager | checked inside Kamra |
| Property | App front desk (`app_front_desk`) | Front Desk, Hotel Admin, Night Auditor, System Manager | checked inside Kamra |
| Property | App housekeeping (`app_housekeeping`) | Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, System Manager | checked inside Kamra |
| Property | App operations (`app_operations`) | Front Desk, Hotel Admin, System Manager | checked inside Kamra |
| Property | App revenue (`app_revenue`) | Hotel Admin, Revenue Manager, System Manager | checked inside Kamra |
| Property | Configure (`configure`) | Hotel Admin, System Manager | `api.set_enabled_modules`, `connect.client.status`, `connect.client.link` and 19 more |
| Property | Edit settings (`edit_settings`) | Finance, Hotel Admin, Housekeeping Supervisor, Revenue Manager, System Manager | `settings.save_settings` |
| Property | Go live (`go_live`) | Finance, Hotel Admin, System Manager | `golive.csv_template`, `golive.preview_companies`, `golive.run_companies` and 3 more |
| Property | Upload images (`upload_images`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.upload_room_image` |
| Property | Use console (`use_console`) | Finance, Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, Night Auditor, Revenue Manager, System Manager | `api.enabled_modules`, `today_layout.get_today_layout`, `today_layout.save_today_layout` and 1 more |
| Property | Use settings (`use_settings`) | Finance, Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Revenue Manager, System Manager | `api.my_connector_credentials`, `api.linked_records`, `mcp_oauth.connect_info` and 2 more |
| Property | Verify tax id (`verify_tax_id`) | Finance, Front Desk, Hotel Admin, System Manager | `api.verify_tax_id` |
| Property | View briefing (`view_briefing`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.position_briefing`, `onboarding.setup_checklist` |
| Property | View dashboard (`view_dashboard`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `dashboards.property_dashboard` |
| Property | View flash (`view_flash`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Night Auditor, System Manager | `reports.manager_flash`, `settings.menu_masters` |
| Property | View locale (`view_locale`) | Finance, Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, Revenue Manager, System Manager | `api.property_locale` |
| Property | View performance (`view_performance`) | Finance, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `dashboards.portfolio_dashboard`, `reports.budget_vs_actual`, `reports.contribution` |
| Property | View snapshot (`view_snapshot`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Night Auditor, Revenue Manager, System Manager | `api.front_desk_snapshot` |
| Rate Plan | Configure (`configure`) | Hotel Admin, System Manager | `api.owner_briefing` |
| Rate Plan | Quote (`quote`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.booking_options`, `api.get_quote` |
| Rate Plan | Set rates (`set_rates`) | Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `api.set_room_rate` |
| Rate Plan | View rates (`view_rates`) | Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `rates.rate_calendar`, `rates.rate_options` |
| Reason Code | View codes (`view_codes`) | Finance, Front Desk, Hotel Admin, Kamra Agent, System Manager | `ledger.list_reason_codes` |
| Reservation | Check in out (`check_in_out`) | Front Desk, Hotel Admin, Kamra Agent, Night Auditor, System Manager | `api.checkin_context`, `api.check_in`, `api.check_out` and 3 more |
| Reservation | Follow instructions (`follow_instructions`) | Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, System Manager | `api.stay_instructions`, `api.set_stay_instruction_status` |
| Reservation | Guided check in (`guided_check_in`) | Front Desk, Hotel Admin, Night Auditor, System Manager | `checkin.complete_checkin_step`, `checkin.skip_checkin_step`, `checkin.save_guest_details` and 5 more |
| Reservation | Handle stays (`handle_stays`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.registration_card`, `api.waive_security_deposit`, `api.release_access_instructions` and 28 more |
| Reservation | Plan stays (`plan_stays`) | Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `allocation.suggest_allocation`, `allocation.apply_allocation`, `api.set_pays_own_charges` and 2 more |
| Reservation | Set room charges (`set_room_charges`) | Finance, Front Desk, Hotel Admin, Night Auditor, System Manager | `checkin.set_room_charges` |
| Reservation | View stays (`view_stays`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `api.find_reservations`, `api.reservation_detail` |
| Revenue Budget | Set budget (`set_budget`) | Finance, Hotel Admin, Revenue Manager, System Manager | `reports.save_budget` |
| Room | Update rooms (`update_rooms`) | Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, System Manager | `api.hk_room_media`, `api.hk_log_item`, `api.hk_post_consumable` and 1 more |
| Room | View availability (`view_availability`) | Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `api.inventory_availability` |
| Room | View board (`view_board`) | Front Desk, Hotel Admin, Housekeeping Supervisor, Kamra Agent, System Manager | `api.room_board` |
| Room | View rooms (`view_rooms`) | Finance, Front Desk, Hotel Admin, Housekeeping Supervisor, Kamra Agent, Night Auditor, Revenue Manager, System Manager | `rooms.rooms_board`, `rooms.room_detail`, `rooms.room_availability` and 2 more |
| Room | View tape (`view_tape`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.availability_calendar`, `api.tape_chart`, `api.tape_chart_hourly` |
| Room Block | Manage blocks (`manage_blocks`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.room_blocks`, `api.create_room_block`, `api.release_room_block` |
| SOP Template | Configure (`configure`) | Hotel Admin, System Manager | `sop.get_sop_template`, `sop.save_sop_template`, `sop.seed_sop_templates` |
| SOP Template | Read sops (`read_sops`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `sop.get_sop`, `sop.list_sops` |
| Security Deposit | Refund deposit (`refund_deposit`) | Finance, Front Desk, Hotel Admin, System Manager | `api.simulate_payment_link`, `api.withhold_security_deposit`, `api.refund_security_deposit` |
| Security Deposit | View refunds (`view_refunds`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.pending_deposit_refunds` |
| Service Ticket | Handle requests (`handle_requests`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `api.create_ticket`, `api.tickets_list`, `api.advance_ticket` and 1 more |
| Service Ticket | Work requests (`work_requests`) | Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, System Manager | `tickets.tickets_search`, `tickets.ticket_detail`, `tickets.ticket_assignees` and 6 more |
| Venue Booking | Bill functions (`bill_functions`) | Finance, Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `banquet.set_payment_terms`, `banquet.default_payment_terms`, `banquet.record_receipt` and 8 more |
| Venue Booking | Configure (`configure`) | Hotel Admin, System Manager | `banquet_ops.seed_banquet_checklist_templates` |
| Venue Booking | Issue indent (`issue_indent`) | Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, Revenue Manager, System Manager | `banquet.issue_indent` |
| Venue Booking | Manage functions (`manage_functions`) | Front Desk, Hotel Admin, Kamra Agent, Revenue Manager, System Manager | `api.venue_calendar`, `api.create_group_block`, `banquet.create_enquiry` and 19 more |
| Venue Booking | Reopen function (`reopen_function`) | Finance, Hotel Admin, Revenue Manager, System Manager | `banquet.reopen_function` |
| Venue Booking | View functions (`view_functions`) | Finance, Front Desk, Hotel Admin, Housekeeping, Housekeeping Supervisor, Kamra Agent, Revenue Manager, System Manager | `banquet.banquet_catalogue`, `banquet.function_sheet`, `banquet.linkable_groups` and 14 more |
| WhatsApp Message | Configure (`configure`) | Hotel Admin, System Manager | `agents_channels.channel_connections` |
| WhatsApp Message | Reply messages (`reply_messages`) | Front Desk, Hotel Admin, Kamra Agent, System Manager | `whatsapp.threads`, `whatsapp.thread`, `whatsapp.reply` |

Record access over Desk and REST (standard rights, permission level 0):

| Doctype | Role | Rights |
| --- | --- | --- |
| Agent Action Log | System Manager | read, write, create, delete, report, export |
| Agent Action Log | Hotel Admin | read, report |
| Agent Action Log | Front Desk | read, report |
| Agent Action Log | Finance | read, report |
| Agent Action Log | Kamra Agent | read, report |
| AI Assistant Settings | System Manager | read, write, create, delete, report |
| AI Assistant Settings | Hotel Admin | read, write, create, delete, report |
| Banquet Checklist Template | System Manager | read, write, create, delete, report, export |
| Banquet Checklist Template | Hotel Admin | read, write, create, delete |
| Banquet Checklist Template | Front Desk | read |
| Banquet Checklist Template | Finance | read |
| Banquet Checklist Template | Housekeeping | read |
| Banquet Checklist Template | Housekeeping Supervisor | read |
| Banquet Dish | System Manager | read, write, create, delete, report, export |
| Banquet Dish | Hotel Admin | read, write, create, delete, report, export |
| Banquet Dish | Front Desk | read, write, create, report |
| Banquet Dish | Revenue Manager | read, write, create, report |
| Banquet Dish | Finance | read, report |
| Banquet Dish | Kamra Agent | read, report |
| Banquet Function Task | System Manager | read, write, create, delete, report, export |
| Banquet Function Task | Hotel Admin | read, write, create, delete |
| Banquet Function Task | Front Desk | read, write, create |
| Banquet Function Task | Finance | read, write |
| Banquet Function Task | Housekeeping | read, write |
| Banquet Function Task | Revenue Manager | read, write |
| Banquet Function Task | Housekeeping Supervisor | read, write |
| Banquet Menu | System Manager | read, write, create, delete, report, export |
| Banquet Menu | Hotel Admin | read, write, create, delete, report, export |
| Banquet Menu | Front Desk | read, write, create, report |
| Banquet Menu | Revenue Manager | read, write, create, report |
| Banquet Menu | Finance | read, report |
| Banquet Menu | Kamra Agent | read, report |
| Banquet Service Item | System Manager | read, write, create, delete, report, export |
| Banquet Service Item | Hotel Admin | read, write, create, delete, report, export |
| Banquet Service Item | Front Desk | read, write, create, report |
| Banquet Service Item | Revenue Manager | read, write, create, report |
| Banquet Service Item | Finance | read, report |
| Banquet Service Item | Kamra Agent | read, report |
| Cancelled Invoice | System Manager | read, write, create |
| Cancelled Invoice | Hotel Admin | read |
| Cancelled Invoice | Finance | read |
| Cancelled Invoice | Front Desk | read |
| Cancelled Invoice | Kamra Agent | read |
| Cash Transfer | System Manager | read, write, create, delete, report, export |
| Cash Transfer | Hotel Admin | read, report |
| Cash Transfer | Finance | read, report |
| Cash Transfer | Front Desk | read, report |
| Cash Transfer | Kamra Agent | read, report |
| Cash Transfer | Night Auditor | read, report |
| Cashier | System Manager | read, write, create, delete, report, export |
| Cashier | Hotel Admin | read, write, create, delete, report, export |
| Cashier | Finance | read, write, create, report, export |
| Cashier | Front Desk | read, write, create, report |
| Cashier | Kamra Agent | read, write, create, report |
| Cashier PIN | System Manager | read, write, create, delete |
| Cashier Session | System Manager | read, write, create, delete, report, export |
| Cashier Session | Hotel Admin | read, report, export |
| Cashier Session | Finance | read, report, export |
| Cashier Session | Front Desk | read, report |
| Cashier Session | Kamra Agent | read, report |
| Cashier Session | Night Auditor | read, report |
| Cashier Terminal | System Manager | read, write, create, delete, report, export |
| Cashier Terminal | Hotel Admin | read, write, create, delete, report |
| Cashier Terminal | Finance | read, write, create, report |
| Cashier Terminal | Front Desk | read, report |
| Cashier Terminal | Kamra Agent | read, report |
| Cashier Terminal | Night Auditor | read, report |
| Cashier Transaction | System Manager | read, write, create, delete, report, export |
| Cashier Transaction | Hotel Admin | read, report, export |
| Cashier Transaction | Finance | read, report, export |
| Cashier Transaction | Front Desk | read, report |
| Cashier Transaction | Kamra Agent | read, report |
| Channel Manager Connection | System Manager | read, write, create, delete, report, export |
| Channel Manager Connection | Hotel Admin | read, write, create, delete, report, export |
| Channel Manager Connection | Revenue Manager | read, write, create, delete, report, export |
| Channel Manager Connection | Front Desk | read, report, export |
| Channel Manager Connection | Kamra Agent | read, write, create, delete, report, export |
| Channel Provider Connection | System Manager | read, write, create, delete, report, export |
| Channel Provider Connection | Hotel Admin | read, write, create, delete, report |
| Channel Room Mapping | System Manager | read, write, create, delete, report, export |
| Channel Room Mapping | Hotel Admin | read, write, create, delete, report, export |
| Channel Room Mapping | Revenue Manager | read, write, create, delete, report, export |
| Channel Room Mapping | Kamra Agent | read, write, create, delete, report, export |
| City Ledger Account | System Manager | read, write, create, delete, report, export |
| City Ledger Account | Hotel Admin | read, write, create, delete, report, export |
| City Ledger Account | Finance | read, write, create, report, export |
| City Ledger Account | Front Desk | read, write, create, report |
| City Ledger Account | Kamra Agent | read, write, create, report |
| City Ledger Account | Night Auditor | read, report |
| City Ledger Entry | System Manager | read, write, create, delete, report, export |
| City Ledger Entry | Hotel Admin | read, report, export |
| City Ledger Entry | Finance | read, report, export |
| City Ledger Entry | Front Desk | read, report |
| City Ledger Entry | Kamra Agent | read, report |
| Copilot Conversation | System Manager | read, write, create, delete |
| Copilot Conversation | Hotel Admin | read, write, create, delete |
| Copilot Conversation | Front Desk | read, write, create, delete |
| Copilot Conversation | Finance | read, write, create, delete |
| Copilot Conversation | Revenue Manager | read, write, create, delete |
| Copilot Conversation | Kamra Agent | read, write, create, delete |
| Corporate Account | System Manager | read, write, create, delete, report, export |
| Corporate Account | Hotel Admin | read, write, create, delete, report |
| Corporate Account | Front Desk | read, report |
| Corporate Account | Finance | read, write, create, delete, report |
| Corporate Account | Kamra Agent | read, report |
| Credit Note | System Manager | read, write, create, delete, report, export |
| Credit Note | Hotel Admin | read, report, export |
| Credit Note | Finance | read, report, export |
| Credit Note | Front Desk | read, report |
| Credit Note | Kamra Agent | read, report |
| Discount Voucher | System Manager | read, write, create, delete, report, export |
| Discount Voucher | Hotel Admin | read, write, create, delete, report |
| Discount Voucher | Front Desk | read, report |
| Discount Voucher | Revenue Manager | read, write, create, delete, report |
| Discount Voucher | Kamra Agent | read, report |
| Exchange Rate | System Manager | read, write, create, delete, report, export |
| Exchange Rate | Hotel Admin | read, write, create, delete, report, export |
| Exchange Rate | Finance | read, write, create, report, export |
| Exchange Rate | Front Desk | read, write, create, report |
| Exchange Rate | Kamra Agent | read, write, create, report |
| Exchange Transaction | System Manager | read, write, create, delete, report, export |
| Exchange Transaction | Hotel Admin | read, report, export |
| Exchange Transaction | Finance | read, report, export |
| Exchange Transaction | Front Desk | read, report |
| Exchange Transaction | Kamra Agent | read, report |
| Experience | System Manager | read, write, create, delete, report, export |
| Experience | Hotel Admin | read, write, create, delete, report |
| Experience | Front Desk | read, report |
| Experience | Revenue Manager | read, write, create, report |
| Experience | Kamra Agent | read, report |
| External POS Charge | System Manager | read, report |
| External POS Charge | Hotel Admin | read, report |
| External POS Charge | Finance | read, report |
| Folio | System Manager | read, write, create, delete, report, export |
| Folio | Hotel Admin | read, write, create, report |
| Folio | Front Desk | read, write, create, report |
| Folio | Finance | read, write, create, report |
| Folio | Kamra Agent | read, write, create, report |
| Folio | Night Auditor | read, report |
| Folio Ledger Entry | System Manager | read, write, create, delete, report, export |
| Folio Ledger Entry | Hotel Admin | read, report, export |
| Folio Ledger Entry | Finance | read, report, export |
| Folio Ledger Entry | Front Desk | read, report |
| Folio Ledger Entry | Kamra Agent | read, report |
| Folio Reprint | System Manager | read, write, create, delete, report, export |
| Folio Reprint | Hotel Admin | read, report, export |
| Folio Reprint | Finance | read, report, export |
| Folio Reprint | Front Desk | read, report |
| Folio Reprint | Kamra Agent | read, report |
| Group Booking | System Manager | read, write, create, delete, report, export |
| Group Booking | Hotel Admin | read, write, create, delete, report |
| Group Booking | Front Desk | read, write, create, report |
| Group Booking | Finance | read, report |
| Group Booking | Kamra Agent | read, write, create, report |
| Guest | System Manager | read, write, create, delete, report, export |
| Guest | Hotel Admin | read, write, create, delete, report |
| Guest | Front Desk | read, write, create, report |
| Guest | Finance | read, report |
| Guest | Kamra Agent | read, write, create, report |
| Guest | Night Auditor | read, report |
| Hosting Enquiry | System Manager | read, write, create, delete, report, export |
| Housekeeping Task | System Manager | read, write, create, delete, report, export |
| Housekeeping Task | Hotel Admin | read, write, create, delete, report |
| Housekeeping Task | Front Desk | read, write, create, report |
| Housekeeping Task | Housekeeping | read, write, report |
| Housekeeping Task | Kamra Agent | read, write, create, report |
| Housekeeping Task | Housekeeping Supervisor | read, write, create, report |
| Hurdle Rate | System Manager | read, write, create, delete, report, export |
| Hurdle Rate | Hotel Admin | read, write, create, delete, report |
| Hurdle Rate | Front Desk | read, write, create, report |
| Hurdle Rate | Finance | read, report |
| Hurdle Rate | Kamra Agent | read, write, create, report |
| Ingredient | System Manager | read, write, create, delete, report, export |
| Ingredient | Hotel Admin | read, write, create, delete, report |
| Ingredient | Finance | read, write, create, delete, report |
| Ingredient | Front Desk | read, report |
| Ingredient | Kamra Agent | read, report |
| Ingredient Ledger Entry | System Manager | read, report, export |
| Ingredient Ledger Entry | Hotel Admin | read, report |
| Ingredient Ledger Entry | Finance | read, report |
| Ingredient Ledger Entry | Front Desk | read, report |
| Ingredient Ledger Entry | Kamra Agent | read, report |
| Ingredient Stock | System Manager | read, report, export |
| Ingredient Stock | Hotel Admin | read, report |
| Ingredient Stock | Finance | read, report |
| Ingredient Stock | Front Desk | read, report |
| Ingredient Stock | Kamra Agent | read, report |
| Kamra Connect Settings | System Manager | read, write |
| Kamra Connect Settings | Hotel Admin | read, write |
| Kamra Custom Report | System Manager | read, write, create, delete, report |
| Kamra Custom Report | Hotel Admin | read, write, create, delete, report |
| Kamra Custom Report | Finance | read, write, create, delete, report |
| Kamra Custom Report | Front Desk | read |
| Kamra Custom Report | Revenue Manager | read |
| Kitchen Printer | System Manager | read, write, create, delete, report, export |
| Kitchen Printer | Hotel Admin | read, write, create, delete, report, export |
| Kitchen Printer | Finance | read, write, create, report |
| Kitchen Printer | Front Desk | read, report |
| Kitchen Printer | Kamra Agent | read, report |
| Kitchen Printer | Night Auditor | read, report |
| Laundry Order | System Manager | read, write, create, delete, report, export |
| Laundry Order | Hotel Admin | read, write, create, delete, report |
| Laundry Order | Front Desk | read, write, create, report |
| Laundry Order | Finance | read, report |
| Laundry Order | Kamra Agent | read, write, create, report |
| Laundry Order | Housekeeping | read, write, create, report |
| Laundry Order | Housekeeping Supervisor | read, write, create, report |
| Laundry Rate | System Manager | read, write, create, delete, report, export |
| Laundry Rate | Hotel Admin | read, write, create, delete, report |
| Laundry Rate | Front Desk | read, write, create, report |
| Laundry Rate | Finance | read, report |
| Laundry Rate | Kamra Agent | read, write, create, report |
| Laundry Rate | Housekeeping | read, write, create, report |
| Laundry Rate | Housekeeping Supervisor | read, write, create, report |
| Lost And Found Item | System Manager | read, write, create, delete, report, export |
| Lost And Found Item | Hotel Admin | read, write, create, delete, report |
| Lost And Found Item | Front Desk | read, write, create, delete, report |
| Lost And Found Item | Housekeeping | read, write, create, report |
| Lost And Found Item | Kamra Agent | read, write, create, report |
| Lost And Found Item | Housekeeping Supervisor | read, write, create, report |
| MCP OAuth Client | System Manager | read, write, create, delete |
| MCP OAuth Grant | System Manager | read, write, create, delete |
| Meal Plan | System Manager | read, write, create, delete, report, export |
| Meal Plan | Hotel Admin | read, write, create, delete, report |
| Meal Plan | Front Desk | read, report |
| Meal Plan | Revenue Manager | read, write, create, delete, report |
| Meal Plan | Kamra Agent | read, report |
| Menu Item | System Manager | read, write, create, delete, report, export |
| Menu Item | Hotel Admin | read, write, create, delete, report |
| Menu Item | Front Desk | read, report |
| Menu Item | Finance | read, write, create, report |
| Menu Item | Kamra Agent | read, report |
| Night Audit Log | System Manager | read, write, create, delete, report, export |
| Night Audit Log | Hotel Admin | read, report, export |
| Night Audit Log | Finance | read, report, export |
| Night Audit Log | Night Auditor | read, report, export |
| Night Audit Run | System Manager | read, write, create, delete, report, export |
| Night Audit Run | Hotel Admin | read, report |
| Night Audit Run | Front Desk | read, report |
| Night Audit Run | Finance | read, report |
| Night Audit Run | Kamra Agent | read, report |
| Night Audit Run | Night Auditor | read, report |
| Outbound Webhook | System Manager | read, write, create, delete, report |
| Outbound Webhook | Hotel Admin | read, write, create, delete, report |
| Outbound Webhook Delivery | System Manager | read, delete, report |
| Outbound Webhook Delivery | Hotel Admin | read, report |
| Payment Gateway Settings | System Manager | read, write, create, delete, report, export |
| Payment Gateway Settings | Hotel Admin | read, write, create, delete, report |
| Petty Cash Voucher | System Manager | read, write, create, delete, report, export |
| Petty Cash Voucher | Hotel Admin | read, report, export |
| Petty Cash Voucher | Finance | read, report, export |
| Petty Cash Voucher | Front Desk | read, report |
| Petty Cash Voucher | Kamra Agent | read, report |
| POS Order | System Manager | read, write, create, delete, report, export |
| POS Order | Hotel Admin | read, write, create, delete, report |
| POS Order | Front Desk | read, write, create, report |
| POS Order | Finance | read, report |
| POS Order | Kamra Agent | read, write, create, report |
| POS Order | Night Auditor | read, report |
| POS Outlet | System Manager | read, write, create, delete, report, export |
| POS Outlet | Hotel Admin | read, write, create, delete, report |
| POS Outlet | Front Desk | read, report |
| POS Outlet | Finance | read, write, create, report |
| POS Outlet | Kamra Agent | read, report |
| POS Outlet | Night Auditor | read, report |
| POS Table Reservation | System Manager | read, write, create, delete, report, export |
| POS Table Reservation | Hotel Admin | read, write, create, delete, report |
| POS Table Reservation | Front Desk | read, write, create, report |
| POS Table Reservation | Finance | read, report |
| POS Table Reservation | Kamra Agent | read, write, create, report |
| Print Job | System Manager | read, write, create, delete, report, export |
| Print Job | Hotel Admin | read, delete, report |
| Print Job | Finance | read, report |
| Print Job | Front Desk | read, report |
| Proforma Folio | System Manager | read, write, create, delete, report, export |
| Proforma Folio | Hotel Admin | read, report, export |
| Proforma Folio | Finance | read, report, export |
| Proforma Folio | Front Desk | read, report |
| Proforma Folio | Kamra Agent | read, report |
| Property | System Manager | read, write, create, delete, report, export |
| Property | Hotel Admin | read, write, create, delete, report |
| Property | Front Desk | read, report |
| Property | Finance | read, report |
| Property | Revenue Manager | read, report |
| Property | Housekeeping | read, report |
| Property | Kamra Agent | read, report |
| Property | Housekeeping Supervisor | read, report |
| Property | Night Auditor | read, report |
| Property Setting | System Manager | read, write, create, delete, report |
| Property Setting | Hotel Admin | read, report |
| Rate Guardrail | System Manager | read, write, create, delete, report, export |
| Rate Guardrail | Hotel Admin | read, write, create, delete, report |
| Rate Guardrail | Revenue Manager | read, report |
| Rate Guardrail | Kamra Agent | read, report |
| Rate Plan | System Manager | read, write, create, delete, report, export |
| Rate Plan | Hotel Admin | read, write, create, delete, report |
| Rate Plan | Front Desk | read, report |
| Rate Plan | Revenue Manager | read, write, create, delete, report |
| Rate Plan | Kamra Agent | read, report |
| Reason Code | System Manager | read, write, create, delete, report, export |
| Reason Code | Hotel Admin | read, write, create, delete, report, export |
| Reason Code | Finance | read, write, create, report, export |
| Reason Code | Front Desk | read, write, create, report |
| Reason Code | Kamra Agent | read, write, create, report |
| Reservation | System Manager | read, write, create, delete, report, export |
| Reservation | Hotel Admin | read, write, create, delete, report |
| Reservation | Front Desk | read, write, create, report |
| Reservation | Finance | read, report |
| Reservation | Revenue Manager | read, report |
| Reservation | Housekeeping | read, report |
| Reservation | Kamra Agent | read, write, create, report |
| Reservation | Housekeeping Supervisor | read, report |
| Reservation | Night Auditor | read, report |
| Revenue Budget | System Manager | read, write, create, delete |
| Revenue Budget | Hotel Admin | read, write, create, delete |
| Revenue Budget | Revenue Manager | read, write, create, delete |
| Revenue Budget | Finance | read, write, create |
| Room | System Manager | read, write, create, delete, report, export |
| Room | Hotel Admin | read, write, create, delete, report |
| Room | Front Desk | read, write, create, report |
| Room | Housekeeping | read, write, report |
| Room | Revenue Manager | read, report |
| Room | Finance | read, report |
| Room | Kamra Agent | read, write, report |
| Room | Housekeeping Supervisor | read, write, report |
| Room | Night Auditor | read, report |
| Room Block | System Manager | read, write, create, delete, report, export |
| Room Block | Hotel Admin | read, write, create, delete, report |
| Room Block | Front Desk | read, write, create, report |
| Room Block | Kamra Agent | read, report |
| Room Type | System Manager | read, write, create, delete, report, export |
| Room Type | Hotel Admin | read, write, create, delete, report |
| Room Type | Front Desk | read, report |
| Room Type | Revenue Manager | read, write, create, report |
| Room Type | Housekeeping | read, report |
| Room Type | Kamra Agent | read, report |
| Room Type | Housekeeping Supervisor | read, report |
| Room Type | Night Auditor | read, report |
| Season | System Manager | read, write, create, delete, report, export |
| Season | Hotel Admin | read, write, create, delete, report |
| Season | Front Desk | read, report |
| Season | Revenue Manager | read, write, create, delete, report |
| Season | Kamra Agent | read, report |
| Security Deposit | System Manager | read, write, create, delete |
| Security Deposit | Hotel Admin | read |
| Security Deposit | Front Desk | read |
| Security Deposit | Finance | read |
| Security Deposit | Kamra Agent | read |
| Sellable Unit | System Manager | read, write, create, delete, report, export |
| Sellable Unit | Hotel Admin | read, write, create, delete, report |
| Sellable Unit | Front Desk | read, write, report |
| Sellable Unit | Revenue Manager | read, write, report |
| Sellable Unit | Kamra Agent | read, write, report |
| Sellable Unit | Housekeeping | read, report |
| Sellable Unit | Housekeeping Supervisor | read, report |
| Service Ticket | System Manager | read, write, create, delete, report, export |
| Service Ticket | Hotel Admin | read, write, create, delete, report |
| Service Ticket | Front Desk | read, write, create, report |
| Service Ticket | Housekeeping | read, write, report |
| Service Ticket | Kamra Agent | read, write, create, report |
| Service Ticket | Housekeeping Supervisor | read, write, report |
| Shift Handover | System Manager | read, write, create, delete, report, export |
| Shift Handover | Hotel Admin | read, write, create, delete, report |
| Shift Handover | Front Desk | read, write, create, report |
| Shift Handover | Finance | read, report |
| Shift Handover | Kamra Agent | read, report |
| SOP Template | System Manager | read, write, create, delete, report |
| SOP Template | Hotel Admin | read, write, create, report |
| SOP Template | Front Desk | read |
| Ticket Event | System Manager | read, write, create, delete, report, export |
| Ticket Event | Hotel Admin | read, report |
| Ticket Event | Front Desk | read, report |
| Ticket Event | Housekeeping | read |
| Ticket Event | Housekeeping Supervisor | read |
| Ticket Event | Kamra Agent | read |
| Transaction Code | System Manager | read, write, create, delete, report, export |
| Transaction Code | Hotel Admin | read, write, create, delete, report, export |
| Transaction Code | Finance | read, write, create, report, export |
| Transaction Code | Front Desk | read, write, create, report |
| Transaction Code | Kamra Agent | read, write, create, report |
| Travel Agent | System Manager | read, write, create, delete, report, export |
| Travel Agent | Hotel Admin | read, write, create, delete, report |
| Travel Agent | Front Desk | read, report |
| Travel Agent | Revenue Manager | read, write, create, delete, report |
| Travel Agent | Kamra Agent | read, report |
| Turnover Profile | System Manager | read, write, create, delete |
| Turnover Profile | Hotel Admin | read, write, create, delete |
| Turnover Profile | Housekeeping | read, write |
| Turnover Profile | Front Desk | read |
| Turnover Profile | Housekeeping Supervisor | read, write |
| Venue | System Manager | read, write, create, delete, report, export |
| Venue | Hotel Admin | read, write, create, delete, report |
| Venue | Front Desk | read, write, create, report |
| Venue | Kamra Agent | read, report |
| Venue Booking | System Manager | read, write, create, delete, report, export |
| Venue Booking | Hotel Admin | read, write, create, delete, report |
| Venue Booking | Front Desk | read, write, create, report |
| Venue Booking | Kamra Agent | read, write, create, report |
| WhatsApp Message | System Manager | read, write, create, delete, report, export |
| WhatsApp Message | Hotel Admin | read, write, create, delete, report, export |
| WhatsApp Message | Front Desk | read, write, create, report, export |
| WhatsApp Message | Kamra Agent | read, write, create, report, export |
| WhatsApp Message | Finance | read, report, export |
| ZATCA Invoice | System Manager | read, write, create |
| ZATCA Invoice | Hotel Admin | read |
| ZATCA Invoice | Finance | read, report, export |
| ZATCA Invoice | Front Desk | read |
| ZATCA Settings | System Manager | read, write, create, delete |
| ZATCA Settings | Hotel Admin | read, write, create |
| ZATCA Settings | Finance | read |
<!-- permissions:end -->
