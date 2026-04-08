# AI Report

## Alembic Setup

- `alembic.ini` používá `sqlalchemy.url = sqlite:///./storage.db`.
- `alembic/env.py` přidává root projektu do `sys.path`, importuje `Base` ze `s3_service.database` a importuje `s3_service.models`, aby bylo `target_metadata = Base.metadata` kompletní i pro autogenerate.
- Pro SQLite je v `env.py` zapnuté `render_as_batch=True`, což je důležité pro změny tabulek přes Alembic migrace.

## What AI Helped With

- doporučení nastavit `target_metadata = Base.metadata`, jinak Alembic generuje prázdné nebo neúplné migrace
- doporučení explicitně importovat modul s ORM modely v `env.py`, protože samotný import `Base` nestačí, pokud modely ještě nebyly načtené
- upozornění na relativní cestu k SQLite databázi a na to, že příkaz `alembic` musí běžet z očekávaného working directory
- doporučení kontrolovat autogenerované migrace ručně, hlavně u SQLite a u změn relací / cizích klíčů

## Issues and Manual Corrections

- U relací a komplexnějších změn schématu nestačilo slepě spoléhat na autogenerate:
  - migrace pro buckety a `bucket_id` potřebovala ruční backfill existujících dat
  - migrace pro billing counters a soft delete bylo potřeba ručně zkontrolovat kvůli SQLite batch alter chování
- U evoluce domény bylo nutné ručně hlídat, aby nové sloupce měly správné defaulty a nezničily existující data.
- U request billing bylo potřeba rozhodnout, které endpointy se vůbec mají počítat a na jaký bucket se mají mapovat; to není něco, co Alembic nebo AI odvodí automaticky.

## Common Mistakes AI Can Make

- navrhne `target_metadata = None` nebo zapomene importovat modul s modely, což vede k prázdným migracím
- vygeneruje migraci bez backfill kroků pro existující data
- podcení omezení SQLite při `ALTER TABLE` a nenastaví batch režim
- navrhne automatické přepočty nebo relace bez kontroly business pravidel a kompatibility s existujícími daty

## Final Notes

- Autogenerate je dobrý start, ale ne náhrada za review.
- Každá migrace v `alembic/versions` byla zkontrolovaná tak, aby odpovídala reálnému stavu databáze i aplikace.
