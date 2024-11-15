from zavod import Context, helpers as h


# LINKS_PERSONS = [
#     # child kidnappers
#     f"https://war-sanctions.gur.gov.ua/en/kidnappers/persons?page={page}&per-page=12",
#     # russian athletes
#     f"https://war-sanctions.gur.gov.ua/en/sport/persons?page={page}&per-page=12",
# ]

# LINKS_COMPANIES = [
#     f"https://war-sanctions.gur.gov.ua/en/kidnappers/companies?page={page}&per-page=12s",  # child kidnappers
# ]


def crawl_item(context: Context, data, link):
    names = data.pop("Name")
    positions = data.pop("Position", None)

    person = context.make("Person")
    person.id = context.make_id(names, positions)
    for name in h.multi_split(names, [" | "]):
        person.add("name", name)
    person.add("citizenship", data.pop("Citizenship", None))
    person.add("taxNumber", data.pop("Tax Number", None))
    person.add("sourceUrl", data.pop("Links", None).split(" | "))
    dob_pob = data.pop("Date and place of birth", None)
    if dob_pob:
        dp_parts = dob_pob.split(" | ")
        # If we get more than one part, unpack it into dob and pob
        if len(dp_parts) == 2:
            dob, pob = dp_parts
            h.apply_date(person, "birthDate", dob)
            person.add("birthPlace", pob)
        elif len(dp_parts) == 1:
            # If there’s only one part, we assume it's just the dob
            dob = dp_parts[0]
            h.apply_date(person, "birthDate", dob)
    if positions:
        pos_parts = positions.split(" / ")
        for position in pos_parts:
            person.add("position", position)
    person.add("topics", "sanction")
    person.add("topics", "crime.war")

    sanction = h.make_sanction(context, person)
    sanction.add("reason", data.pop("Reasons", None))
    sanction.add("sourceUrl", link)

    context.emit(person, target=True)
    context.emit(sanction)
    context.audit_data(data)


def crawl(context):
    # Define the base URLs for both child kidnappers and Russian athletes
    LINKS_PERSONS = [
        # child kidnappers
        "https://war-sanctions.gur.gov.ua/en/kidnappers/persons?page={page}&per-page=12",
        # russian athletes
        "https://war-sanctions.gur.gov.ua/en/sport/persons?page={page}&per-page=12",
    ]

    for base_url in LINKS_PERSONS:
        page = 1
        unique_links = set()

        while True:
            # Build the URL for the current page
            url = base_url.format(page=page)
            print(f"Fetching {url}...")

            # Fetch the HTML content for the current page
            index_page = context.fetch_html(url, cache_days=3)
            unique_links.add(url)

            # Attempt to extract "pagination" element
            pagination = index_page.find(".//ul[@class='pagination']")
            if pagination is None:
                context.log.warning("Could not find pagination element")
                break

            # Find the "next" link (if it exists)
            next_page_elem = pagination.find(".//li[@class='next']/a")
            if next_page_elem is None:
                print("No next page found, exiting the loop.")
                break  # Exit loop if no next page is found

            # Get the URL for the next page
            next_page_url = next_page_elem.get("href")
            if next_page_url in unique_links:
                print("Next page has been processed already, exiting the loop.")
                break  # Exit loop if the next page is already processed

            # Proceed to the next page
            page += 1

        for index_page in unique_links:
            main_grid = index_page.find('.//div[@id="main-grid"]')
            if main_grid is not None:
                for a in main_grid.findall(".//a"):
                    href = [a.get("href")]
                    for link in href:
                        if link.startswith("https:"):
                            detail_page = context.fetch_html(link, cache_days=3)

                            details_container = detail_page.find(
                                ".//div[@id='js_visibility'][@class='col-12 col-lg-9']"
                            )
                            if details_container is None:
                                context.log.warning(
                                    f"Could not find details container on {link}"
                                )
                                continue
                            data = {}
                            for row in details_container.findall(
                                ".//div[@class='row']"
                            ):
                                label_elem = row.find(
                                    ".//div[@class='col-12 col-md-4 col-lg-2 yellow']"
                                )
                                value_elem = row.find(
                                    ".//div[@class='col-12 col-md-8 col-lg-10']"
                                )
                                if value_elem is None:
                                    value_elem = row.find(
                                        ".//div[@class='js_visibility_target col-12 col-md-8 col-lg-10']"
                                    )
                                if label_elem is not None and value_elem is not None:
                                    label = (
                                        label_elem.text_content()
                                        .strip()
                                        .replace("\n", " ")
                                    )
                                    value = (
                                        value_elem.text_content()
                                        .strip()
                                        .replace("\n", " ")
                                    )
                                    value = " ".join(value.split())
                                    value = " | ".join(
                                        [
                                            text.strip()
                                            for text in value_elem.itertext()
                                            if text.strip()
                                        ]
                                    ).strip()

                                    data[label] = value
                            crawl_item(context, data, link)
