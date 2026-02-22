import { getLocale } from "@/libs/locales";
import HeroFlow from "@/components/HeroFlow";

export default function Hero() {
  const { common } = getLocale('en');
  
  return (
    <section className="flex min-h-[60vh] items-center justify-center px-4 py-20">
      <div className="flex max-w-2xl flex-col items-center gap-6 text-center">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          {common.hero.title}
        </h1>
        <div className="mt-4 w-full">
          <HeroFlow />
        </div>
      </div>
    </section>
  );
}
