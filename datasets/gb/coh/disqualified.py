import os
import time
import string
from typing import Dict, Any
from urllib.parse import urljoin
from requests.exceptions import HTTPError

from zavod import Context
from zavod import helpers as h


class AbortCrawl(Exception):
    pass


API_KEY = os.environ.get("OPENSANCTIONS_COH_API_KEY", "")
AUTH = (API_KEY, "")
SEARCH_URL = (
    "https://api.company-information.service.gov.uk/search/disqualified-officers"
)
# SEARCH_URL = "https://api-sandbox.company-information.service.gov.uk/search/disqualified-officers"
API_URL = "https://api.company-information.service.gov.uk/"
WEB_URL = "https://find-and-update.company-information.service.gov.uk/register-of-disqualifications/A"


def crawl_item(context: Context, listing: Dict[str, Any]) -> None:
    links = listing.get("links", {})
    url = urljoin(API_URL, links.get("self"))
    try:
        data = context.fetch_json(url, auth=AUTH, cache_days=45)
    except HTTPError as err:
        if err.response.status_code in (429, 416):
            raise AbortCrawl()
        if err.response.status_code == 404:
            context.log.info("Entity removed: %s" % url)
            return
        context.log.exception("HTTP error: %s" % url)
        return
    person = context.make("Person")
    _, officer_id = url.rsplit("/", 1)
    person.id = context.make_slug(officer_id)

    person.add("name", listing.get("title"))
    person.add("notes", listing.get("description"))
    person.add("topics", "corp.disqual")
    source_url = urljoin(WEB_URL, links.get("self"))
    person.add("sourceUrl", source_url)

    h.apply_name(
        person,
        first_name=data.pop("forename", None),
        last_name=data.pop("surname", None),
        middle_name=data.pop("other_forenames", None),
        lang="eng",
    )
    person.add("title", data.pop("title", None))

    nationality = data.pop("nationality", None)
    if nationality is not None:
        person.add("nationality", nationality.split(","))
    person.add("birthDate", data.pop("date_of_birth", None))

    address = listing.get("address", {})
    address = h.make_address(
        context,
        full=listing.get("address_snippet"),
        street=address.get("address_line_1"),
        street2=address.get("premises"),
        city=address.get("locality"),
        postal_code=address.get("postal_code"),
        region=address.get("region"),
        # country_code=person.first("nationality"),
    )
    h.apply_address(context, person, address)

    for disqual in data.pop("disqualifications", []):
        case_id = disqual.get("case_identifier")
        sanction = h.make_sanction(context, person, key=case_id)
        sanction.add("recordId", case_id)
        sanction.add("startDate", disqual.get("disqualified_from"))
        sanction.add("endDate", disqual.get("disqualified_until"))
        sanction.add("listingDate", disqual.get("undertaken_on"))
        for key, value in disqual.get("reason", {}).items():
            value = value.replace("-", " ")
            reason = f"{key}: {value}"
            sanction.add("reason", reason)
        sanction.add("country", "gb")
        context.emit(sanction)

        address = disqual.get("address", {})
        address = h.make_address(
            context,
            full=listing.get("address_snippet"),
            street=address.get("address_line_1"),
            street2=address.get("premises"),
            city=address.get("locality"),
            postal_code=address.get("postal_code"),
            region=address.get("region"),
            # country_code=person.first("nationality"),
        )

        for company_name in disqual.get("company_names", []):
            company = context.make("Company")
            company.id = context.make_slug("named", company_name)
            company.add("name", company_name)
            company.add("jurisdiction", "gb")
            # company.add("topics", "crime")
            context.emit(company)
            h.apply_address(context, company, address)

            directorship = context.make("Directorship")
            directorship.id = context.make_id(person.id, company.id)
            directorship.add("director", person)
            directorship.add("organization", company)
            context.emit(directorship)

    context.emit(person, target=True)


def crawl(context: Context) -> None:
    if not len(API_KEY):
        context.log.error("Please set $OPENSANCTIONS_COH_API_KEY.")
        return
    try:
        for letter in string.ascii_uppercase:
            start_index = 0
            while True:
                params = {
                    "q": letter,
                    "start_index": str(start_index),
                    "items_per_page": "100",
                }
                try:
                    data = context.fetch_json(
                        SEARCH_URL,
                        params=params,
                        auth=AUTH,
                        cache_days=10,
                    )
                except HTTPError as err:
                    if err.response.status_code in (429, 416):
                        raise AbortCrawl()
                    context.log.exception("HTTP error: %s" % SEARCH_URL)
                    break
                context.log.info("Search: %s" % letter, start_index=start_index)
                for item in data.pop("items", []):
                    crawl_item(context, item)
                    time.sleep(3)
                start_index = data["start_index"] + data["items_per_page"]
                if data["total_results"] < start_index:
                    break
    except AbortCrawl:
        context.log.info("Rate limit exceeded, aborting.")
