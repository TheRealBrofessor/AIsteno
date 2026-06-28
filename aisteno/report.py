"""Compression reporting for AIsteno."""

from dataclasses import dataclass

from .codec import decode, encode


@dataclass(frozen=True)
class Stats:
    original_characters: int
    encoded_characters: int
    characters_saved: int
    percent_reduction: float
    roundtrip_matches: bool


def calculate_stats(text: str) -> Stats:
    encoded = encode(text)
    original_count = len(text)
    encoded_count = len(encoded)
    saved = original_count - encoded_count
    reduction = (saved / original_count * 100.0) if original_count else 0.0
    return Stats(
        original_characters=original_count,
        encoded_characters=encoded_count,
        characters_saved=saved,
        percent_reduction=reduction,
        roundtrip_matches=decode(encoded) == text,
    )


def format_stats(stats: Stats) -> str:
    return "\n".join(
        (
            f"original character count: {stats.original_characters}",
            f"encoded character count: {stats.encoded_characters}",
            f"characters saved: {stats.characters_saved}",
            f"percent reduction: {stats.percent_reduction:.2f}%",
            f"roundtrip decode matches original: {'yes' if stats.roundtrip_matches else 'no'}",
        )
    )
