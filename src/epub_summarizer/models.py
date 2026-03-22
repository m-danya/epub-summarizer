from dataclasses import dataclass


@dataclass(frozen=True)
class Chapter:
    title: str
    content: str


@dataclass(frozen=True)
class ChapterSummary:
    title: str
    summary: str
