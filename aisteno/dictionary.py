"""Stable v0.1 dictionary and format constants."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Substitution:
    phrase: str
    shorthand: str


# Longest phrases come first. This ordering is part of the v0.1 format.
SUBSTITUTIONS: tuple[Substitution, ...] = (
    Substitution("Professor prefers low-token mode", "PREF:TOKLOW"),
    Substitution("one-box copy paste commands", "CMD=1BOX"),
    Substitution("memory injection budget", "MEM.INJ.BUDGET"),
    Substitution("file-system", "FS"),
    Substitution("injected context", "INJ"),
    Substitution("token budget", "TOK"),
    Substitution("legal case refs", "CASE"),
    Substitution("device refs", "DEV"),
    Substitution("no fluff", "NOFLUFF"),
    Substitution("Autonode", "AN"),
    Substitution("Professor", "P"),
    Substitution("Miahou", "M"),
    Substitution("forensics", "FORE"),
    Substitution("context", "CTX"),
    Substitution("memory", "MEM"),
    Substitution("backup", "BK"),
    Substitution("delete", "DEL"),
    Substitution("merge", "MRG"),
    Substitution("retain", "KEEP"),
    Substitution("yup", "APPROVE"),
)

LEGEND = """AISTENO/v0.1
MODE: reversible
LEGEND:
P=Professor
M=Miahou
AN=Autonode
MEM=memory
CTX=context
FS=file-system
BK=backup
DEL=delete
MRG=merge
KEEP=retain
CASE=legal case refs
DEV=device refs
FORE=forensics
TOK=token budget
INJ=injected context
APPROVE=yup/approved
"""

BODY_MARKER = "BODY:\n"
HEADER = LEGEND + BODY_MARKER
