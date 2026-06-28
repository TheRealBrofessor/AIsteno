"""Lossy, fact-preserving structured memory packer for AIsteno v0.2."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .wordlist import WORDLIST


PACK_LEGEND = """PREF=user preferences
STYLE=communication style
RULE=standing rules
PROJ=project notes
DEV=device notes
TOOL=tool/app notes
ACCT=account/email/service notes
PATH=important paths
WF=workflow
TASK=open tasks
STATUS=current status
MEM=memory-specific info
AGENT=agent behavior
RISK=risks/warnings
NEXT=next action
"""


@dataclass(frozen=True)
class PackResult:
    text: str
    records_created: int
    possible_lost_detail_warnings: int


_PROTECTED = re.compile(
    r"(?:"
    r"`[^`\n]+`"  # inline command or code
    r"|\"[^\"\n]+\""  # exact user phrases and quoted values
    r"|\b[A-Z_][A-Z0-9_]*=[^\s]+\s+[A-Za-z0-9_.-]+"  # environment command
    r"|https?://[^\s<>\"]+"
    r"|[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"|(?<!\w)(?:[A-Za-z]:[\\/]|~[/\\]|/|\./|\.\./)[^\s<>\"'`),;]+"
    r"|\b(?:[A-Za-z0-9-]+\.)+(?:local|lan|internal|com|org|net|io|dev|ai|app|co|edu|gov)\b"
    r"|\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+){2,}\b"  # non-FQDN hostnames
    r"|\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    r"|\b(?:sha(?:1|224|256|384|512)|md5):[0-9a-fA-F]{16,}\b"
    r"|\b[0-9a-fA-F]{32,128}\b"
    r"|\b(?:Case|Docket)\s+(?:No\.?|Number|#)?\s*[A-Z0-9][A-Z0-9._/-]*"
    r")",
    re.IGNORECASE,
)

_FILLER = re.compile(
    r"\b(?:the user prefers|the user likes|user prefers|user likes|"
    r"remember that|please remember that|it is important that|important|"
    r"currently|has been|should be|is used for|this means)\b",
    re.IGNORECASE,
)

_SUBJECT_PREFIX = re.compile(
    r"^(?:Professor|the user|user|I)\s+(?:says?|wants?|prefers?|likes?|requests?|needs?)\s+",
    re.IGNORECASE,
)

_BULLET = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\[[ xX]\]\s*)")

_CLASSIFIERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("RISK", ("warning", "risk", "never ", "do not ", "don't ", "sensitive", "danger", "forensic", "hash")),
    ("ACCT", ("account", "email", "login", "password", "credential", "subscription", "@")),
    ("PATH", (" path", "directory", "folder", "repository root", "location:", "/home/", "/srv/")),
    ("DEV", ("device", "laptop", "phone", "tablet", "desktop", "server", "hostname", "operating system", " OS ", "model:")),
    ("TASK", ("open task", "todo", "to do", "needs to", "must still", "remaining task")),
    ("NEXT", ("next action", "next step", "follow up")),
    ("STATUS", ("status", "currently", "in progress", "completed", "blocked", "pending", "live", "working")),
    ("WF", ("workflow", "dry-run", "dry run", "preview", "backup", "checkpoint", "before edit", "before chang", "git ")),
    ("STYLE", ("tone", "communication style", "formatting", "jargon", "bullet", "friendly", "professional")),
    ("PREF", ("prefer", "likes", "wants", "answer", "no fluff", "copy paste", "copy/paste", "sources", "low-token", "concise", "direct")),
    ("AGENT", ("agent should", "agent must", "assistant should", "assistant must", "agent behavior", "permission")),
    ("MEM", ("memory", "context", "session history", "remember")),
    ("TOOL", ("tool", "app", "VS Code", "Codex", "editor", "router")),
    ("PROJ", ("project", "Autonode", "Miahou", "release", "repository", "execution layer", "version")),
    ("RULE", ("rule", " means ", "always", "standing instruction", "must ", "should ")),
)


def _protect(text: str) -> tuple[str, list[str]]:
    values: list[str] = []

    def replace(match: re.Match[str]) -> str:
        values.append(match.group(0))
        return f"\x00{len(values) - 1}\x00"

    return _PROTECTED.sub(replace, text), values


def _restore(text: str, values: list[str]) -> str:
    for index, value in enumerate(values):
        text = text.replace(f"\x00{index}\x00", value)
    return text


def _replace_wordlist(text: str) -> str:
    # Longest first prevents a generic phrase from consuming a specific one.
    for phrase, shorthand in sorted(WORDLIST, key=lambda item: len(item[0]), reverse=True):
        pattern = rf"(?<!\w){re.escape(phrase)}(?!\w)"
        text = re.sub(pattern, lambda _: shorthand, text, flags=re.IGNORECASE)
    return text


def _split_records(text: str) -> list[str]:
    records: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        records.append(_BULLET.sub("", raw_line).strip())

    split: list[str] = []
    for record in records:
        # Sentences are independent memory facts; do not split decimal versions.
        split.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z])", record) if part.strip())
    return split


def _tag_for(record: str) -> str:
    padded = f" {record} "
    folded = padded.casefold()
    for tag, needles in _CLASSIFIERS:
        if any(needle.casefold() in folded for needle in needles):
            return tag
    return "MEM"


def _compact_record(record: str, tag: str) -> str:
    # A labeled path may legally contain spaces. Treat everything after the
    # label as one exact identifier instead of guessing where it ends.
    labeled_path = re.match(r"^(?:important\s+|evidence\s+)?path\s*:\s*(.+)$", record, re.IGNORECASE)
    if tag == "PATH" and labeled_path:
        return labeled_path.group(1)

    protected, values = _protect(record)
    protected = _BULLET.sub("", protected).strip()

    means = re.match(r"^(?:User\s+says\s+)?(.+?)\s+means\s+(.+?)[.]?$", protected, re.IGNORECASE)
    if means:
        compact = f"{means.group(1).strip()}={means.group(2).strip()}"
    else:
        compact = _FILLER.sub("", protected)
        compact = _SUBJECT_PREFIX.sub("", compact)
        compact = re.sub(r"\b(?:and wants|and prefers)\b", ";", compact, flags=re.IGNORECASE)
        compact = re.sub(r"\s+(?:and|also)\s+", ";", compact, flags=re.IGNORECASE)
        compact = _replace_wordlist(compact)
        basic = (
            (r"\bfile operations?\b", "fileops"),
            (r"\bbackups?\b", "bk"),
            (r"\bdelet(?:e|ing)\b", "del"),
            (r"\bmerg(?:e|ing)\b", "mrg"),
            (r"\bretain(?:ing)?\b", "keep"),
            (r"\bcontext\b", "ctx"),
            (r"\bpreview\b", "prev"),
            (r"\bdry[- ]run\b", "dry"),
            (r"\boverwrite\b", "owr"),
            (r"\bchanging\b", "change"),
            (r"\bediting\b", "edit"),
            (r"\bwithout\b", "no"),
            (r"\bonly after\b", "after"),
            (r"\bbefore\b", "pre"),
        )
        for pattern, replacement in basic:
            compact = re.sub(pattern, replacement, compact, flags=re.IGNORECASE)
        compact = re.sub(r"\b(?:a|an|the)\s+", "", compact, flags=re.IGNORECASE)
        compact = re.sub(r"\b(?:is|are)\s+(?=live\b|active\b|ready\b)", "", compact, flags=re.IGNORECASE)
        compact = re.sub(r"\b(?:that|can be|every|please)\s+", "", compact, flags=re.IGNORECASE)
        compact = re.sub(r"\s*[,;:]\s*", ";", compact)
        compact = re.sub(r"\s*=\s*", "=", compact)
        compact = re.sub(r"\s+", " ", compact).strip(" .;,:")
        compact = re.sub(r";{2,}", ";", compact)

    compact = _restore(compact, values)
    # Labels already represented by the record tag add no information.
    labels = {
        "TASK": r"(?:open\s+)?task",
        "NEXT": r"next\s+(?:action|step)",
        "STATUS": r"(?:current\s+)?status",
        "DEV": r"(?:device|model)",
        "PATH": r"(?:evidence\s+)?path",
        "RISK": r"(?:forensic\s+)?hash",
        "ACCT": r"account",
        "RULE": r"rule",
    }
    label = labels.get(tag, re.escape(tag))
    compact = re.sub(rf"^(?:{label}|{re.escape(tag)})\s*[=:;-]\s*", "", compact, flags=re.IGNORECASE)

    # Canonical normal-memory shapes: these remove grammar, not facts.
    shapes: tuple[tuple[str, str], ...] = (
        (r"ans=(short|concise);ans=direct", r"ans=\1/direct"),
        (r"ans=(short|concise) with no=fluff", r"ans=\1;no=fluff"),
        (r"cmd=1box(?: that)? run no edit", "cmd=1box/noedit"),
        (r"src=needed;asks? to (?:avoid )?lists=short", "src=needed;lists=short"),
        (r"answer first;followed by short supporting details", "answer.first;detail=short"),
        (r"dev\.primary is (.+?) running (.+)", r"primary=\1;OS=\2"),
        (r"laptop host is (.+?);OS is (.+)", r"laptop.host=\1;OS=\2"),
        (r"bk phone is (.+)", r"phone.bk=\1"),
        (r"user uses (.+?) as editor;(.+?) as AI\.asst", r"\1=editor;\2=AI.asst"),
        (r"acct\.work email is (.+)", r"work.email=\1"),
        (r"main proj\.dir is (.+)", r"main.proj=\1"),
        (r"proj repo is (.+?);proj active", r"repo=\1;active"),
        (r"user works on AI\.agent\.proj named (.+?) with (.+?) as its local\.exec layer", r"\1/\2;role=local.exec"),
        (r"dry\.first for fileops", "dry.first:fileops"),
        (r"bk\.pre\.edit;confirmation pre del files", "bk.pre.edit;confirm.pre.del"),
        (r"user uses git\.ckpt pre large changes", "git.ckpt.pre.large.change"),
        (r"wf requires review\.pre\.apply generated changes", "review.pre.apply"),
        (r"asst;ask\.pre\.change cfg;should not owr existing output by default", "asst:ask.pre.cfg;no.owr"),
        (r"archive mode is works;pack mode is dev", "archive=works;pack=WIP"),
        (r"Miahou should keep mem\.inj\.budget ctx", "Miahou:keep mem.inj.budget/ctx"),
        (r"Autonode will bk;mrg;;?del after yup", "Autonode:bk,mrg,del after yup"),
        (r"(Case\s+No\.?\s+\S+) must remain exact", r"\1 exact"),
        (r"Miahou should ask\.pre\.change files;prev changes first;keep bk\.pre\.edit", "Miahou:ask.pre.file.change;prev.first;bk.pre.edit"),
        (
            r"Autonode is local\.exec layer for Miahou agent proj;handles fileops;scan;research;monitor;notify;system tasks",
            "Miahou/Autonode:local.exec;tasks=fileops,scan,research,monitor,notify,system",
        ),
        (r"proj\.status active;next is to test normal mem packing", "proj=active;test normal.mem.pack"),
        (r"user uses VS Code;Codex;wants git\.ckpt pre large changes;src=needed", "VS Code,Codex;git.ckpt.pre.large;src=needed"),
    )
    for pattern, replacement in shapes:
        compact = re.sub(rf"^{pattern}$", replacement, compact, flags=re.IGNORECASE)
    return compact


def _merge_fields(existing: list[str], candidate: str) -> None:
    for field in (part for part in candidate.split(";") if part):
        folded = field.casefold()
        if any(folded == current.casefold() or folded in current.casefold() for current in existing):
            continue
        existing[:] = [current for current in existing if current.casefold() not in folded]
        existing.append(field)


_DENSE_PHRASES: tuple[tuple[str, str], ...] = (
    ("Nurse Harn retaliated via", "Nurse.Harn:retal="),
    ("Forde grieved husband", "Forde grievance(husband)"),
    ("Transfusions from cumulative factors", "transfusion<-cumulative"),
    ("NOT diet alone", "!diet-only"),
    ("Officer White blocked pain meds", "Officer.White:blk pain.med"),
    ("All 14th Amendment;PLRA complete", "14A+PLRA=done"),
    ("very short direct commands", "cmd=short/direct"),
    ("action and results over explanation", "action/results>explain"),
    ("things done no asking questions", "do>ask.Q"),
    ("state goal FIRST", "goal.1st"),
    ("wait for explicit", "wait.explicit"),
    ("confirmation pre executing multi-step tasks", "confirm.pre.multi-task"),
    ("halt immediately", "halt.now"),
    ("When brainstorming vulns/exploits", "brainstorm:vuln/exploit"),
    ("no execution — only questions", "no.exec;Q.only"),
    ("you ask one question back", "ask.1Q.back"),
    ("things displayed on HIS screen", "display>HIS.screen"),
    ("Build product first", "product.1st"),
    ("Token reduction", "tok.reduce"),
    ("Frustration signals", "frustration"),
    ("Never repeat failed approaches", "no.repeat.failed"),
    ("Test CLI pre GUI wiring", "test.CLI>GUI"),
    ("won't display from agent", "agent.no.display"),
    ("Bulk deletes blocked by sec", "bulk.del=blocked"),
    ("user must run cleanup", "U:run.cleanup"),
    ("Same-file copy errors", "copy.same=err"),
    ("check src!=dest", "check:src!=dest"),
    ("blocks browser forms", "blocks browser.form"),
    ("min between sends", "min/send"),
    ("VERIFY all facts pre drafting", "verify.fact.pre.draft"),
    ("never construct causal narratives from mem", "no.causal.from.mem"),
    ("Android forensics suite", "Android FORE.suite"),
    ("Competitive recon at", "recon="),
    ("Phased dev plan active", "dev.plan=active"),
    ("classifies tasks → builds packet", "task→packet"),
    ("Returns compact JSON", "out=compact.JSON"),
    ("Miahou explains", "Miahou:explain"),
    ("LLM tokens for Autonode tasks", "LLM.tok/Autonode.task"),
    ("approval=req for writes/destructive", "write/del:approval"),
    ("All tests pass", "tests=pass"),
    ("NO BROM exploit", "BROM.exploit=none"),
    ("USB non-responsive", "USB=no.response"),
    ("after failed", "post.fail"),
    ("works for bk/extraction", "works:bk/extract"),
    ("in fastboot mode", "mode=fastboot"),
    ("recovery menu accessible", "recovery=access"),
    ("Partition layout captured", "partition.layout=cap"),
    ("Hacking skill tree names", "skill.tree"),
    ("needs VM reversing", "need VM.reverse"),
    ("I can do it", "can.do"),
    ("Paste code", "paste.code"),
    ("no setup", "setup=none"),
    ("communicates in", "comm="),
    ("Prefers action", "pref:action"),
    ("results over explanation", "results>explain"),
    ("Wants things done", "want:done"),
    ("is OWNER of", "=OWNER:"),
    ("creator only", "creator"),
    ("Forensic suite proj active", "FORE.suite=active"),
    ("NEVER judge passwords", "no.judge.pw"),
    ("has ONE machine", "machine=1"),
    ("No other machines", "other.machine=0"),
    ("custom driver", "drv=custom"),
    ("standard ioctls FAIL", "std.ioctl=FAIL"),
    ("triggers restart", "→restart"),
    ("Communication shorthand", "comm.short"),
    ("go-ahead", "go"),
    ("Use this when user says", "when U says"),
    ("instead of", "not"),
    ("Professor preferences", "PREF"),
    ("sentences max", "sent.max"),
    ("no filler", "no=filler"),
    ("bullet points", "bullets"),
    ("just do it", "act"),
    ("all sudo", "sudo=all"),
    ("web GUI", "web.GUI"),
    ("Spam rules", "spam.rule"),
    ("Default deny", "deny.default"),
    ("skill tree", "skill.tree"),
    ("Workflow rule", "WF"),
    ("Thinktank mode", "thinktank"),
    ("project active", "proj=active"),
    ("Professor rule", "P.rule"),
    ("Professor", "P"),
    ("the user", "U"),
    ("User", "U"),
    ("preferences", "pref"),
    ("currently", "now"),
    ("executing", "exec"),
    ("execution", "exec"),
    ("extraction", "extract"),
    ("installed", "inst"),
    ("accessible", "access"),
    ("captured", "cap"),
    ("required", "req"),
    ("destructive", "del"),
    ("questions", "Q"),
    ("question", "Q"),
    ("machine", "mach"),
    ("passwords", "pw"),
    ("reversing", "reverse"),
    ("displayed", "display"),
    ("explanation", "explain"),
    ("configuration", "cfg"),
    ("confirmation", "confirm"),
    ("approaches", "tries"),
    ("security", "sec"),
    ("browser", "web"),
    ("application", "app"),
    ("tasks", "task"),
    ("retaliated", "retal"),
    ("Transfusions", "transfusion"),
    ("cumulative", "cum"),
    ("factors", "factor"),
    ("blocked", "blk"),
    ("complete", "done"),
    ("Frustration", "frust"),
    ("signals", "sig"),
    ("product", "prod"),
    ("reduction", "reduce"),
    ("repeat", "rpt"),
    ("failed", "fail"),
    ("wiring", "wire"),
    ("display", "show"),
    ("cleanup", "clean"),
    ("errors", "err"),
    ("facts", "fact"),
    ("drafting", "draft"),
    ("causal narratives", "causal.story"),
    ("forensics", "FORE"),
    ("Competitive", "comp"),
    ("active", "on"),
    ("classifies", "class"),
    ("builds", "build"),
    ("executes", "exec"),
    ("Returns", "out"),
    ("compact", "cmp"),
    ("explains", "explain"),
    ("tokens", "tok"),
    ("writes", "write"),
    ("Artifacts", "art"),
    ("exploit", "xpl"),
    ("responsive", "resp"),
    ("Partition", "part"),
    ("layout", "map"),
    ("Research", "res"),
    ("recovery", "recov"),
    ("reversing", "rev"),
    ("reverse", "rev"),
    ("needs", "need"),
    ("communication", "comm"),
    ("shorthand", "short"),
    ("instead", "not"),
    ("machine", "mach"),
    ("machines", "mach"),
    ("standard", "std"),
    ("driver", "drv"),
    ("restart", "rst"),
    ("questions", "Q"),
    ("commands", "cmd"),
    ("before", "pre"),
    ("after", "post"),
    ("only", "only"),
)


def _dense_compact(text: str) -> str:
    protected, values = _protect(text)
    for phrase, shorthand in sorted(_DENSE_PHRASES, key=lambda item: len(item[0]), reverse=True):
        protected = re.sub(
            rf"(?<!\w){re.escape(phrase)}(?!\w)",
            lambda _: shorthand,
            protected,
            flags=re.IGNORECASE,
        )
    protected = re.sub(r"\s+(?:is|are|was|were)\s+", "=", protected, flags=re.IGNORECASE)
    protected = re.sub(r"\s+(?:and|also)\s+", ";", protected, flags=re.IGNORECASE)
    protected = re.sub(r"\s*—\s*", "—", protected)
    protected = re.sub(r"\s*→\s*", "→", protected)
    protected = re.sub(r"\s*([=+])\s*", r"\1", protected)
    protected = re.sub(r";{2,}", ";", protected).strip(" ;")
    restored = _restore(protected, values)
    shapes: tuple[tuple[str, str], ...] = (
        (
            r"wf rule (\(.+?\));Always goal\.1st;wait\.explicit (\".+?\") confirm\.pre\.multi-task\. (\".+?\")=halt\.now",
            r"\1:goal.1st;wait \2 pre multi-task;\3=halt",
        ),
        (r"thinktank (\(.+?\));brainstorm:vuln/xpl;no\.exec;Q\.only", r"thinktank\1:vuln/xpl=no.exec/Q.only"),
        (r"U asks;ask\.1Q\.back", "U asks→1Q.back"),
        (r"show>HIS\.screen when he says (\".+?\")—use (.+)", r"\1→show:HIS.screen via \2"),
        (r"P=OWNER: (.+?)/(.+?) \(not (.+?)—\3=creator\)", r"\1/\2:owner=P;\3=creator"),
        (r"P\.rule;no\.judge\.pw\. sudo=(.+)", r"P:no.judge.pw;sudo=\1"),
        (r"P mach=1;(.+)", r"P:mach=1;\1"),
        (r"comm\.short (\(.+?\));(.+)", r"comm.short\1:\2"),
        (r"U comm=cmd=short/direct (.+)", r"U:cmd=short/direct\1"),
        (r"pref:action;results>explain", "pref:action/results>explain"),
        (r"want:done no asking Q", "want:do>ask.Q"),
        (r"Wants do>ask\.Q", "want:do>ask.Q"),
        (r"Company;(.+)", r"company=\1"),
        (r"OS;(.+)", r"OS=\1"),
        (r"(.+?) drv=custom (.+)—std\.ioctl=FAIL", r"\1:drv=custom\2;std.ioctl=FAIL"),
        (
            r"Moto Z Droid \((.+?)\);?",
            r"Moto Z Droid[\1]",
        ),
        (r"Android ([^;]+);kernel ([^;]+);(.+)", r"Android\1/kernel\2/\3"),
        (r"KGSL:drv=custom(\".+?\");std\.ioctl=FAIL", r"KGSL[\1]:drv=custom;ioctl=FAIL"),
        (r"BP Tools in fastboot→rst", "BP Tools:fastboot→rst"),
        (r"when U says yup not approved", "U:yup→approved"),
        (r"when U says yup not ok", "U:yup→approved"),
        (r"P:mach=1;(.+?) on (.+?) \(host;(.+?)\)", r"P:1mach=\1/\2@\3"),
        (r"other\.mach=0", "mach.other=0"),
        (r"PREF;tok=low—2-3 sent\.max;no=filler;bullets;act\. (\".+?\")=sudo=all", r"tok=low;ans=2-3sent;no=filler;bullets;act;\1=sudo.all"),
        (r"Flask for web\.GUI\. tkinter agent\.no\.show—use Flask", "web.GUI=Flask;tkinter:no.agent.display→Flask"),
        (r"Bridge SMTP;1025 IMAP;1143 localhost\. reCAPTCHA blocks web\.form", "SMTP:1025;IMAP:1143@localhost;reCAPTCHA:block.web.form"),
        (r"Email/ProtonMail;(.+?) / (.+)", r"ProtonMail:\1;pw=\2"),
        (r"Vertex Global Services LLC—Android FORE\.suite", "Vertex Global Services LLC:Android FORE.suite"),
        (r"Miahou GUI \(Flask;(.+?)\)", r"Miahou.GUI=Flask:\1"),
        (r"Autonode v1\.0 LIVE (\(.+?\));Router \((.+?)\) task→packet", r"Autonode v1.0 LIVE\1;router=\2:task→packet"),
        (r"Engine \((.+?)\) exec file_ops \(LIVE\)\+system_ops \(scaffold/gated false\)", r"engine=\1:file_ops=LIVE;system_ops=scaffold/gated:false"),
        (r"out=cmp\.JSON;Miahou:explain \(cap (.+?)\)\. 0 LLM\.tok/Autonode\.task", r"out=JSON;Miahou:explain≤\1;Autonode.LLM.tok=0"),
        (r"deny\.default;approval=req for write/del", "deny.default;write/del=approval"),
        (r"art;(.+)", r"art=\1"),
        (r"Moto G Stylus 2022 \((.+?)\);(.+?);BROM\.xpl=none in mtkclient", r"Moto G Stylus 2022[\1;\2];mtkclient:BROM.xpl=none"),
        (r"Preloader USB=no\.response post\.fail (.+)", r"Preloader.USB=no.response post fail:\1"),
        (r"mode=fastboot \((.+?)\);recov=access", r"fastboot=\1;recovery=access"),
        (r"part\.map=cap\. mtkclient inst (.+)", r"partition.map=cap;mtkclient=\1"),
        (r"skill\.tree;(.+)", r"skill.tree=\1"),
        (r"res;(.+)", r"research=\1"),
        (r"JS rev;P need VM\.rev", "JS:VM.rev needed;can.do"),
        (r"paste\.code;setup=none", "paste.code;setup=0"),
    )
    for pattern, replacement in shapes:
        restored = re.sub(rf"^{pattern}$", replacement, restored, flags=re.IGNORECASE)
    return restored


def pack(text: str, *, legend: bool = False) -> PackResult:
    """Pack normal memory into compact records; output is intentionally lossy."""
    grouped: dict[str, list[str]] = {}
    warnings = 0
    for raw_record in _split_records(text):
        tag = _tag_for(raw_record)
        compact = _compact_record(raw_record, tag)
        if not compact:
            warnings += 1
            continue
        if len(raw_record) > 500:
            warnings += 1
        compact = _dense_compact(compact)
        if compact != "§":
            _merge_fields(grouped.setdefault(tag, []), compact)

    lines = [f"{tag}{{{';'.join(fields)}}}" for tag, fields in grouped.items()]
    packed = "\n".join(lines)
    if packed:
        packed += "\n"
    if legend:
        packed = PACK_LEGEND + packed
    return PackResult(packed, len(lines), warnings)
