# 简体中文术语表（Kamra PMS）

本文件是 `frontend/src/i18n/locales/zh-CN.json` 与 `kamra/translations/zh.csv` 译文的**强制对照表**。
新增或修改译文前先查这里；表中没有的词，先补表再用。同一个英文词只能有一种译法，
语境确实不同时使用项目既有的 `sense|` 前缀机制（见文末）。

## 一、核心业务术语（基线）

| English | 简体中文 | 说明 |
|---|---|---|
| Dashboard | 仪表盘 | 首页概览 |
| Front Desk | 前台 | 模块名 |
| Reservation | 预订 | 名词；动作"预订"同形 |
| Booking | 预订 | 与 Reservation 同译，避免出现两套说法 |
| Check-in | 入住 | 名词/动作；"办理入住"用于按钮/流程标题 |
| Check-out | 退房 | 名词/动作；"办理退房"用于按钮/流程标题 |
| Room Status | 房态 | |
| Available | 空闲 | 可售房间状态 |
| Occupied | 已入住 | 有客人在住 |
| Vacant | 空置 | 无人入住 |
| Dirty | 待清洁 | 客房清洁状态 |
| Clean | 已清洁 | |
| Inspected | 已检查 | 主管查房通过 |
| Out of Order | 停用 | 维修/不可售 |
| Housekeeping | 客房清洁 | 模块名；指团队时可写"客房部" |
| Night Audit | 夜审 | 日结流程 |
| Folio | 客账 | 一位客人的账单；不译作"账单"以免与 Invoice 混淆 |
| Folio charge | 客账费用 | 入账到客账的一笔消费 |
| Folio payment | 客账收款 | 客账上的一笔收款 |
| Deposit | 押金 | 预订/入住押金 |
| Security deposit | 押金 | 与 Deposit 统一 |
| Advance | 预付款 | 提前支付的房费 |
| Refund | 退款 | |
| No-show | 未到店 | 预订未入住 |
| Walk-in | 散客入住 | 无预订直接入住 |
| Room Type | 房型 | |
| Room | 客房 | 具体房号 |
| Room Charge | 房费 | 客账行项目 |
| ADR | 平均每日房价 | 首次出现可写"平均每日房价（ADR）" |
| RevPAR | 每间可售房收入 | 同上，首次出现附缩写 |

## 二、房态日历与预订流程

| English | 简体中文 | 说明 |
|---|---|---|
| Tape Chart | 房态日历 | 拖拽式房态/预订日历 |
| Calendar | 日历 | |
| Arrival | 到店 | 当日预计到店 |
| Departure | 离店 | 当日预计离店 |
| In-house | 在住 | 在住客人列表 |
| Stay | 住店 | 一段住宿；"住宿"用于描述性文字 |
| Rooming List | 分房单 | 团队分房 |
| Group Booking | 团队预订 | |
| Room Block | 预留房 | 团队锁房 |
| Room Change | 换房 | |
| Upgrade | 升级房型 | |
| Day Use | 日用房 | 当日入住当日退房 |
| Early Check-out | 提前退房 | |
| Late Check-out | 延迟退房 | |
| Overbooking | 超订 | |
| Rate Plan | 价格方案 | 不译作"房价计划" |
| Season | 季节价 | 价格调整规则 |
| Guardrail | 价格护栏 | 业主设定的价格上下限 |
| Meal Plan | 餐食方案 | EP/CP/MAP/AP 缩写保留英文 |
| Voucher | 优惠券 | 折扣券 |
| Occupancy | 入住率 | 百分比指标 |
| Business Date | 营业日 | 夜审推进的日期 |

## 三、账单、收银与财务

| English | 简体中文 | 说明 |
|---|---|---|
| Billing | 账单 | 模块名 |
| Bill | 账单 | 单张账单 |
| Invoice | 发票 | 正式发票 |
| Tax Invoice | 税务发票 | |
| Receipt | 收据 | 收款凭证 |
| Post | 入账 | 动词：把消费记到客账 |
| Void | 作废 | 作废一笔入账/账单 |
| Settle | 结账 | 结清余额 |
| Close Folio | 关闭客账 | |
| Split Billing | 分账 | 一笔消费拆到多个客账 |
| Routed Billing | 转账结算 | 公司付房费、客人付其他 |
| Balance | 余额 | |
| Balance Due | 应收余额 | 客账上待收金额 |
| Due | 应收 | |
| Payable | 应付 | |
| Receivable | 应收 | |
| Aging | 账龄 | 应收逾期分析 |
| Statement | 对账单 | 企业客户对账单 |
| City Ledger | 应收账户 | 企业挂账 |
| Corporate Account | 企业账户 | |
| Cashier | 收银员 | |
| Till | 钱箱 | 收银台现金抽屉 |
| Cashier Shift | 收银班次 | |
| Shift Handover | 交接班 | |
| Petty Cash | 备用金 | |
| Currency Desk | 货币兑换台 | |
| Taxable Value | 应税金额 | |
| Service Charge | 服务费 | |
| Municipality Fee | 市政费 | 部分国家的地方税 |
| GST | 商品及服务税（GST） | 印度税种，缩写保留 |
| VAT | 增值税（VAT） | 缩写保留 |
| Night Audit Blocker | 夜审阻断项 | 阻止日结的未处理事项 |

## 四、餐饮、宴会与运营

| English | 简体中文 | 说明 |
|---|---|---|
| Outlet | 营业点 | 餐厅/酒吧等销售点 |
| POS | 餐饮收银 | 模块名 |
| KOT | 厨房单（KOT） | 缩写保留 |
| Kitchen Display | 厨房显示屏 | |
| Menu Item | 菜单项 | |
| Recipe | 配方 | |
| Stock | 库存 | |
| Laundry | 洗衣 | |
| Minibar | 迷你吧 | |
| Lost & Found | 失物招领 | |
| Housekeeping Task | 客房任务 | |
| Room Board | 房态看板 | 主管视图 |
| Service Ticket | 服务工单 | 维修/客需工单 |
| Banquet | 宴会 | |
| BEO | 宴会执行单（BEO） | 缩写保留 |
| Venue | 场地 | |
| Venue Booking | 场地预订 | |
| GRC | 入住登记卡（GRC） | 缩写保留 |
| Guest Request | 客需 | |

## 五、通用界面词

| English | 简体中文 | 说明 |
|---|---|---|
| Save | 保存 | 按钮 |
| Cancel | 取消 | 按钮 |
| Delete | 删除 | 按钮 |
| Remove | 移除 | 从列表中拿掉，不删除记录 |
| Edit | 编辑 | 按钮 |
| Add | 添加 | 按钮 |
| New | 新建 | |
| Confirm | 确认 | 按钮 |
| Close | 关闭 | 按钮/窗口 |
| Back | 返回 | |
| Next | 下一步 | |
| Done | 完成 | |
| Search | 搜索 | |
| Filter | 筛选 | |
| All | 全部 | 筛选项 |
| None | 无 | |
| From / To | 从 / 到 | 日期范围 |
| Status | 状态 | 表格列名 |
| Action | 操作 | 表格列名 |
| Amount | 金额 | |
| Date | 日期 | |
| Time | 时间 | |
| Total | 合计 | |
| Subtotal | 小计 | |
| Notes | 备注 | |
| Reason | 原因 | |
| Required | 必填 | 校验提示 |
| Loading… | 加载中… | |
| No results | 无匹配结果 | 空状态 |
| Nothing here yet | 暂无内容 | 空状态 |
| Are you sure? | 确定继续吗？ | 确认弹窗 |

## 六、模块与角色

| English | 简体中文 | 说明 |
|---|---|---|
| Property | 酒店 | 多酒店场景用"物业"容易误解，统一"酒店" |
| Revenue Management | 收益管理 | |
| Reports | 报表 | |
| Settings | 设置 | |
| Users | 用户 | |
| Roles & Permissions | 角色与权限 | |
| Notifications | 消息通知 | |
| Guest | 客人 | |
| Staff | 员工 | |
| Hotel Admin | 酒店管理员 | 角色名 |
| Front Desk (role) | 前台 | 角色名 |
| Finance | 财务 | 角色名 |
| Revenue Manager | 收益经理 | 角色名 |
| System Manager | 系统管理员 | 角色名 |
| Kamra Agent | Kamra 智能助手 | 产品名 Kamra 保留 |

## 七、书写规则

1. **占位符原样保留**：`{n}`、`{0}`、`{name}` 不翻译、不增删、不改大小写；中文语序需要调整时移动整个占位符。
2. **中英文之间加空格**（如 `房号 101`、`GST 税率`），数字与中文之间同样加空格（`3 间夜`）。
3. **标点**：句子用中文全角标点（，。：；！？）；括号用全角（），但其中是英文/代码时用半角 `()` 并保留空格。
4. **不加句号**：标题、按钮、菜单、表格列名、标签不加句末句号；完整句子（提示、说明、校验信息）跟随原文，原文有句号才加。
5. **按钮用动词短语**，标题用名词短语，说明文字用完整句。
6. **复数**：中文不分单复数，`tn()` 的两个英文 key（`{n} night` / `{n} nights`）译成同一形态（`{n} 间夜`）。
7. **不翻译**：API 字段名、枚举值、房号、客人姓名、订单号/发票号、货币代码（INR/USD/EUR）、品牌名 Kamra、行业缩写 EP/CP/MAP/AP、KOT、BEO、GRC、GST、VAT、ADR、RevPAR（首次出现可加中文注释）。
8. **金额与日期**：金额格式由后端 `ui_locale` 决定，译文不改货币符号；日期/时间走 `Intl` 的 `zh-CN`，译文不手写日期格式。
9. **同一英文一词一译**。语境确实冲突时用 `sense|` 前缀把词义写进 key：
   ```
   t("Open")            按钮：打开
   t("open|Open")       状态：开放/进行中
   ```
   `sense|` 前缀只在英文原文里出现，翻译后自动去掉前缀（见 `frontend/src/lib/i18n.ts`）。

### 一词多义（判定为"一致"，不要按同形词强行统一）

同一个英文词在下列语境里保留两种译法，核查术语一致性时不算偏差：

| English | 语境 A | 语境 B |
|---|---|---|
| Voucher | 营销折扣码 → 优惠券（Discount Voucher） | 备用额/收付款凭证 → 凭证（Allowance Voucher、voucher numbers） |
| Housekeeping | 职能/流程 → 客房清洁 | 团队/部门 → 客房部（"客房部会看到…"） |
| Refund | 名词 → 退款（a refund） | 动词 → 退还（refund the rest） |
| Occupied | 状态标签 → 已入住 | 后接数字的计数 → 间（`{occupied} 间`、`{pct}% 入住率`） |
| Inspected | 状态标签 → 已检查 | 被动动作 → 检查（"由 {who} 检查"） |
| Invoice | 单据 → 发票 | 动作 → 开票（Direct invoice 直接开票） |
| Balance | 账户余额 → 余额 | 报表名 → 试算平衡（trial balance）、资产负债表（balance sheet） |
| Room charge | 客账行项 → 房费 | 入账动作 → 客房入账（最大客房入账） |
| Guest | 具体客人 → 客人 | 占位符无名词时省略（`{guest} · 退房或打开登记`） |

`Folio Charge.charge_type` 这类字段/类名原样保留，不翻译。

## 八、维护流程

```bash
cd frontend
node scripts/i18n-extract.mjs          # 重建 catalog.csv（合并全部 locale）
npm run i18n:coverage                  # 看每个语言的覆盖率
node scripts/i18n-coverage.mjs --missing zh-CN   # 列出中文缺失的 key
node scripts/i18n-import.mjs --lang zh-CN --column chinese   # 从 catalog 导入译文
```

- 译文写进 `catalog.csv` 的 `chinese` 列，再用 `i18n-import` 生成 `zh-CN.json`，
  保证 catalog 与字典一致；直接改 JSON 也可以，但下一次 import 会以 catalog 为准。
- 后端词条在 `kamra/translations/zh.csv`（`source,translation`），源字符串必须与
  代码里 `_("…")`/`frappe._("…")` 的英文逐字一致，`{0}` 占位符原样保留。
