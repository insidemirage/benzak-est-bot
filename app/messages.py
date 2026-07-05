import html

FUEL_FILTER_RECOMMENDATION = (
    "\n\n100 не всегда предоставляется в информации провайдера данных, "
    "поэтому лучше не отмечать только его."
)


def format_checking_message(prefix: str, stations_url: str, dev_mode: bool) -> str:
    if not dev_mode:
        return prefix

    return f'{prefix}\n\nDev: <a href="{html.escape(stations_url, quote=True)}">ссылка toplivo</a>'


def format_fuel_filter_message(selected_fuel_types: set[str], ordered_fuel_types: tuple[str, ...]) -> str:
    if not selected_fuel_types:
        return (
            "Выберите нужные типы бензина. Можно отметить несколько вариантов."
            + FUEL_FILTER_RECOMMENDATION
        )

    return (
        f"Выбрано: {format_fuel_types_for_text(selected_fuel_types, ordered_fuel_types)}. "
        "Можно изменить выбор или нажать «Готово»."
        + FUEL_FILTER_RECOMMENDATION
    )


def format_fuel_types_for_text(fuel_types: set[str], ordered_fuel_types: tuple[str, ...]) -> str:
    return ", ".join(sorted(fuel_types, key=ordered_fuel_types.index))
