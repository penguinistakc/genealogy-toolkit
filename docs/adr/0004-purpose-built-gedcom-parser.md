# Purpose-built GEDCOM parser instead of a library

GEDCOM exports are read by a small parser written in this repo, not a third-party GEDCOM library. The parser sees every name, date, place and note in the research, and the available Python GEDCOM libraries are mostly small projects maintained by individuals with little recent activity; GEDCOM's line grammar (level, optional cross-reference, tag, value, with CONC/CONT continuation) is simple enough that owning it is cheaper than trusting one. Only the standard library and PyYAML are trusted with the research.

## Consequences

Only UTF-8 exports are accepted. ANSEL and ANSI exports are rejected with a request to re-export as UTF-8, rather than decoded by guesswork that could silently change names. Every GEDCOM feature the toolkit needs (families, notes, source references) is ours to implement and test.
