# Unlisted Cases: Justice Gorbanzo, Sitting by Designation

The case in this workspace is an unlisted case. It was not heard on the podcast; it was filed directly with the Court from a private league. Everything above still applies unless this section says otherwise. Where they conflict, this section controls.

## The Bench

Unlisted cases are heard by Justice Gorbanzo, sitting by designation, alone. Chief Justice Heifetz, Justice Kelly, and Justice Horlbeck do not participate, and nothing in the opinion should suggest that they heard the case or agreed with it.

Justice Gorbanzo sits on the Fantasy Court itself, so the opinion is an opinion of the Court with the same precedential force as any other. Fantasy Court precedent binds Justice Gorbanzo, and Justice Gorbanzo's opinions bind later cases. Treat the corpus exactly as you would for any other case.

**Authorship**: always `<span class="small-caps">Justice Gorbanzo</span>, sitting by designation, delivered the opinion of the Court.` There are no concurrences or dissents, since there is no one else on the bench.

**Doctrinal projects**: Justice Gorbanzo has doctrinal projects like any other justice. Grep the corpus for "Gorbanzo" before writing. If prior Gorbanzo opinions exist, extend their line and keep the voice consistent. If none exist, this opinion establishes the voice: give Justice Gorbanzo a recognizable method and a commitment or two that future opinions can pick up, distinct from the three regular justices. Justice Gorbanzo may occasionally acknowledge sitting by designation, but do not make it the joke of every paragraph.

## The Record

There is no `transcript.txt`. In its place:

- `record.md`: the written record, if one was filed. It may contain the parties' accounts, league rules, chat logs, and the like.
- `exhibits/`: exhibits filed with the case (PDFs, images), listed in `case.md` as Exhibit A, Exhibit B, and so on. Read every exhibit in full. Use the Read tool on PDFs directly; for long PDFs, read them in page ranges. Images inside exhibits (screenshots, league settings, chat logs) are evidence; examine them carefully.

## Deciding the Case

There are no hosts whose conclusion you must follow. Justice Gorbanzo decides the case on the merits, applying Fantasy Court precedent. The guidelines above about fidelity to the episode and the hosts' reasoning are replaced by fidelity to the record and to precedent. If `record.md` contains a direction from the filer about how the case should come out (for example, a "Court's direction" section), follow it.

- Draw facts about the league and the parties only from `record.md` and the exhibits. Do not invent facts, scores, messages, or league rules. Facts about the NFL itself may also come from `./fantasypros` and web search (below). Where the parties' accounts conflict, resolve the conflict as a fact-finder and say how you resolved it.
- Cite the record specifically, in ordinary legal style and plain text with no special markup: "Ex. A, at 3" for page 3 of Exhibit A, or "Record" for `record.md`.
- The parties are members of a private league. Refer to them as the record does.

## FantasyPros Data

With no hosts to supply football judgment, you have `./fantasypros`, which queries FantasyPros expert consensus data. Use it when a question turns on player value that the record does not settle: whether a trade was lopsided, whether a lineup decision was defensible, what a waiver claim was worth, what a manager knew or should have known about an injury.

```
./fantasypros find "Puka Nacua" "Kenneth Walker"         # resolve names to FantasyPros IDs (free)
./fantasypros projections "Puka Nacua" "Kenneth Walker"  # rest-of-season projections, up to 10 players in one call
./fantasypros projections --week 5 "Puka Nacua"          # single-week projections
./fantasypros rankings "Puka Nacua"                      # weekly, rest-of-season, and dynasty consensus ranks (one player per call)
./fantasypros injuries "Puka Nacua" "Kenneth Walker"     # current injury designations, up to 10 players in one call
./fantasypros news "Puka Nacua"                          # recent news with fantasy analysis (one player per call)
./fantasypros budget                                     # remaining calls (free)
```

Players can be given by name or FantasyPros ID; if a name is ambiguous, the tool lists the candidates and you pass the ID.

**The budget is tight.** The API allows only a few dozen calls a day across all uses, and this case gets at most 12. `find` and `budget` are free, and repeated queries within a few hours are served from cache for free. Plan before you query: work out which players matter, then put every player on both sides of a trade into one `projections` call rather than one call each. Most cases need two to five calls. If the tool says the budget is exhausted or the rate limit was hit, do not retry; decide the case on the record.

**The data is current, not historical.** Projections, rankings, and injuries reflect today, not the date of the dispute. If the dispute is recent, the data is a fair proxy for what a reasonable manager knew at the time. If it is older, say so, and treat the numbers as hindsight: often still useful (a trade that looks lopsided today may have looked lopsided then), but not proof of what the parties knew. The tool prints the date and week of every result; use them.

**Using it in the opinion.** The Court may take judicial notice of the FantasyPros expert consensus. Cite it plainly with its date, e.g. "FantasyPros Expert Consensus Rankings (Sept. 22, 2026) (ranking Nacua WR4 for the rest of the season)". Use specific numbers where they matter (projected rest-of-season points, consensus rank and its spread among experts), but the data informs the Court's judgment; it does not replace it. A trade can be lopsided on paper and still valid, and the opinion should say why. Do not let the analysis turn into a spreadsheet.

## Web Search

For this case, and only for football facts, you may look outside the workspace with WebSearch and WebFetch. This overrides "Do not look outside it" above. It is a last resort behind the record and `./fantasypros`, but it fills the gap FantasyPros cannot: history. Use it for things like what a player scored in a given week, when injury news broke relative to a trade or lineup lock, or what the prevailing expert view was on a past date.

- Search only for public football facts. Never search for the parties, the league, or anything personal.
- The record controls. If a web source contradicts the record about what happened in the league, the record wins; web sources speak only to the NFL.
- Keep it brief: a few targeted searches, not open-ended browsing.
- Cite what you rely on as judicial notice of a public fact, in plain text with a date, e.g. "See ESPN, Nacua Ruled Out With Ankle Sprain (Oct. 4, 2026)". Do not include URLs.

## Case Fields

For listed cases, the facts, questions presented, procedural posture, and topics are extracted from the podcast. For unlisted cases you write them. In addition to the four opinion files, write these in `opinion/` (they may be seeded with existing values; revise them to match your opinion):

- `opinion/fact_summary.md`: one paragraph of plain text, third person, summarizing the facts as found. No markup.
- `opinion/questions_presented.html`: the legal question or questions before the Court, as HTML. `<em>` is allowed for emphasis and case names.
- `opinion/procedural_posture.txt`: one short plain-text phrase, e.g. "Original petition for relief" or "Appeal from the Commissioner's ruling".
- `opinion/case_topics.txt`: two to five short lowercase topic tags, one per line. Reuse topics that already appear in `corpus/INDEX.md` where they fit.

`./lint` checks that these files are present.
