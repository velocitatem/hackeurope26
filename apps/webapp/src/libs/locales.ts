import commonEn from '@/locales/en/common.json';

type LocaleCommon = typeof commonEn;
type LocaleBundle = { common: LocaleCommon };

// TODO: Add more languages as needed
const locales: Record<string, LocaleBundle> = {
  en: {
    common: commonEn
  }
};

export function getLocale(locale: string = 'en'): LocaleBundle {
  return locales[locale] ?? locales.en;
}

function getNestedValue(source: unknown, keys: string[]): unknown {
  let current: unknown = source;
  for (const key of keys) {
    if (!current || typeof current !== 'object' || !(key in current)) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

export function t<T = unknown>(key: string, locale: string = 'en'): T | string {
  const translations = getLocale(locale);
  const value = getNestedValue(translations, key.split('.'));

  if (value === undefined || value === null) {
    return key;
  }

  return value as T;
}
