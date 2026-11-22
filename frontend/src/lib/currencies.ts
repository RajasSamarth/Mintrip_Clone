/**
 * Shared Currency utilities and exchange rates.
 * Default currency is INR (₹) across the MindTrip application.
 */

export interface Currency {
  code: string;
  symbol: string;
  label: string;
  rateFromUSD: number; // 1 USD = rateFromUSD units
  rateFromINR: number; // 1 INR = rateFromINR units
}

export const CURRENCIES: Record<string, Currency> = {
  INR: { code: "INR", symbol: "₹", label: "Indian Rupee", rateFromUSD: 85.0, rateFromINR: 1.0 },
  USD: { code: "USD", symbol: "$", label: "US Dollar", rateFromUSD: 1.0, rateFromINR: 1 / 85.0 },
  EUR: { code: "EUR", symbol: "€", label: "Euro", rateFromUSD: 0.92, rateFromINR: 0.92 / 85.0 },
  GBP: { code: "GBP", symbol: "£", label: "British Pound", rateFromUSD: 0.78, rateFromINR: 0.78 / 85.0 },
  AED: { code: "AED", symbol: "AED", label: "United Arab Emirates Dirham", rateFromUSD: 3.67, rateFromINR: 3.67 / 85.0 },
  JPY: { code: "JPY", symbol: "¥", label: "Japanese Yen", rateFromUSD: 152.0, rateFromINR: 152.0 / 85.0 },
  CAD: { code: "CAD", symbol: "CA$", label: "Canadian Dollar", rateFromUSD: 1.39, rateFromINR: 1.39 / 85.0 },
  AUD: { code: "AUD", symbol: "AU$", label: "Australian Dollar", rateFromUSD: 1.52, rateFromINR: 1.52 / 85.0 },
  SGD: { code: "SGD", symbol: "S$", label: "Singapore Dollar", rateFromUSD: 1.33, rateFromINR: 1.33 / 85.0 },
  CHF: { code: "CHF", symbol: "CHF", label: "Swiss Franc", rateFromUSD: 0.88, rateFromINR: 0.88 / 85.0 },
  CNY: { code: "CNY", symbol: "¥", label: "Chinese Yuan", rateFromUSD: 7.23, rateFromINR: 7.23 / 85.0 },
  THB: { code: "THB", symbol: "฿", label: "Thai Baht", rateFromUSD: 34.6, rateFromINR: 34.6 / 85.0 },
  MYR: { code: "MYR", symbol: "RM", label: "Malaysian Ringgit", rateFromUSD: 4.45, rateFromINR: 4.45 / 85.0 },
  IDR: { code: "IDR", symbol: "Rp", label: "Indonesian Rupiah", rateFromUSD: 15850.0, rateFromINR: 15850.0 / 85.0 },
  SAR: { code: "SAR", symbol: "SAR", label: "Saudi Riyal", rateFromUSD: 3.75, rateFromINR: 3.75 / 85.0 },
  QAR: { code: "QAR", symbol: "QAR", label: "Qatari Riyal", rateFromUSD: 3.64, rateFromINR: 3.64 / 85.0 },
  KWD: { code: "KWD", symbol: "KD", label: "Kuwaiti Dinar", rateFromUSD: 0.31, rateFromINR: 0.31 / 85.0 },
  BHD: { code: "BHD", symbol: "BD", label: "Bahraini Dinar", rateFromUSD: 0.38, rateFromINR: 0.38 / 85.0 },
  OMR: { code: "OMR", symbol: "OMR", label: "Omani Rial", rateFromUSD: 0.385, rateFromINR: 0.385 / 85.0 },
  NZD: { code: "NZD", symbol: "NZ$", label: "New Zealand Dollar", rateFromUSD: 1.68, rateFromINR: 1.68 / 85.0 },
  ZAR: { code: "ZAR", symbol: "R", label: "South African Rand", rateFromUSD: 17.6, rateFromINR: 17.6 / 85.0 },
  BRL: { code: "BRL", symbol: "R$", label: "Brazilian Real", rateFromUSD: 5.78, rateFromINR: 5.78 / 85.0 },
  MXN: { code: "MXN", symbol: "Mex$", label: "Mexican Peso", rateFromUSD: 20.2, rateFromINR: 20.2 / 85.0 },
  TRY: { code: "TRY", symbol: "₺", label: "Turkish Lira", rateFromUSD: 34.3, rateFromINR: 34.3 / 85.0 },
  KRW: { code: "KRW", symbol: "₩", label: "South Korean Won", rateFromUSD: 1380.0, rateFromINR: 1380.0 / 85.0 },
  HKD: { code: "HKD", symbol: "HK$", label: "Hong Kong Dollar", rateFromUSD: 7.78, rateFromINR: 7.78 / 85.0 },
  SEK: { code: "SEK", symbol: "kr", label: "Swedish Krona", rateFromUSD: 10.7, rateFromINR: 10.7 / 85.0 },
  NOK: { code: "NOK", symbol: "kr", label: "Norwegian Krone", rateFromUSD: 10.9, rateFromINR: 10.9 / 85.0 },
  DKK: { code: "DKK", symbol: "kr", label: "Danish Krone", rateFromUSD: 6.87, rateFromINR: 6.87 / 85.0 },
  PLN: { code: "PLN", symbol: "zł", label: "Polish Zloty", rateFromUSD: 4.02, rateFromINR: 4.02 / 85.0 },
  PHP: { code: "PHP", symbol: "₱", label: "Philippine Peso", rateFromUSD: 58.4, rateFromINR: 58.4 / 85.0 },
  VND: { code: "VND", symbol: "₫", label: "Vietnamese Dong", rateFromUSD: 25300.0, rateFromINR: 25300.0 / 85.0 },
  EGP: { code: "EGP", symbol: "E£", label: "Egyptian Pound", rateFromUSD: 49.1, rateFromINR: 49.1 / 85.0 },
  ILS: { code: "ILS", symbol: "₪", label: "Israeli New Shekel", rateFromUSD: 3.73, rateFromINR: 3.73 / 85.0 },
  LKR: { code: "LKR", symbol: "Rs", label: "Sri Lankan Rupee", rateFromUSD: 293.0, rateFromINR: 293.0 / 85.0 },
  PKR: { code: "PKR", symbol: "Rs", label: "Pakistani Rupee", rateFromUSD: 278.0, rateFromINR: 278.0 / 85.0 },
  BDT: { code: "BDT", symbol: "৳", label: "Bangladeshi Taka", rateFromUSD: 119.5, rateFromINR: 119.5 / 85.0 },
  NPR: { code: "NPR", symbol: "Rs", label: "Nepalese Rupee", rateFromUSD: 136.0, rateFromINR: 136.0 / 85.0 },
};

export function formatPriceInCurrency(
  amount: number,
  currencyCode: string = "INR"
): string {
  const curr = CURRENCIES[currencyCode] || CURRENCIES.INR;
  if (currencyCode === "INR") {
    return `${curr.symbol} ${Math.round(amount).toLocaleString("en-IN")}`;
  }
  return `${curr.symbol} ${Math.round(amount).toLocaleString("en-US")}`;
}

export function convertAmount(
  amount: number,
  fromCode: string,
  toCode: string
): number {
  if (fromCode === toCode) return amount;
  const from = CURRENCIES[fromCode] || CURRENCIES.INR;
  const to = CURRENCIES[toCode] || CURRENCIES.INR;

  // Convert to USD first as intermediate
  let inUSD = amount;
  if (fromCode === "INR") {
    inUSD = amount / 85.0;
  } else if (from.rateFromUSD > 0) {
    inUSD = amount / from.rateFromUSD;
  }

  // Convert USD to target currency
  if (toCode === "INR") {
    return inUSD * 85.0;
  }
  return inUSD * to.rateFromUSD;
}

export function formatFlightPriceDisplay(
  flight: { price_inr?: number; price_usd?: number; currency?: string; selected_currency?: string },
  targetCurrency: string = "INR"
): string {
  const curr = CURRENCIES[targetCurrency] || CURRENCIES.INR;
  const inr = flight.price_inr;
  const usd = flight.price_usd;

  if (targetCurrency === "INR") {
    const val = inr != null && inr > 0 ? inr : (usd ? usd * 85.0 : 0);
    return `${curr.symbol} ${Math.round(val).toLocaleString("en-IN")}`;
  }

  if (targetCurrency === "USD") {
    const val = usd != null && usd > 0 ? usd : (inr ? inr / 85.0 : 0);
    return `${curr.symbol}${Math.round(val).toLocaleString("en-US")}`;
  }

  // Other currencies: convert from USD
  const baseUSD = usd != null && usd > 0 ? usd : (inr ? inr / 85.0 : 0);
  const converted = baseUSD * curr.rateFromUSD;
  return `${curr.symbol} ${Math.round(converted).toLocaleString("en-US")}`;
}
