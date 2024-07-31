import csv
from lxml.etree import _Element
from typing import List, Dict, Set
from rigour.mime.types import CSV

from zavod import Context
from zavod import helpers as h


def parse_names(field: str) -> List[str]:
    names: List[str] = []
    for value in field.split(";"):
        value = value.strip()
        if len(value):
            names.append(value)
    return names


def assert_link_hash(context: Context, doc: _Element, label: str, expected: str) -> str:
    label_xpath = f".//td[contains(text(), '{label}')]"
    label_cells = doc.xpath(label_xpath)
    assert len(label_cells) == 1
    anchors = label_cells[0].xpath("./following-sibling::td//a")
    assert len(anchors) == 1
    link = anchors[0]
    url = link.get("href")
    h.assert_url_hash(context, url, expected)
    return url


def crawl(context: Context) -> None:
    doc = context.fetch_html(context.dataset.url)
    doc.make_links_absolute(context.dataset.url)
    expected_sources: Set[str] = set()

    expected_sources.add(
        assert_link_hash(
            context,
            doc,
            "UNLAWFUL ASSOCIATIONS UNDER SECTION 3 OF UNLAWFUL ACTIVITIES (PREVENTION) ACT, 1967",
            "aeb4c0e7cff5acd1e5c34f1e3d07cfdbde56471a",
        )
    )
    expected_sources.add(
        assert_link_hash(
            context,
            doc,
            "TERRORIST ORGANISATIONS LISTED IN THE FIRST SCHEDULE OF THE UNLAWFUL ACTIVITIES (PREVENTION) ACT, 1967",
            "8b563dccdbbb8d497572d3687f7be976fa9702cc",
        )
    )
    expected_sources.add(
        assert_link_hash(
            context,
            doc,
            "INDIVIDUALS TERRORISTS LISTED IN THE FOURTH SCHEDULE OF THE UNLAWFUL ACTIVITIES (PREVENTION) ACT, 1967",
            "310081dd2bd196140f76705d10447ea2dcf924e5",
        )
    )

    path = context.fetch_resource("source.csv", context.data_url)
    context.export_resource(path, CSV, title=context.SOURCE_TITLE)
    named_ids: Dict[str, str] = {}
    with open(path, "r") as fh:
        for row in csv.DictReader(fh):
            entity = context.make(row.pop("Type", "LegalEntity"))
            source_url = row.pop("SourceURL")
            if source_url not in expected_sources:
                context.log.warn(
                    "Source URL not in overview page. Perhaps it's out of date?",
                    url=source_url,
                )
            id_ = row.pop("ID")
            name = row.pop("Name")
            if name is None:
                context.log.warn("No name", row=row)
                continue
            entity.id = context.make_id(id_, name, source_url)
            assert entity.id is not None, row
            named_ids[name] = entity.id
            entity.add("name", name)
            entity.add("notes", row.pop("Notes"))
            entity.add("topics", "sanction")
            entity.add("sourceUrl", source_url)
            entity.add("alias", parse_names(row.pop("Aliases")))
            entity.add("weakAlias", parse_names(row.pop("Weak")))

            sanction = h.make_sanction(context, entity, id_)
            sanction.add("program", row.pop("Designation"))
            sanction.add("authorityId", id_)

            linked = row.pop("Linked", "").strip()
            if len(linked) and linked in named_ids:
                rel = context.make("UnknownLink")
                rel.id = context.make_id(linked, "linked", entity.id)
                rel.add("subject", named_ids[linked])
                rel.add("object", entity.id)
                context.emit(rel)

            context.emit(entity, target=True)
            context.emit(sanction)
