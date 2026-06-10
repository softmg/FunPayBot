export function formatPrice(price: string | null): string {
  if (!price) {
    return "Неизвестно";
  }

  const numeric = Number(price.replace(/\s/g, "").replace(",", "."));
  if (!Number.isFinite(numeric)) {
    return price;
  }

  return `${new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(numeric)} ₽`;
}
