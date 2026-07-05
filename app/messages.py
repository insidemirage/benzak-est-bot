import html


def format_checking_message(prefix: str, stations_url: str, dev_mode: bool) -> str:
    if not dev_mode:
        return prefix

    return f'{prefix}\n\nDev: <a href="{html.escape(stations_url, quote=True)}">ссылка toplivo</a>'

