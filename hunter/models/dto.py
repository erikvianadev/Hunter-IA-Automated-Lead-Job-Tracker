from dataclasses import dataclass


@dataclass
class JobResult:
    title: str
    company: str
    location: str
    description: str
    link: str
    source: str = "indeed"

    def is_valid(self) -> bool:
        return bool(self.title and self.link)
    
    def __getitem__(self, key):
        return getattr(self, key)

    @classmethod
    def create(
        cls,
        title="",
        company="",
        location="",
        description="",
        link="",
        source="indeed",
    ):
        return cls(
            title=title or "",
            company=company or "",
            location=location or "",
            description=description or "",
            link=link or "",
            source=source or "",
        )