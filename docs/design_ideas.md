# Fantasy court web app - design ideas

Context: The Ringer Fantasy Football podcast has a recurring segment called "Fantasy Court" where the hosts resolve disputes between participants in fantasy football leagues that have been emailed in.

This is a fun side project to build an official-seeming court website for the Ringer Fantasy Court docket. We'll use a mix of different AI tools to transcribe podcasts, extract cases, and generate opinions for publication on the website.

- Cloudflare pages static deployment
- Local Python backend with celery scheduling which deploys the static app to Cloudflare
- Scheduled job
    - Grab from RSS feed
    - Upsert to episodes table
        - has_fantasy_court
        - fantasy_court_start
        - fantasy_court_end
    - Download and cache episode mp3s in bucket
    - Create sliced versions of episodes based on fantasy court timestamps
    - Transcribe sliced versions with gpt-4o-transcribe with diarization, store in a transcription table
    - Use an LLM to extract timestamps and detailed summaries of individual cases, store individual cases in database table
    - For each case, use Claude Sonnet 4.5 to generate a legal opinion with HTML formatting (including small caps, italics, etc.), with majority author (or per curiam) and a dissent if someone disagrees. Store in an opinions table
    - Generate PDF with weasyprint, store in bucket

Idea: let opinion drafting agent build up a common law - go chronologically and give it access to a database of its previous opinions that it can cite, while staying faithful with the actual adjudication of the case in the episode!


## Remaining TODOs

- [ ] Entire frontend and static site generation - 10 points
- [ ] PDF generation for opinions - 5 points
- [ ]
- [x] Case creation from transcripts - 2 points
- [x] Opinion drafting agent - 10 points

automated pipeline:
 create celery job which runs every 30 minutes which:
 - ingests episodes from rss feed
 - creates segments
 - transcribes segments
 - creates cases
 - creates opinions
 - creates citations
 - exports opinions
 - builds next js static site with reference to exported opinions
 - deploys static site to cloudflare pages with wrangler
