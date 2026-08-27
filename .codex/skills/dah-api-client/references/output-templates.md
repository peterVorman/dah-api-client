# Output Templates

Use these shapes for concise, stable answers.

## Current Debt

```text
Станом на зараз:
- Квартири: <count>, <amount> грн
- Нежитлові: <count>, <amount> грн
- Разом: <amount> грн

Найбільший вплив:
1. <label>: <amount> грн
2. <label>: <amount> грн

Висновок: <one concrete operational conclusion>.
```

## Dynamics

```text
Динаміка за <period>:
- Було: <amount> грн
- Стало: <amount> грн
- Зміна: <signed amount> грн

Основний рух: <apartments/premises/none>.
```

## Entrance/Floor Analysis

```text
Боргове навантаження з урахуванням площі:
1. <entrance>: <amount> грн, <amount/m2> грн/м²
2. <entrance>: <amount> грн, <amount/m2> грн/м²

Окремо: Без підʼїзду — <amount> грн, <amount/m2> грн/м².
```

## Notification Preview

```text
Готові до повідомлення:
1. <label>: <debt> грн, канал <method>, отримувачі <scope>, кількість <n>

Не показую raw userId/tenantId/контакти. Для відправки потрібен апрув.
```

## Send Result

```text
Відправлено: <count>
- <label>: <recipient count> отримувачів, канал <method>

Пропущено: <count>
- <label>: <reason>
```

## Single Debtor Audit

```text
<label>:
- Поточний борг: <amount> грн
- Повідомлень у ledger: <records>, дат: <unique dates>
- Останній контакт: <date/status/method>
- Оплати за період: <amount> грн

Висновок: <payment found/not found and next action>.
```
