from zavod import Context
from lxml import html
from urllib.parse import urlparse, parse_qs
import re

from zavod import helpers as h

REGEX_PATTERN = re.compile(r"(.+)\((.+)\)(.+)")


def crawl_person(context: Context, cell: html.HtmlElement):
    source_url = cell.xpath(".//a/@href")[0]
    match = REGEX_PATTERN.match(cell.text_content())

    if not match:
        context.log.warning("Regex did not match data for person %s" % source_url)
        return

    name, crime, status = map(str.strip, match.groups())

    # either first or last name is considered a bare minimum to emit a person entity
    unknown_spellings = ["Unknown", "Uknown"]
    if sum(name.count(x) for x in unknown_spellings) >= 2:
        return

    person = context.make("Person")

    # each wanted person has a dedicated details page
    # which appears to be a unique identifier
    id = parse_qs(urlparse(source_url).query)["bid"][0]
    person.id = context.make_slug(id)

    h.apply_name(person, full=name)

    person.add("sourceUrl", source_url)
    person.add("notes", f"{status} - {crime}")

    person.add("topics", "crime")
    person.add("country", "za")
    context.emit(person, target=True)


def crawl(context):
    doc = context.fetch_html(context.dataset.data.url, cache_days=1)
    # makes it easier to extract dedicated details page
    doc.make_links_absolute(context.dataset.data.url)
    cells = doc.xpath("//td[.//a[contains(@href, 'detail.php')]]")

    for cell in cells:
        crawl_person(context, cell)
