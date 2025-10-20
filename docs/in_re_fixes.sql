-- Replace all occurrences of "In re. " (with period) with "In re " (without period)
-- across all relevant text and HTML fields in the database

-- Fix FantasyCourtOpinion fields
UPDATE fantasy_court_opinions
SET authorship_html = REPLACE(authorship_html, 'In re. ', 'In re ')
WHERE authorship_html LIKE '%In re. %';

UPDATE fantasy_court_opinions
SET holding_statement_html = REPLACE(holding_statement_html, 'In re. ', 'In re ')
WHERE holding_statement_html LIKE '%In re. %';

UPDATE fantasy_court_opinions
SET reasoning_summary_html = REPLACE(reasoning_summary_html, 'In re. ', 'In re ')
WHERE reasoning_summary_html LIKE '%In re. %';

UPDATE fantasy_court_opinions
SET opinion_body_html = REPLACE(opinion_body_html, 'In re. ', 'In re ')
WHERE opinion_body_html LIKE '%In re. %';

-- Fix FantasyCourtCase fields
UPDATE fantasy_court_cases
SET case_caption = REPLACE(case_caption, 'In re. ', 'In re ')
WHERE case_caption LIKE '%In re. %';

UPDATE fantasy_court_cases
SET fact_summary = REPLACE(fact_summary, 'In re. ', 'In re ')
WHERE fact_summary LIKE '%In re. %';

UPDATE fantasy_court_cases
SET questions_presented_html = REPLACE(questions_presented_html, 'In re. ', 'In re ')
WHERE questions_presented_html IS NOT NULL AND questions_presented_html LIKE '%In re. %';

UPDATE fantasy_court_cases
SET procedural_posture = REPLACE(procedural_posture, 'In re. ', 'In re ')
WHERE procedural_posture IS NOT NULL AND procedural_posture LIKE '%In re. %';

-- Fix PodcastEpisode fields
UPDATE podcast_episodes
SET description_html = REPLACE(description_html, 'In re. ', 'In re ')
WHERE description_html IS NOT NULL AND description_html LIKE '%In re. %';
