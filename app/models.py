import json, hashlib
from pydantic import BaseModel, Field


class FeedLink(BaseModel):
    href: str
    rel: str | None = None
    type: str | None = None


class FeedMetadata(BaseModel):
    title: str | None = None
    id: str | None = None
    links: list[FeedLink] = Field(default_factory=list)
    icon: str | None = None
    logo: str | None = None
    subtitle: str | None = None
    updated: str | None = None


class Feed(BaseModel):
    name: str
    url: str
    period: str
    created: str
    metadata: FeedMetadata = FeedMetadata()


class FeedEntryContent(BaseModel):
    type: str | None = None  # text | html | any media type - text/html | xhtml
    value: str | None = None
    src: str | None = None


class FeedPerson(BaseModel):
    name: str | None = None
    url: str | None = None
    email: str | None = None


class FeedEntry(BaseModel):
    published: str
    id: str | None = None
    authors: list[FeedPerson] = Field(default_factory=list)
    contributors: list[FeedPerson] = Field(default_factory=list)
    title: str | None = None
    summary: str | None = None
    links: list[FeedLink] = Field(default_factory=list)
    contents: list[FeedEntryContent] = Field(default_factory=list)

    def compute_id(self) -> str:
        if self.id:
            return self.id

        payload = {
            "title": self.title,
            "published": self.published,
            "summary": self.summary,
            "links": [
                {"href": l.href, "rel": l.rel, "type": l.type}
                for l in self.links
            ],
            "contents": [
                {"type": c.type, "value": c.value, "src": c.src}
                for c in self.contents
            ],
        }

        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()

        return hashlib.sha256(encoded).hexdigest()


