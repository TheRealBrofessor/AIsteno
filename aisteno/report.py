"""Compression reporting for AIsteno."""

from dataclasses import dataclass

from .codec import decode, encode
from .pack import PackResult, pack


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


@dataclass(frozen=True)
class PackStats:
    original_characters: int
    packed_characters: int
    characters_saved: int
    percent_reduction: float
    records_created: int
    possible_lost_detail_warnings: int


def calculate_pack_stats(text: str) -> PackStats:
    result: PackResult = pack(text)
    original_count = len(text)
    packed_count = len(result.text)
    saved = original_count - packed_count
    reduction = (saved / original_count * 100.0) if original_count else 0.0
    return PackStats(
        original_characters=original_count,
        packed_characters=packed_count,
        characters_saved=saved,
        percent_reduction=reduction,
        records_created=result.records_created,
        possible_lost_detail_warnings=result.possible_lost_detail_warnings,
    )


def format_pack_stats(stats: PackStats) -> str:
    return "\n".join(
        (
            f"original chars: {stats.original_characters}",
            f"packed chars: {stats.packed_characters}",
            f"chars saved: {stats.characters_saved}",
            f"percent reduction: {stats.percent_reduction:.2f}%",
            f"records created: {stats.records_created}",
            f"possible lost-detail warnings: {stats.possible_lost_detail_warnings}",
        )
    )
