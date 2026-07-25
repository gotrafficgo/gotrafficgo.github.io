#!/usr/bin/env python3
"""Update Google Scholar statistics embedded in index.html."""

from __future__ import annotations

import argparse
import html
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


SCHOLAR_ID = "qH12Xy4AAAAJ"
SCHOLAR_URL = (
    "https://scholar.google.com/citations"
    f"?user={SCHOLAR_ID}&hl=en"
)
STAT_PATTERN = re.compile(
    r'<td[^>]*class=["\'][^"\']*\bgsc_rsb_std\b[^"\']*["\'][^>]*>'
    r"(.*?)</td>",
    re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")


def fetch_profile(attempts: int = 3) -> str:
    request = urllib.request.Request(
        SCHOLAR_URL,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
        },
    )

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == attempts:
                raise RuntimeError(
                    f"Unable to fetch Google Scholar after {attempts} attempts: {error}"
                ) from error
            time.sleep(attempt * 5)

    raise RuntimeError("Unable to fetch Google Scholar")


def parse_stats(profile_html: str) -> dict[str, str]:
    raw_values = STAT_PATTERN.findall(profile_html)
    values: list[str] = []

    for raw_value in raw_values:
        text = html.unescape(TAG_PATTERN.sub("", raw_value)).strip()
        digits = re.sub(r"\D", "", text)
        if digits:
            values.append(f"{int(digits):,}")

    # Scholar orders the table as:
    # citations (all/since), h-index (all/since), i10-index (all/since).
    if len(values) < 6:
        raise RuntimeError(
            "Google Scholar statistics table was not found. "
            "The request may have been rate-limited or the page structure changed."
        )

    return {
        "citations": values[0],
        "h-index": values[2],
        "i10-index": values[4],
    }


def update_index(index_path: Path, stats: dict[str, str]) -> bool:
    page = index_path.read_text(encoding="utf-8")
    updated_page = page

    for stat_name, value in stats.items():
        pattern = re.compile(
            rf'(<strong data-scholar-stat="{re.escape(stat_name)}">)'
            r"[^<]*"
            r"(</strong>)"
        )
        updated_page, replacements = pattern.subn(
            rf"\g<1>{value}\g<2>",
            updated_page,
            count=1,
        )
        if replacements != 1:
            raise RuntimeError(
                f'Expected one data-scholar-stat="{stat_name}" marker in {index_path}'
            )

    if updated_page == page:
        return False

    index_path.write_text(updated_page, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--index",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "index.html",
    )
    parser.add_argument(
        "--profile-html",
        type=Path,
        help="Parse a saved Scholar profile instead of making a network request.",
    )
    args = parser.parse_args()

    try:
        profile_html = (
            args.profile_html.read_text(encoding="utf-8")
            if args.profile_html
            else fetch_profile()
        )
        stats = parse_stats(profile_html)
        changed = update_index(args.index, stats)
    except (OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        "Google Scholar stats: "
        f"citations={stats['citations']}, "
        f"i10-index={stats['i10-index']}, "
        f"h-index={stats['h-index']}"
    )
    print("index.html updated" if changed else "index.html already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
