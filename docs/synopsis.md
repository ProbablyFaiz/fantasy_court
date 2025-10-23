# Fantasy Court: A Synopsis

## What It Is

Fantasy Court is an AI-powered web application that transforms a recurring podcast segment into an official-looking appellate court docket website. The podcast hosts Danny Heifetz (Chief Justice), Danny Kelly (Justice), and Craig Horlbeck (Justice) from "The Ringer Fantasy Football Show" adjudicate humorous fantasy football disputes submitted by listeners. This system automatically:

- Transcribes podcast episodes using AssemblyAI
- Extracts individual cases and their legal proceedings using Claude Sonnet 4.5
- Generates formal judicial opinions (750-1250 words) in authentic legal prose
- Builds and deploys a static website to Cloudflare Pages

The result is a fully functional parody of an actual appellate court system, with formal case captions, docket numbers, holdings, legal reasoning, and citations between cases forming a "common law" of fantasy football jurisprudence.

## The Concept & Humor

The crux of the Fantasy Court concept lies in the contrast between content and form.

### The Content: Genuinely Absurd Disputes

Fantasy football league members argue about:
- Whether trading an injured player to a relative constitutes blackmail
- Whether making roster moves during a spouse's labor is permissible
- Whether a commissioner's trade with their father-in-law is voidable due to conflict of interest
- Whether dropping players without warning violates league norms
- Whether a waiver claim during an opponent's wedding constitutes unsportsmanlike conduct

These are fundamentally silly situations. The stakes are imaginary. The grievances are petty. The whole enterprise is ridiculous.

### The Form: Complete Legal Seriousness

Each case receives the full treatment of an appellate court opinion:

**Formal Case Captions**: "Alec v. Nick" | "In re Roster Management During Wife's Labor" | "People v. Taysom Hill"

**Docket Numbers**: Following real appellate conventions (YY-EEEE-N format): 25-0197-1, 24-0134-2

**Fact Summaries**: Written in formal legal prose that treats the situation with complete gravity

**Questions Presented**: Legal issues framed with precision and terminology

**Full Judicial Opinions** including:
- Authorship statements (which justice wrote the opinion, who concurred/dissented)
- Holding statements
- Reasoning summaries explaining the legal framework
- Complete opinion bodies with citations to precedent
- Legal analogies to contract law, fiduciary duties, and equitable principles
- Dry wit delivered in formal prose
- Disposition statements ("It is so ordered", "Petition denied", etc.)

### The Comic Mechanism

Instead of:
> "Can I trade my injured player?"

You get:
> "Commissioners owe fiduciary duties to their leagues and may not exploit information asymmetries when trading with league members. We distinguished permissible pre-news trading by ordinary managers who owe no such duties."

The hosts' actual reasoning from the podcast is preserved and formalized into coherent legal doctrine. Previous opinions are cited like real precedent, building up common law over time. Justice names appear in small caps. The site uses legal typography with equity fonts and formal layouts. Everything reads like an actual appellate court website.

The joke is not mockery of the legal system. The joke is faithful execution of legal formalism applied to situations that deserve no such dignity. It's the same principle as a nature documentary about squirrels narrated with David Attenborough gravitas. The contrast is the comedy.

## Technical Implementation

### Architecture Overview

Three major components work in concert:

1. **Backend (FastAPI + Python)**: Orchestrates pipeline, manages PostgreSQL database, provides REST API, runs AI inference
2. **Frontend (Next.js Static Site)**: Statically generated pages deployed to Cloudflare Pages
3. **Automated Pipeline (Celery)**: Scheduled ingestion and processing tasks

### Database Schema

The data model captures the full appellate court metaphor:

- **PodcastEpisode**: Metadata (title, date, MP3 URL)
- **FantasyCourtSegment**: Timestamps identifying where Fantasy Court occurs within episodes
- **EpisodeTranscript**: Full transcripts with speaker diarization (stored as JSONB)
- **FantasyCourtCase**: Individual disputes with docket numbers, case captions, fact summaries, questions presented, topics, temporal markers
- **FantasyCourtOpinion**: AI-generated opinions with authorship, holdings, reasoning summaries, full opinion bodies, agent conversation logs
- **CaseCitation**: Junction table tracking which opinions cite earlier opinions
- **Provenance**: Metadata tracking what task/model created each record

### The Automated Pipeline

**Episode Ingestion** (backend/court/ingest/):
- Fetches RSS feed from The Ringer Fantasy Football Show
- Parses episodes, extracts MP3 URLs
- Upserts to PostgreSQL (idempotent via GUID)

**Segment Detection** (backend/court/inference/create_segments.py):
- GPT-5-mini analyzes episode descriptions
- Identifies Fantasy Court segments
- Extracts start/end timestamps
- Converts time formats to seconds

**Audio Download** (backend/court/ingest/download_to_bucket.py):
- Downloads episode MP3s from podcast feed
- Stores in S3-compatible bucket
- Creates sliced versions containing only Fantasy Court segment

**Transcription** (backend/court/inference/transcribe_segments.py):
- Uses OpenAI's GPT-4o-transcribe-diarize for speech-to-text
- Returns detailed transcript with speaker diarization
- Stores in EpisodeTranscript as JSONB

**Case Extraction** (backend/court/inference/create_cases.py):
- Claude Sonnet 4.5 reads transcript excerpt
- Uses structured output (Pydantic models) to extract:
  - Case caption (creative legal naming)
  - Fact summary (formal legal prose)
  - Questions presented
  - Procedural posture
  - Case topics (tags for categorization)
- Creates docket numbers automatically

**Opinion Drafting Agent** (backend/court/inference/create_opinions.py):
- The most sophisticated component
- Claude Sonnet 4.5 with extended thinking (interleaved thinking capability)
- Agent has three tools:
  1. `list_past_opinions`: Browse all previously decided opinions
  2. `read_past_opinion`: Read full text of specific earlier opinions
  3. `submit_opinion`: Submit completed opinion

**Agent Workflow**:
1. Receives case information and podcast transcript excerpt
2. Analyzes transcript to understand hosts' actual reasoning and conclusion
3. Reviews past opinions to find relevant precedent
4. Studies 2-4 relevant earlier opinions in detail
5. Drafts complete opinion with formal legal prose
6. Submits via tool, creating FantasyCourtOpinion record

**The Agent's Prompt** (340+ lines) provides:
- Detailed guidelines on opinion structure and formatting
- HTML markup rules (only `<p>`, `<em>`, `<span class="small-caps">`, `<span data-cite-docket>` allowed)
- Citation format requirements using Bluebook signals (no signal, "See", "See also", "Cf.", "But see", "But cf.")
- Examples of authorship strings, holdings, and opinion text
- Instructions to maintain fidelity to hosts' actual reasoning
- Guidance on legal prose style ("Modern legal prose... think Kagan, Gorsuch, Newsom, Roberts, Sotomayor circa 2025")
- Encouragement for dry wit and treating absurd situations with complete seriousness

**Citation Building** (backend/court/inference/create_citations.py):
- Parses opinion HTML to extract `<span data-cite-docket="XX-XXXX-X">` citations
- Verifies cited docket numbers exist
- Creates CaseCitation records linking citing case to cited case

**Export & Static Site Generation** (backend/court/export/):
- Queries all opinions with eager-loaded data
- Exports two JSON files:
  1. index.json: Array of OpinionItem for list views
  2. opinions/{docket_number}.json: Individual OpinionRead files with full details
- Applies SmartyPants for proper quote formatting
- Frontend statically generates pages from these JSON files

### Key Technical Decisions

**1. Chronological Opinion Processing**

Cases are processed in chronological order and committed to database before later opinions are drafted. This allows the AI agent to build up real precedent over time, creating a sense of "common law development" rather than one-off opinions. The agent can cite cases that were actually decided earlier in the workflow, making the precedent authentic.

**2. Static Site Generation**

Instead of a dynamic API-driven frontend, opinions are exported to JSON and the Next.js site is statically generated. This enables deployment to Cloudflare Pages (CDN-optimized) without backend infrastructure requirements for the public site. The backend API exists for internal tooling and pipeline orchestration, but the public site is pure static HTML/CSS/JS.

**3. Extended Thinking**

Uses Claude's interleaved thinking capability to give the agent space to reason deeply about case facts, legal principles, and relevant precedent before drafting. The agent can think through analogies, consider multiple approaches, and plan the opinion structure before committing to prose.

**4. HTML Citation Markers**

Opinions use `<span data-cite-docket="XX-XXXX-X">` to mark citations. Frontend converts these to clickable links after component mount, enabling rich cross-references between opinions. This creates a web of precedent where readers can follow citation chains through the Fantasy Court common law.

**5. Tool-Based Opinion Submission**

The agent doesn't just return structured output. It actively uses tools to:
- Browse past opinions (seeing what precedent exists)
- Read specific opinions in detail (understanding earlier reasoning)
- Submit the final opinion (with validation)

This agentic approach produces better opinions because the agent can research before writing, just like a real judicial clerk.

**6. Provenance Tracking**

Every record tracks which task/model created it. This enables:
- Reproducibility (what version of the agent drafted this?)
- A/B testing (comparing opinions drafted with different prompts)
- Quality analysis (which model produces better citations?)

**7. Pydantic for Data Validation**

Pydantic models are used everywhere:
- Database responses (SQLAlchemy to Pydantic)
- API contracts (FastAPI response models)
- Structured output from AI (Claude structured output)

This ensures type safety and automatic validation across the entire stack.

### Frontend Implementation

**Technology Stack**:
- Next.js with static site generation (`getStaticProps`, `getStaticPaths`)
- React + TypeScript
- Tailwind CSS
- Legal fonts (Equity, Old English for heading)
- Lucide icons
- Client-side filtering and search

**Key Pages**:

**Home (/)**: Lists all opinions with filtering by season, opinion type (unanimous vs. divided), and full-text search. Saves filter state to sessionStorage. Paginated display shows opinion cards with case caption, docket number, authorship, and holding.

**Opinion Detail (/opinions/[docket_number])**: Displays complete opinion with:
- Case header with docket number
- Audio player linked to specific time range in podcast episode
- Procedural posture
- Full opinion body
- Citation format box with "Copy" button
- Related cases section
- "Cited By" section showing which later cases cite this opinion

**Citation Linking**: Uses `useEffect` to convert `data-cite-docket` spans to clickable links to other opinions after mount.

**Styling**: Legal typography (Equity font, Old English header, small caps for justice names), legal document layout with margins, accent color highlighting, responsive design.

### Infrastructure

- **Database**: PostgreSQL with Alembic migrations
- **Cache**: Redis for Celery
- **Job Queue**: Celery for scheduled pipeline runs
- **Storage**: S3-compatible bucket (Cloudflare R2) for MP3s
- **Frontend Hosting**: Cloudflare Pages
- **Backend**: Docker/Docker Compose for local development and production

### The Magic Moment

The most delightful technical aspect is watching the agent research precedent. When drafting an opinion about, say, whether a commissioner can trade with their father-in-law, the agent will:

1. List past opinions and see titles like "Commiss'rs Duties v. Trading Privileges" and "In re Conflict of Interest"
2. Read those opinions in full to understand established doctrine
3. Apply that doctrine to the current case
4. Cite the earlier opinions using proper Bluebook signals

The agent is not retrieving isolated facts. It's reading entire judicial opinions, synthesizing legal principles, and applying them to new situations. The result is coherent, internally consistent legal reasoning that develops over time.

This is what makes Fantasy Court more than a joke. It's a genuine experiment in whether an AI agent can maintain a coherent common law system across dozens of cases, building precedent incrementally, and producing opinions that respect both earlier doctrine and the actual reasoning of the podcast hosts.

The answer, delightfully, is yes.

## Conclusion

Fantasy Court is simultaneously:
- A loving parody of appellate courts
- A sophisticated AI pipeline orchestrating multiple models and tasks
- A case study in agentic workflows
- A static site deployed at CDN edge

It demonstrates that the funniest comedy comes not from mocking formalism, but from faithfully executing it in contexts where no reasonable person would bother. The technical sophistication is necessary because the joke only works if the execution is flawless. Mediocre legal prose would break the spell. Inconsistent precedent would undermine the conceit. The humor requires craftsmanship.

This is what happens when you give an AI agent with extended thinking access to 50 earlier judicial opinions and a podcast transcript about whether someone can drop Taysom Hill during their opponent's birthday party. You get 1,200 words of formal legal analysis citing precedent about fiduciary duties, equitable estoppel, and the reasonable expectations of fantasy football league members.

And it's absolutely perfect.
