from typing import Generator, Dict, Tuple, Optional
from lxml.etree import _Element
from normality import slugify
from zavod import Context, helpers as h
import re

# It will match the following substrings: DD (any month) YYYY
DATE_PATTERN = r"\b(\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4})\b"


def parse_table(
    table: _Element,
) -> Generator[Dict[str, Tuple[str, Optional[str]]], None, None]:
    headers = None
    for row in table.findall(".//tr"):
        if headers is None:
            headers = []
            for el in row.findall("./th"):
                headers.append(slugify(el.text_content()))
            continue

        cells = []
        for el in row.findall("./td"):
            for span in el.findall(".//span"):
                # add newline to split spans later if we want
                span.tail = "\n" + span.tail if span.tail else "\n"

            # there can be multiple links in the same cell
            a_tags = el.findall(".//a")
            if a_tags is None:
                cells.append((el.text_content(), None))
            else:
                cells.append((el.text_content(), [a.get("href") for a in a_tags]))

        assert len(headers) == len(cells)
        yield {hdr: c for hdr, c in zip(headers, cells) if hdr}


def crawl_item(input_dict: dict, context: Context):
    # aliases will be either a list of size one or None if there is no aliases
    name, *aliases = input_dict.pop("terrorist-entity")[0].split("Also known as ")

    aliases = aliases[0].split(", ") if aliases else []

    organization = context.make("Organization")
    organization.id = context.make_slug(name)
    organization.add("topics", "sanction")

    organization.add("name", name)
    organization.add("alias", aliases)

    sanction = h.make_sanction(context, organization)

    raw_initial_sanction_date, initial_statement_url = input_dict.pop(
        "date-of-designation-as-a-terrorist-entity-in-new-zealand-including-and-statement-of-case-for-designation"
    )

    initial_sanction_date = re.findall(DATE_PATTERN, raw_initial_sanction_date)[0]

    # There is only one date in this case
    sanction.add("startDate", h.parse_date(initial_sanction_date, formats=["%d %B %Y"]))
    sanction.add("sourceUrl", initial_statement_url)

    raw_renew_sanction_dates, renew_statement_urls = input_dict.pop(
        "date-terrorist-designation-was-renewed-in-new-zealand-including-statement-of-case-for-renewal-of-designation"
    )

    renew_sanction_dates = re.findall(DATE_PATTERN, raw_renew_sanction_dates)

    for renew_sanction_date in renew_sanction_dates:
        sanction.add("date", h.parse_date(renew_sanction_date, formats=["%d %B %Y"]))

    for renew_statement_url in renew_statement_urls:
        sanction.add("sourceUrl", renew_statement_url)

    context.emit(organization, target=True)
    context.emit(sanction)
    context.audit_data(input_dict)


def crawl(context: Context):
    response = context.fetch_html(context.data_url)

    response.make_links_absolute(context.data_url)

    table = response.find(".//table")

    if table.findtext(".//caption/strong") != "Alphabetical list of Designated Terrorist Entities in New Zealand pursuant to UNSC Resolution 1373":
        context.log.error("Structure of the website changed, this might not be the correct table")

    for item in parse_table(response.find(".//table")):
        crawl_item(item, context)
